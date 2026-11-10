// Present mode: a hands-free narrated tour with a spotlight on each panel.

import { state, emit } from './state.js'
import { api } from './api.js'
import { speak, stop as stopVoice, preload, captions } from './voice.js'
import * as cmd from './command.js'
import * as day from './day.js'
import * as map from './map.js'
import * as views from './views.js'
import { delay, typeText, reduced } from './util.js'

let app = null       // {setView, ask, setLens}
let run = null       // {abort: AbortController, skip: fn}
let spotTarget = null
let spotRaf = 0

// no numbers here: used only if /api/present fails
const FALLBACK = [
  { id: 'f1', view: 'command', action: 'boot', spotlight: null, min_ms: 2500, speech: { caption: "Hi, I'm Gridshift. I decide where and when a company's computing should run, so it runs on the cleanest power the grid has." } },
  { id: 'f2', view: 'command', action: 'focus_map', spotlight: '#map', min_ms: 3000, speech: { caption: 'Each dot is a grid region. Flexible work moves toward the regions with the cleanest power, and a person signs off every move.' } },
  { id: 'f3', view: 'evidence', action: 'show_findings', spotlight: '#rq-cards', min_ms: 3000, speech: { caption: 'The thesis found that moving work between regions pays, while the more sophisticated layers mostly do not.' } },
  { id: 'f4', view: 'knowledge', action: 'run_reasoner', spotlight: '#kgraph', min_ms: 3000, speech: { caption: 'The rules live in an ontology, and a reasoner works out where each job may go.' } },
  { id: 'f5', view: 'command', action: 'close', spotlight: null, min_ms: 2000, speech: { caption: "Explainable, measured, and a person signs off every move. That's Gridshift. Ask me anything." } },
]

export function initPresent(ctx) {
  app = ctx
  document.getElementById('presentStop').addEventListener('click', () => stopPresent())
}

export const isPresenting = () => !!run

// ---------- spotlight ----------
export function spotlight(sel) {
  const s = document.getElementById('spotlight')
  cancelAnimationFrame(spotRaf)
  spotTarget = sel ? document.querySelector(sel) : null
  if (!spotTarget) { s.classList.remove('on'); document.getElementById('captions')?.classList.remove('cap-high'); return }
  // only scroll the panel column that holds the target, never the page
  const box = spotTarget.closest('.cmd-right, .ev-wrap, .drift-body')
  if (box) {
    const top = spotTarget.offsetTop - box.offsetTop - Math.max(0, (box.clientHeight - spotTarget.offsetHeight) / 3)
    box.scrollTo({ top: Math.max(0, top), behavior: reduced() ? 'auto' : 'smooth' })
  }
  s.classList.add('on')
  const follow = () => {
    if (!spotTarget) return
    const r = spotTarget.getBoundingClientRect()
    const p = 8
    s.style.left = `${r.left - p}px`; s.style.top = `${r.top - p}px`
    s.style.width = `${r.width + p * 2}px`; s.style.height = `${r.height + p * 2}px`
    placeCaptions(r)
    spotRaf = requestAnimationFrame(follow)
  }
  follow()
}

// keep the caption off the spotlit panel: bottom by default, top if that covers less of it
function placeCaptions(r) {
  const cap = document.getElementById('captions')
  if (!cap) return
  const ch = Math.max(48, cap.getBoundingClientRect().height)
  const vh = window.innerHeight
  const topBar = 56 + 64
  const bottomY = vh - 60 - 30 - ch
  const cw = Math.min(880, window.innerWidth - 32); const cx0 = (window.innerWidth - cw) / 2
  const xo = Math.max(0, Math.min(r.right, cx0 + cw) - Math.max(r.left, cx0))
  if (!xo) { cap.classList.remove('cap-high'); return }
  const ov = (y0) => Math.max(0, Math.min(r.bottom, y0 + ch) - Math.max(r.top, y0))
  const low = ov(bottomY); const high = ov(topBar)
  const isHigh = cap.classList.contains('cap-high')
  if (!isHigh && high + 20 < low) cap.classList.add('cap-high')
  else if (isHigh && low + 20 < high) cap.classList.remove('cap-high')
}

async function fakeClick(btn, signal) {
  const c = document.getElementById('fakeCursor')
  if (!btn) return
  const r = btn.getBoundingClientRect()
  const x1 = r.left + r.width / 2; const y1 = r.top + r.height / 2
  c.style.transition = 'none'
  c.style.transform = `translate(${x1 + 140}px, ${y1 + 110}px)`
  c.classList.add('on')
  c.getBoundingClientRect()
  c.style.transition = 'transform .9s cubic-bezier(.77,0,.175,1), opacity .3s'
  c.style.transform = `translate(${x1}px, ${y1}px)`
  await delay(reduced() ? 0 : 950, signal)
  c.classList.remove('click'); void c.offsetWidth; c.classList.add('click')
  btn.classList.add('pressed')
  await delay(160, signal)
  btn.classList.remove('pressed')
  setTimeout(() => c.classList.remove('on', 'click'), 700)
}

