"""Gridshift: a local, voice-driven console for the capstone.

    python -m agentic.serve [--port 8765] [--host 127.0.0.1] [--no-browser] [--quiet]

Serves the web app in agentic/web/ and a small JSON API (see console.py). Standard
library only. Binds to localhost: the licensed data never leaves this machine.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import threading
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from . import console, voice

WEB_DIR = Path(__file__).with_name("web")
MAX_BODY = 64 * 1024
MIME = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml",
        ".json": "application/json", ".mp3": "audio/mpeg", ".png": "image/png", ".ico": "image/x-icon",
        ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8", ".webp": "image/webp", ".jpg": "image/jpeg"}


def _ascii(text: str) -> str:
    return text.encode("ascii", "replace").decode("ascii")


class Handler(BaseHTTPRequestHandler):
    server_version = "Gridshift/1.0"
    quiet = False

    # ---------------------------------------------------------------- plumbing

    def log_message(self, fmt, *args):
        if not self.quiet:
            print(_ascii("[gridshift] " + (fmt % args)), flush=True)

    def _send(self, status: int, body: bytes, ctype: str, headers: dict | None = None):
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, obj, status: int = 200):
        body = json.dumps(obj, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self._send(status, body, "application/json; charset=utf-8", {"Cache-Control": "no-store"})

    def _error(self, err: console.ApiError):
        self._json(err.body(), err.status)

    def _body(self):
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_BODY:
            raise console.BadRequestError("request body too large")
        raw = self.rfile.read(n) if n else b""
        try:
            return json.loads(raw.decode("utf-8") or "{}")
        except (UnicodeDecodeError, ValueError):
            raise console.BadRequestError("body is not valid JSON") from None

    def _base_url(self) -> str:
        host = self.headers.get("Host") or f"localhost:{self.server.server_address[1]}"
        return f"http://{host}"

    def _dispatch(self, fn):
        try:
            fn()
        except console.ApiError as e:
            self._error(e)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except FileNotFoundError as e:
            self._error(console.DataUnavailableError(_ascii(str(e))))
        except Exception as e:
            print(_ascii(f"[gridshift] error on {self.path}: {type(e).__name__}: {e}"), flush=True)
            if not self.quiet:
                print(_ascii(traceback.format_exc()), flush=True)
            try:
                self._error(console.ApiError(f"{type(e).__name__}: {_ascii(str(e))[:200]}", console.LINES["error"]))
            except Exception:
                pass

    # ---------------------------------------------------------------- verbs

    def do_GET(self):
        self._dispatch(self._get)

    def do_HEAD(self):
        self._dispatch(self._get)

    def do_POST(self):
        self._dispatch(self._post)

    def _get(self):
        url = urlsplit(self.path)
        q = {k: v[-1] for k, v in parse_qs(url.query).items()}
        path = url.path
        routes = {
            "/api/health": console.health,
            "/api/meta": console.meta,
            "/api/plan": lambda: console.plan(q.get("job"), q.get("day"), q.get("share")),
            "/api/sweep": lambda: console.sweep(q.get("job"), q.get("day"), q.get("shares")),
            "/api/findings": console.findings,
            "/api/graph": console.graph,
            "/api/drift": lambda: console.drift(q.get("portfolio", "all"), q.get("start"), q.get("end")),
            "/api/evals": console.evals,
            "/api/interfaces": lambda: console.interfaces(self._base_url()),
            "/api/present": console.present,
        }
        if path in routes:
            return self._json(routes[path]())
        if path == "/api/tts":
            return self._tts(q.get("text", ""))
        if path == "/.well-known/agent-card.json":
            from . import a2a
            return self._json(a2a.agent_card(self._base_url()))
        if path.startswith(("/api/", "/.well-known/")) or path == "/a2a":
            raise console.NotFoundError(f"no route {path}")
        return self._static(path)

    def _post(self):
        path = urlsplit(self.path).path
        if path == "/a2a":
            return self._a2a()
        if path == "/api/ask":
            body = self._body()
            if not isinstance(body, dict):
                raise console.BadRequestError("body must be a JSON object")
            return self._json(console.ask(str(body.get("text") or ""), body.get("context")))
        if path == "/api/decision":
            return self._json(console.decide(self._body()))
        raise console.NotFoundError(f"no route POST {path}")

    # ---------------------------------------------------------------- special routes

    def _a2a(self):
        from . import a2a

        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(min(n, MAX_BODY)) if n else b""
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return self._json({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
        try:
            return self._json(a2a.handle(payload))
        except FileNotFoundError:
            rid = payload.get("id") if isinstance(payload, dict) else None
            return self._json({"jsonrpc": "2.0", "id": rid,
                               "error": {"code": -32603, "message": "The licensed grid data is not installed here."}})

    def _tts(self, text: str):
        text = text.strip()
        if not text:
            raise console.BadRequestError("text is empty")
        if len(text) > voice.MAX_CHARS:
            raise console.BadRequestError(f"text is longer than {voice.MAX_CHARS} characters")
        hit = voice.is_cached(text)
        try:
            audio = voice.synthesize(text)
        except voice.TTSUnavailable as e:
            raise console.TTSUnavailableError(f"neural voice unavailable: {e}",
                                              "The neural voice is not available, so I'll use the browser voice.") from None
        self._send(200, audio, "audio/mpeg", {"X-Voice-Cache": "hit" if hit else "miss",
                                              "Cache-Control": "max-age=86400"})

    def _static(self, path: str):
        rel = unquote(path).lstrip("/") or "index.html"
        root = WEB_DIR.resolve()
        try:
            target = (root / rel).resolve()
        except (OSError, ValueError):
            raise console.NotFoundError("not found") from None
        if not target.is_relative_to(root):
            raise console.NotFoundError("not found")
        if target.is_dir():
            target = target / "index.html"
        if not target.is_file():
            raise console.NotFoundError(f"no file {path}")
        ctype = MIME.get(target.suffix.lower()) or mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self._send(200, target.read_bytes(), ctype, {"Cache-Control": "no-cache"})


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False   # on Windows this would let two servers share a port


def make_server(host: str = "127.0.0.1", port: int = 8765, quiet: bool = False) -> Server:
    handler = type("GridshiftHandler", (Handler,), {"quiet": quiet})
    return Server((host, port), handler)


def warm(quiet: bool = False) -> None:
    """Ontology, voice engine and the Present script, in the background."""
    def go():
        for name, fn in (("ontology", lambda: console.knowledge.graph(True)), ("voice", voice.engine),
                         ("meta", console.meta), ("present", console.present)):
            try:
                fn()
                if not quiet:
                    print(f"[gridshift] warmed {name}", flush=True)
            except Exception as e:
                print(_ascii(f"[gridshift] could not warm {name}: {type(e).__name__}"), flush=True)
    threading.Thread(target=go, daemon=True).start()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Gridshift: the local console for the capstone.")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    try:
        srv = make_server(a.host, a.port, a.quiet)
    except OSError as e:
        print(_ascii(f"[gridshift] cannot listen on {a.host}:{a.port}: {e}"), flush=True)
        return 1
    url = f"http://localhost:{srv.server_address[1]}"
    print(f"[gridshift] serving {url}  (Ctrl+C to stop)", flush=True)
    if not WEB_DIR.joinpath("index.html").is_file():
        print("[gridshift] note: agentic/web/index.html not found yet, only the API is live", flush=True)
    warm(a.quiet)
    if not a.no_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("[gridshift] stopped", flush=True)
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
