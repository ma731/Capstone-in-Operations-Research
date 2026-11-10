// Voice: neural audio from /api/tts, browser voice as fallback, captions always.
// Also owns speech recognition, the orb and the caption line.

import { state, emit } from './state.js'
import { reduced, esc } from './util.js'

let ctx = null
let analyser = null
let source = null
let token = 0
let ttsEnabled = true
let level = 0
let orbState = 'idle'
let lastEngine = null
const buffers = new Map()

// ---------- audio ----------
export function unlock() {
  try {
    if (!ctx) {
      const AC = window.AudioContext || window.webkitAudioContext
      if (!AC) return
      ctx = new AC()
      analyser = ctx.createAnalyser()
      analyser.fftSize = 512
      analyser.smoothingTimeConstant = 0.6
      analyser.connect(ctx.destination)
    }
    if (ctx.state === 'suspended') ctx.resume().catch(() => {})
  } catch { ctx = null }
  try { window.speechSynthesis?.getVoices() } catch { /* voices load later */ }
}

export function configure({ ttsAvailable }) { ttsEnabled = !!ttsAvailable }

function setEngine(name) {
  if (name === lastEngine) return
  lastEngine = name
  emit('voice:engine', name)
}

function fetchBuffer(tts) {
  if (!ctx || !ttsEnabled || !tts) return Promise.resolve(null)
  if (buffers.has(tts)) return buffers.get(tts)
  const p = (async () => {
    const ctrl = new AbortController()
    const t = setTimeout(() => ctrl.abort(), 6000)
    try {
      const res = await fetch(`/api/tts?text=${encodeURIComponent(tts)}`, { signal: ctrl.signal })
      if (!res.ok) return null
      const ab = await res.arrayBuffer()
      return await new Promise((ok) => {
        try { ctx.decodeAudioData(ab, (b) => ok(b), () => ok(null)) } catch { ok(null) }
      })
    } catch { return null } finally { clearTimeout(t) }
  })()
  buffers.set(tts, p)
  p.then((b) => { if (!b) buffers.delete(tts) })
  if (buffers.size > 48) buffers.delete(buffers.keys().next().value)
  return p
}

export function preload(speech) { if (speech && speech.tts) fetchBuffer(speech.tts) }

// Titan's voice ranking, extended with the spec's names.
function pickVoice() {
  const vs = window.speechSynthesis?.getVoices?.() || []
  const en = vs.filter((v) => /^en[-_]/i.test(v.lang))
  const rank = (v) => (/natural|neural/i.test(v.name) ? 8 : 0) + (/online/i.test(v.name) ? 4 : 0)
    + (/(ava|andrew|emma|aria|jenny)/i.test(v.name) ? 3 : 0) + (/en-us/i.test(v.lang) ? 1 : 0)
  return en.sort((a, b) => rank(b) - rank(a))[0] || null
}

const estimateMs = (text) => Math.max(1400, (String(text).split(/\s+/).filter(Boolean).length / 2.45) * 1000 + 500)

export function isSpeaking() { return orbState === 'speaking' }

export function stop() {
  token++
  try { source?.stop() } catch { /* already stopped */ }
  source = null
  try { window.speechSynthesis?.cancel() } catch { /* no synth */ }
  captions.hide(400)
  if (orbState === 'speaking') setOrb('idle')
}

export function setMuted(m) {
  state.muted = m
  if (m) {
    try { source?.stop() } catch { /* ok */ }
    try { window.speechSynthesis?.cancel() } catch { /* ok */ }
  }
  emit('mute', m)
}

// Speaks a {caption, tts} Speech object. Resolves when it has finished or was stopped.
export async function speak(speech, { signal } = {}) {
  if (!speech) return
  const caption = speech.caption || speech.tts || ''
  const tts = speech.tts || speech.caption || ''
  if (!caption && !tts) return
  stop()
  const my = ++token
  const alive = () => my === token && !(signal && signal.aborted)
  captions.show(caption)
  setOrb('speaking')

  if (state.muted) {
    await timedCaptions(estimateMs(tts), alive)
  } else {
    const buf = await fetchBuffer(tts)
    if (!alive()) return
    if (buf && ctx) {
      setEngine('neural')
      await playBuffer(buf, alive)
    } else if ('speechSynthesis' in window && window.SpeechSynthesisUtterance) {
      setEngine('browser')
      await synth(tts, alive)
    } else {
      setEngine('captions')
      await timedCaptions(estimateMs(tts), alive)
    }
  }
  if (my === token) {
    captions.progress(1)
    captions.hide(1600)
    setOrb('idle')
  }
}