// ---------- actions ----------
async function act(step, signal) {
  const a = step.action
  const args = step.args || {}
  switch (a) {
    case 'boot':
      app.setLens(false)
      map.focusPulse()
      return
    case 'focus_map':
      app.setLens(false)
      map.focusPulse()
      return
    case 'show_lens':
      app.setLens(true)
      return
    case 'type_query': {
      app.setLens(false)
      const input = document.getElementById('askInput')
      input.value = ''
      const text = args.text || ''
      if (reduced()) input.value = text
      else for (let i = 1; i <= text.length; i++) { if (signal.aborted) { input.value = ''; return } input.value = text.slice(0, i); await delay(35, signal) }
      await delay(250, signal)
      input.value = ''
      if (signal.aborted) return
      await app.ask(text, { present: true, signal })
      return
    }
    case 'strip_step':
      await cmd.animateStrip(args.n || 1)
      return
    case 'play_day':
      if (!state.plan?.plan) return
      await day.play({ from: 0 })
      return
    case 'show_kpis':
      if (state.hour < 24) day.setHour(24)
      await cmd.animateStrip(4)
      return
    case 'gate_approve': {
      await cmd.animateStrip(5)
      if (state.plan?.status !== 'PENDING_APPROVAL') return
      cmd.showGate()
      await delay(1500, signal)
      if (signal.aborted) return
      await fakeClick(document.getElementById('approveBtn'), signal)
      if (signal.aborted) return
      await cmd.decide('approve', { by: 'Present mode (demo)', silent: true })
      return
    }
    case 'show_findings':
      await views.ensureFindings()
      await views.animateEvidence()
      return
    case 'show_rq3':
      await views.ensureFindings()
      await views.sweepNeedle()
      return
    case 'show_ladder':
      await views.ensureFindings()
      await views.growLadder()
      return
    case 'run_reasoner':
      await views.ensureGraph()
      await views.runReasoner()
      if (state.meta?.default?.job) views.selectNode(state.meta.default.job)
      return
    case 'show_drift':
      await views.ensureDrift()
      await views.animateDrift()
      return
    case 'run_evals':
      await views.ensureInterfaces()
      await views.runEvals()
      return
    case 'close':
      app.setLens(false)
      return
    default:
  }
}

// ---------- runner ----------
export async function startPresent() {
  if (run) return
  const abort = new AbortController()
  run = { abort, skip: null }
  state.presenting = true
  document.body.classList.add('presenting')
  document.getElementById('presentBar').hidden = false
  document.getElementById('presentBtn').classList.add('live')
  document.getElementById('presentStep').textContent = 'loading'
  emit('present', true)
  app.setView('command')
  stopVoice()

  const r = await api('/api/present')
  if (abort.signal.aborted) return
  const steps = r.ok && r.data?.steps?.length ? r.data.steps : FALLBACK
  if (!r.ok) console.warn('[gridshift] /api/present failed, using the short tour')
  if (steps[0]) preload(steps[0].speech)

  for (let i = 0; i < steps.length; i++) {
    if (abort.signal.aborted) break
    const st = steps[i]
    document.getElementById('presentStep').textContent = `${i + 1} / ${steps.length}`
    document.getElementById('presentFill').style.width = `${((i + 1) / steps.length) * 100}%`
    if (steps[i + 1]) preload(steps[i + 1].speech)
    if (st.view && st.view !== state.view) { app.setView(st.view); await delay(reduced() ? 0 : 450, abort.signal) }
    if (st.action !== 'show_lens' && st.action !== 'type_query') spotlight(st.spotlight)
    else setTimeout(() => { if (run) spotlight(st.spotlight) }, 60)

    const stepAbort = new AbortController()
    const skipP = new Promise((res) => { run.skip = () => { stepAbort.abort(); res() } })
    abort.signal.addEventListener('abort', () => stepAbort.abort(), { once: true })
    const actionP = Promise.race([act(st, stepAbort.signal).catch((e) => console.warn('[gridshift] present step failed', st.id, e)), delay(25000, stepAbort.signal)])
    const speechP = speak(st.speech, { signal: stepAbort.signal })
    await Promise.race([Promise.all([actionP, speechP, delay(st.min_ms || 0, stepAbort.signal)]), skipP])
    if (stepAbort.signal.aborted && !abort.signal.aborted) { stopVoice(); day.pause() }
    await delay(350, abort.signal)
  }
  finishPresent()
}

export function skipStep() { run?.skip?.() }

export function stopPresent() {
  if (!run) return
  run.abort.abort()
  const input = document.getElementById('askInput')
  if (input) input.value = ''
  stopVoice()
  day.pause()
  finishPresent()
}

function finishPresent() {
  if (!run) return
  run = null
  state.presenting = false
  spotlight(null)
  document.getElementById('fakeCursor').classList.remove('on')
  document.body.classList.remove('presenting')
  document.getElementById('presentBar').hidden = true
  document.getElementById('presentBtn').classList.remove('live')
  captions.hide(2500)
  emit('present', false)
}
