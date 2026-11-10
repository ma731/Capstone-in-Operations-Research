// Fetch wrapper. Never throws: always resolves to {ok, status, data, error}.

const LONG = ['/api/plan', '/api/sweep', '/api/ask', '/api/evals', '/api/present']

export async function api(path, { method = 'GET', body, timeout } = {}) {
  const ms = timeout ?? (LONG.some((p) => path.startsWith(p)) ? 25000 : 8000)
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), ms)
  try {
    const res = await fetch(path, {
      method,
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: body !== undefined ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
      cache: 'no-store',
    })
    let data = null
    try { data = await res.json() } catch { data = null }
    if (!res.ok) {
      const error = (data && data.error) || { code: `http_${res.status}`, message: `The server answered ${res.status}.` }
      return { ok: false, status: res.status, data: null, error }
    }
    return { ok: true, status: res.status, data, error: null }
  } catch (e) {
    const timeout = e && e.name === 'AbortError'
    return {
      ok: false, status: 0, data: null,
      error: { code: timeout ? 'timeout' : 'network', message: timeout ? 'The request timed out.' : 'Server not reachable.' },
    }
  } finally {
    clearTimeout(timer)
  }
}

export const qs = (o) => Object.entries(o)
  .filter(([, v]) => v !== undefined && v !== null && v !== '')
  .map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join('&')
