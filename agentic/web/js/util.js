// Small helpers shared by every view.

export const reduced = () => window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false

export const $ = (sel, root = document) => root.querySelector(sel)
export const $$ = (sel, root = document) => [...root.querySelectorAll(sel)]

export function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
}

export function h(tag, attrs = {}, html = '') {
  const n = document.createElement(tag)
  for (const [k, v] of Object.entries(attrs)) {
    if (v === false || v == null) continue
    if (k === 'class') n.className = v
    else if (k.startsWith('on') && typeof v === 'function') n.addEventListener(k.slice(2), v)
    else n.setAttribute(k, v === true ? '' : v)
  }
  if (html) n.innerHTML = html
  return n
}

export const delay = (ms, signal) => new Promise((res) => {
  const t = setTimeout(res, ms)
  signal?.addEventListener?.('abort', () => { clearTimeout(t); res() }, { once: true })
})

export const clamp = (v, a, b) => Math.max(a, Math.min(b, v))
export const lerp = (a, b, t) => a + (b - a) * t
export const easeOut = (t) => 1 - Math.pow(1 - t, 3)
export const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2)

// Numbers: one decimal, trailing .0 dropped. Never invents a value.
export function fmt(v, dp = 1) {
  if (v === null || v === undefined || Number.isNaN(+v)) return '--'
  const s = (+v).toFixed(dp)
  return dp > 0 ? s.replace(/\.0+$/, '') : s
}
export const fmtFixed = (v, dp = 1) => (v === null || v === undefined || Number.isNaN(+v) ? '--' : (+v).toFixed(dp))

// Ease-out cubic over 850 ms from whatever is on screen now (Titan pattern).
export function animateNumber(el, to, { format = (n) => fmt(n), duration = 850 } = {}) {
  if (!el) return
  cancelAnimationFrame(el._raf)
  if (to === null || to === undefined || Number.isNaN(+to)) { el._v = undefined; el.textContent = '--'; return }
  const from = typeof el._v === 'number' ? el._v : 0
  if (reduced() || Math.abs(to - from) < 1e-9) { el._v = to; el.textContent = format(to); return }
  let start = 0
  const tick = (ts) => {
    if (!start) start = ts
    const t = Math.min((ts - start) / duration, 1)
    const v = from + (to - from) * easeOut(t)
    el._v = v
    el.textContent = format(t >= 1 ? to : v)
    if (t < 1) el._raf = requestAnimationFrame(tick)
    else el._v = to
  }
  el._raf = requestAnimationFrame(tick)
}

// Types text into an element. Resolves when done or aborted.
export function typeText(el, text, { cps = 90, signal } = {}) {
  return new Promise((res) => {
    if (!el) return res()
    if (reduced()) { el.textContent = text; return res() }
    el.textContent = ''
    let i = 0
    const step = Math.max(1, Math.round(cps / 40))
    const iv = setInterval(() => {
      if (signal?.aborted) { el.textContent = text; clearInterval(iv); return res() }
      i = Math.min(text.length, i + step)
      el.textContent = text.slice(0, i)
      if (i >= text.length) { clearInterval(iv); res() }
    }, 1000 / 40)
  })
}

// Carbon ramp from the spec: 0 emerald, 200 data, 450 amber, 700+ red.
// clean to dirty: cold blue, sea green, amber, red. Lime stays reserved for savings and actions.
const RAMP = [[0, [69, 168, 196]], [200, [111, 191, 155]], [450, [227, 179, 65]], [700, [224, 90, 71]]]
export function carbonRGB(g) {
  if (g === null || g === undefined || Number.isNaN(+g)) return [110, 125, 120]
  if (g <= RAMP[0][0]) return RAMP[0][1]
  for (let i = 1; i < RAMP.length; i++) {
    if (g <= RAMP[i][0]) {
      const [a, ca] = RAMP[i - 1]; const [b, cb] = RAMP[i]
      const t = (g - a) / (b - a)
      return ca.map((c, k) => Math.round(lerp(c, cb[k], t)))
    }
  }
  return RAMP[RAMP.length - 1][1]
}
export const carbonColor = (g, a = 1) => { const [r, gg, b] = carbonRGB(g); return `rgba(${r},${gg},${b},${a})` }

const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
export const MONTHS_SHORT = MONTHS.map((m) => m.slice(0, 3))
export function dayLabel(iso) {
  if (!iso) return ''
  const [y, m, d] = iso.split('-').map(Number)
  return `${MONTHS_SHORT[m - 1]} ${d}, ${y}`
}
export function monthLabel(ym) {
  if (!ym) return ''
  const [y, m] = ym.split('-').map(Number)
  return `${MONTHS_SHORT[m - 1]} ${String(y).slice(2)}`
}

// Syntax-coloured JSON as HTML.
export function jsonHTML(obj) {
  const s = JSON.stringify(obj, null, 2) ?? ''
  return esc(s).replace(/(&quot;(?:[^&]|&(?!quot;))*?&quot;)(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)/g,
    (m, str, colon, bool, num) => {
      if (str) return colon ? `<span class="k">${str}</span>${colon}` : `<span class="s">${str}</span>`
      if (bool) return `<span class="b">${bool}</span>`
      if (num) return `<span class="n">${num}</span>`
      return m
    })
}

// Panel states: loading (shimmer), error (message + retry), ok (content).
export function setLoading(el, rows = 4) {
  if (!el) return
  el.dataset.state = 'loading'
  const widths = ['w60', '', 'w80', 'w40', '', 'w60']
  el.innerHTML = `<div class="ps-skel">${Array.from({ length: rows }, (_, i) => `<div class="skel ${i === 1 ? 'tall' : widths[i % widths.length]}"></div>`).join('')}</div>`
}

export const hooks = { speak: null }

export function setError(el, error, retry, { title = 'Could not load this panel' } = {}) {
  if (!el) return
  el.dataset.state = 'error'
  const msg = (error && error.message) || 'Something went wrong.'
  el.innerHTML = `<div class="ps-error">
    <div class="err-t"><svg width="16" height="16" viewBox="0 0 20 20"><path d="M10 2.5 18 17H2z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M10 8v4M10 14.2v.3" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>${esc(title)}</div>
    <div class="err-m">${esc(msg)}</div>
    <div class="err-a"></div></div>`
  const actions = el.querySelector('.err-a')
  if (retry) {
    const b = h('button', { class: 'btn-ghost btn-sm' }, 'Retry')
    b.addEventListener('click', () => retry())
    actions.append(b)
  }
  if (error && error.speech && hooks.speak) {
    const b = h('button', { class: 'btn-ghost btn-sm' }, 'Explain')
    b.addEventListener('click', () => hooks.speak(error.speech))
    actions.append(b)
  }
}

let toastT = 0
export function toast(text, ms = 2400) {
  const t = document.getElementById('toast')
  if (!t) return
  t.textContent = text
  t.classList.add('on')
  clearTimeout(toastT)
  toastT = setTimeout(() => t.classList.remove('on'), ms)
}

// Canvas sized for the device pixel ratio. Returns {ctx, w, h}.
export function fitCanvas(canvas) {
  const r = canvas.getBoundingClientRect()
  const dpr = Math.min(window.devicePixelRatio || 1, 2)
  const w = Math.max(1, Math.round(r.width)); const hh = Math.max(1, Math.round(r.height))
  if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(hh * dpr)) {
    canvas.width = Math.round(w * dpr); canvas.height = Math.round(hh * dpr)
  }
  const ctx = canvas.getContext('2d')
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  return { ctx, w, h: hh }
}