function playBuffer(buf, alive) {
  return new Promise((done) => {
    try {
      if (ctx.state === 'suspended') ctx.resume().catch(() => {})
      const src = ctx.createBufferSource()
      src.buffer = buf
      src.connect(analyser)
      source = src
      const t0 = ctx.currentTime
      let finished = false
      const end = () => { if (finished) return; finished = true; done() }
      src.onended = end
      src.start()
      const tick = () => {
        if (finished) return
        if (!alive()) { try { src.stop() } catch { /* ok */ } end(); return }
        captions.progress((ctx.currentTime - t0) / buf.duration)
        requestAnimationFrame(tick)
      }
      requestAnimationFrame(tick)
      // safety net if onended never fires
      setTimeout(end, buf.duration * 1000 + 1500)
    } catch { done() }
  })
}

function synth(text, alive) {
  return new Promise((done) => {
    let finished = false
    const end = () => { if (finished) return; finished = true; clearTimeout(safety); done() }
    const est = estimateMs(text)
    const safety = setTimeout(end, est * 2 + 4000)
    try {
      const u = new SpeechSynthesisUtterance(text.replace(/\s+/g, ' '))
      const v = pickVoice()
      if (v) { u.voice = v; u.lang = v.lang } else u.lang = 'en-US'
      u.rate = 0.97; u.pitch = 0.95
      const start = performance.now()
      let byBoundary = false
      u.onboundary = (e) => { if (typeof e.charIndex === 'number' && text.length) { byBoundary = true; captions.progress(e.charIndex / text.length) } }
      u.onend = end
      u.onerror = end
      window.speechSynthesis.cancel()
      window.speechSynthesis.speak(u)
      const tick = () => {
        if (finished) return
        if (!alive()) { try { window.speechSynthesis.cancel() } catch { /* ok */ } end(); return }
        if (!byBoundary) captions.progress((performance.now() - start) / est)
        requestAnimationFrame(tick)
      }
      requestAnimationFrame(tick)
    } catch { end() }
  })
}

function timedCaptions(ms, alive) {
  return new Promise((done) => {
    const start = performance.now()
    let over = false
    const end = () => { if (!over) { over = true; done() } }
    // timer backstop: rAF pauses when the tab is hidden
    const iv = setInterval(() => { if (!alive() || performance.now() - start >= ms) { clearInterval(iv); captions.progress(1); end() } }, 250)
    const tick = () => {
      if (over) return
      if (!alive()) return end()
      const f = (performance.now() - start) / ms
      captions.progress(f)
      if (f >= 1) return end()
      requestAnimationFrame(tick)
    }
    requestAnimationFrame(tick)
  })
}

// ---------- captions ----------
export const captions = (() => {
  const el = () => document.getElementById('captions')
  let words = []
  let hideT = 0
  return {
    show(text) {
      const c = el(); if (!c) return
      clearTimeout(hideT)
      c.classList.remove('fade')
      const parts = String(text).split(/\s+/).filter(Boolean)
      c.innerHTML = `<span class="cap-in">${parts.map((w) => `<span class="w todo">${esc(w)}</span>`).join(' ')}</span>`
      words = [...c.querySelectorAll('.w')]
      if (reduced()) words.forEach((w) => w.classList.remove('todo'))
    },
    progress(f) {
      if (!words.length) return
      const n = Math.min(words.length, Math.ceil(Math.max(0, f) * words.length))
      for (let i = 0; i < n; i++) words[i].classList.remove('todo')
    },
    hide(ms = 1200) {
      const c = el(); if (!c) return
      clearTimeout(hideT)
      hideT = setTimeout(() => { c.classList.add('fade'); setTimeout(() => { if (c.classList.contains('fade')) { c.innerHTML = ''; words = [] } }, 650) }, ms)
    },
    clear() { const c = el(); if (c) { c.innerHTML = ''; words = [] } },
  }
})()

// ---------- speech recognition ----------
const SR = window.SpeechRecognition || window.webkitSpeechRecognition
let rec = null
let micBlocked = !SR
export const micAvailable = () => !micBlocked

export function startListening({ onInterim, onFinal, onError, onEnd } = {}) {
  if (micBlocked) { onError?.('unsupported'); return false }
  stop() // barge in
  try { rec?.abort() } catch { /* ok */ }
  try {
    rec = new SR()
    rec.lang = 'en-US'
    rec.interimResults = true
    rec.continuous = false
    rec.maxAlternatives = 1
    let gotFinal = false
    rec.onresult = (e) => {
      let interim = ''
      for (let i = e.resultIndex; i < e.results.length; i++) {
        const r = e.results[i]
        if (r.isFinal) { gotFinal = true; onFinal?.(r[0].transcript.trim()) } else interim += r[0].transcript
      }
      if (interim) onInterim?.(interim)
    }
    rec.onerror = (e) => {
      if (['network', 'not-allowed', 'service-not-allowed', 'audio-capture'].includes(e.error)) micBlocked = true
      onError?.(e.error)
    }
    rec.onend = () => { setOrb(orbState === 'listening' ? 'idle' : orbState); onEnd?.(gotFinal) }
    rec.start()
    setOrb('listening')
    return true
  } catch {
    onError?.('start-failed')
    return false
  }
}

export function stopListening() { try { rec?.stop() } catch { /* ok */ } }

// ---------- orb ----------
export function setOrb(s) {
  orbState = s
  emit('orb', s)
}

export function startOrb(canvas) {
  if (!canvas) return
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const S = 52
  canvas.width = S * dpr; canvas.height = S * dpr
  const g = canvas.getContext('2d')
  const data = new Float32Array(512)
  let t = 0
  let last = performance.now()
  const frame = (now) => {
    const dt = Math.min(0.05, (now - last) / 1000); last = now
    const calm = reduced()
    t += dt * (calm ? 0.25 : 1)

    // loudness: real audio when playing, otherwise procedural while speaking
    let target = 0
    if (orbState === 'speaking') {
      if (source && analyser) {
        analyser.getFloatTimeDomainData(data)
        let sum = 0
        for (let i = 0; i < data.length; i++) sum += data[i] * data[i]
        target = Math.min(1, Math.sqrt(sum / data.length) * 5.5)
      } else {
        target = 0.35 + 0.3 * Math.abs(Math.sin(t * 7.3) * Math.sin(t * 3.1 + 1))
      }
    }
    level += (target - level) * (target > level ? 0.45 : 0.12)

    g.setTransform(dpr, 0, 0, dpr, 0, 0)
    g.clearRect(0, 0, S, S)
    const cx = S / 2; const cy = S / 2
    const breathe = calm ? 0 : Math.sin(t * 1.6) * 0.8
    const R = 12.5 + breathe + level * 6

    // listening: expanding rings
    if (orbState === 'listening') {
      for (let k = 0; k < 3; k++) {
        const p = ((t * 0.9 + k / 3) % 1)
        g.beginPath(); g.arc(cx, cy, R + p * 11, 0, Math.PI * 2)
        g.strokeStyle = `rgba(20,232,160,${(1 - p) * 0.7})`; g.lineWidth = 1.5; g.stroke()
      }
    }

    // glow
    const glow = g.createRadialGradient(cx, cy, R * 0.4, cx, cy, R + 12)
    const ga = orbState === 'idle' ? 0.18 : 0.32 + level * 0.3
    glow.addColorStop(0, `rgba(20,232,160,${ga})`); glow.addColorStop(1, 'rgba(20,232,160,0)')
    g.fillStyle = glow; g.beginPath(); g.arc(cx, cy, R + 12, 0, Math.PI * 2); g.fill()

    // blob with noise displacement
    const amp = 0.06 + level * 0.18 + (orbState === 'thinking' ? 0.05 : 0)
    g.beginPath()
    const N = 48
    for (let i = 0; i <= N; i++) {
      const a = (i / N) * Math.PI * 2
      const n = Math.sin(a * 3 + t * 1.9) * 0.5 + Math.sin(a * 5 - t * 2.7) * 0.3 + Math.sin(a * 2 + t * 0.8) * 0.2
      const r = R * (1 + amp * n)
      const x = cx + Math.cos(a) * r; const y = cy + Math.sin(a) * r
      if (i === 0) g.moveTo(x, y); else g.lineTo(x, y)
    }
    g.closePath()
    const fill = g.createRadialGradient(cx - R * 0.35, cy - R * 0.45, 1, cx, cy, R * 1.2)
    fill.addColorStop(0, '#d9ffe9'); fill.addColorStop(0.3, '#5ff6c4'); fill.addColorStop(0.75, '#14b886'); fill.addColorStop(1, '#0a6e50')
    g.fillStyle = fill; g.fill()

    // thinking: rotating arc
    if (orbState === 'thinking') {
      g.beginPath(); g.arc(cx, cy, R + 6, t * 4.2, t * 4.2 + Math.PI * 0.9)
      g.strokeStyle = 'rgba(168,255,53,.9)'; g.lineWidth = 2; g.lineCap = 'round'; g.stroke()
    }
    requestAnimationFrame(frame)
  }
  requestAnimationFrame(frame)
}
