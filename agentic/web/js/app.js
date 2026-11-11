// Gridshift console: boot, views, keyboard, dock and the voice agent loop.

import { state, on, emit } from './state.js'
import { api } from './api.js'
import * as voice from './voice.js'
import * as map from './map.js'
import * as day from './day.js'
import * as cmd from './command.js'
import * as views from './views.js'
import * as present from './present.js'
import { initPalette, togglePalette, paletteOpen, closePalette } from './palette.js'
import { $, $$, esc, delay, reduced, hooks, toast, typeText } from './util.js'

hooks.speak = (s) => voice.speak(s)
const VIEWS = ['command', 'knowledge', 'evidence', 'monitor', 'interfaces']
const line = (k) => state.meta?.lines?.[k]
const uiLine = (k) => state.meta?.lines?.ui?.[k]

/* ---------------- boot ---------------- */
async function boot() {
  bootDots()
  const linesEl = $('#bootLines')
  const add = async (label, value, cls = 'ok') => {
    const row = document.createElement('div')
    row.className = 'boot-line'
    row.innerHTML = `<span class="${cls}">${cls === 'ok' ? '[ok]' : cls === 'warn' ? '[!!]' : '[xx]'}</span><span class="t"></span>`
    linesEl.appendChild(row)
    await typeText(row.querySelector('.t'), `${label}: ${value}`, { cps: 260 })
  }
  const [hr, mr] = await Promise.all([api('/api/health'), api('/api/meta')])
  state.serverUp = hr.ok
  if (hr.ok) {
    const H = hr.data
    state.health = H
    state.dataAvailable = !!H.data_available
    voice.configure({ ttsAvailable: H.tts?.available })
    if (mr.ok) { state.meta = mr.data; state.dataAvailable = state.dataAvailable && mr.data.data_available !== false }
    const nz = state.meta?.zones?.length
    await add('ontology', `${H.ontology?.asserted_triples} to ${H.ontology?.reasoned_triples} triples`)
    await add('grid data', H.data_available ? `${nz ?? '?'} regions, ${H.day_range?.first} to ${H.day_range?.last}` : 'licensed data not installed (offline mode)', H.data_available ? 'ok' : 'warn')
    await add('optimiser', H.solver || 'unknown')
    await add('voice', H.tts?.available ? `${H.tts.engine}, ${H.tts.voice}` : 'browser voice (neural voice unavailable)', H.tts?.available ? 'ok' : 'warn')
    if (!mr.ok) await add('meta', mr.error?.message || 'failed', 'bad')
  } else {
    await add('server', 'not reachable at this address', 'bad')
    $('#offlineBanner').hidden = false
  }
  const tag = state.meta?.app?.tagline
  if (tag) { $('#bootTag').textContent = tag; $('#brandTag').textContent = tag }
  if (state.meta?.app?.subtitle) $('#bootFoot').textContent = `${state.meta.app.subtitle}. ${state.meta.app.thesis_title || ''}`
  const btn = $('#enterBtn')
  btn.disabled = false
  if (!hr.ok) btn.querySelector('span').textContent = 'Enter offline'
  btn.focus()
  btn.addEventListener('click', enter, { once: true })
}

function bootDots() {
  const c = $('#bootDots')
  const g = c.getContext('2d')
  const t0 = performance.now()
  const frame = (now) => {
    if (!$('#boot') || $('#boot').classList.contains('out')) return
    const w = c.width = innerWidth; const hh = c.height = innerHeight
    const t = (now - t0) / 1000
    g.clearRect(0, 0, w, hh)
    for (let y = 18; y < hh; y += 26) {
      for (let x = 18; x < w; x += 26) {
        const d = Math.hypot(x - w / 2, y - hh * 0.42) / Math.hypot(w, hh)
        const a = Math.max(0, Math.min(1, t * 1.4 - d * 3)) * (0.08 + 0.1 * Math.sin(x * 0.05 + y * 0.03 + t * 1.2) ** 2)
        g.fillStyle = `rgba(18,26,38,${a * 1.1})`
        g.fillRect(x, y, 1.6, 1.6)
      }
    }
    if (!reduced()) requestAnimationFrame(frame)
  }
  requestAnimationFrame(frame)
}

let entered = false
function enter() {
  if (entered) return
  entered = true
  voice.unlock()
  $('#boot').classList.add('out')
  setTimeout(() => $('#boot').remove(), 800)
  const app = $('#app')
  app.classList.add('on')
  app.removeAttribute('aria-hidden')
  start()
}

/* ---------------- app start ---------------- */
function start() {
  if (state.meta?.default) state.req = { ...state.meta.default }
  setDataPill()
  setVoicePill(state.health?.tts?.available ? 'neural' : 'browser')
  map.initMap(state.meta)
  day.initDay()
  cmd.initCommand()
  present.initPresent({ setView, ask, setLens })
  initPalette(paletteItems)
  initDock()
  initTabs()
  initKeys()
  renderLens()
  glyph()
  voice.startOrb($('#orb'))
  setView('command', { quiet: true })

  if (!state.serverUp) {
    cmd.showOffline()
    $('#stageMsg').textContent = 'Server not reachable. Start it with: python -m agentic.serve'
    views.prefetch()
    return
  }
  if (state.dataAvailable) cmd.loadPlan({ autoPlay: true })
  else cmd.showOffline()
  views.prefetch()
  const greet = line('greeting')
  if (greet) setTimeout(() => { if (!state.presenting) voice.speak(greet) }, 500)
}

on('data', () => setDataPill())
on('voice:engine', (e) => setVoicePill(e))
on('mute', (m) => {
  const b = $('#muteBtn')
  b.setAttribute('aria-pressed', String(m))
  b.title = m ? 'Unmute voice (M)' : 'Mute voice (M)'
})

function setDataPill() {
  const p = $('#dataPill')
  if (!state.serverUp) { p.className = 'pill pill-red'; p.innerHTML = '<i></i><span>Server down</span>'; return }
  if (state.dataAvailable) { p.className = 'pill pill-live'; p.innerHTML = '<i></i><span>Live data</span>'; p.title = 'Every number is computed live from the thesis code' }
  else { p.className = 'pill pill-amber'; p.innerHTML = '<i></i><span>Data offline</span>'; p.title = line('data_offline')?.caption || 'Licensed grid data not installed' }
}

function setVoicePill(engine) {
  const p = $('#voicePill')
  const name = (state.health?.tts?.voice || '').replace(/^en-US-|Neural$/g, '') || 'neural'
  if (engine === 'neural') { p.className = 'pill pill-live'; p.innerHTML = `<i></i><span>Voice: ${esc(name)}</span>` }
  else if (engine === 'browser') { p.className = 'pill pill-mute'; p.innerHTML = '<i></i><span>Browser voice</span>' }
  else { p.className = 'pill pill-amber'; p.innerHTML = '<i></i><span>Captions only</span>' }
}

function glyph() {
  const g = $('.glyph-dots')
  const pos = []
  for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) pos.push([9 + c * 7, 9 + r * 7])
  g.innerHTML = pos.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="2.1" fill="#d5dbe2"/>`).join('')
  const dots = [...g.children]
  let i = 0
  const seq = [6, 3, 4, 1, 2, 5, 8]
  const tick = () => {
    dots.forEach((d) => d.setAttribute('fill', '#d5dbe2'))
    for (let k = 0; k < 3; k++) {
      const d = dots[seq[(i + k) % seq.length]]
      d.setAttribute('fill', k === 2 ? '#2443d6' : k === 1 ? '#7c8899' : '#aeb7c2')
    }
    i++
  }
  tick()
  if (!reduced()) setInterval(tick, 650)
}

/* ---------------- views ---------------- */
function initTabs() {
  $$('.tab').forEach((t) => t.addEventListener('click', () => setView(t.dataset.view, { speakIt: false })))
  window.addEventListener('resize', moveInk)
}

function moveInk() {
  const t = $(`.tab[data-view="${state.view}"]`)
  const ink = $('.tab-ink')
  if (!t || !ink) return
  ink.style.width = `${t.offsetWidth}px`
  ink.style.transform = `translateX(${t.offsetLeft}px)`
}

export function setView(v, { speakIt = false } = {}) {
  if (!VIEWS.includes(v)) return
  state.view = v
  $$('.view').forEach((s) => s.classList.toggle('on', s.dataset.view === v))
  $$('.tab').forEach((t) => { t.classList.toggle('on', t.dataset.view === v); t.setAttribute('aria-selected', String(t.dataset.view === v)) })
  moveInk()
  emit('view', v)
  views.onViewShown(v)
  if (speakIt && uiLine(v)) voice.speak(uiLine(v))
}

/* ---------------- lens ---------------- */
function renderLens() {
  const L = state.meta?.lens || []
  const el = $('#lens')
  el.innerHTML = `<div class="lens-h"><div><div class="lens-t">Supply chain lens</div><div class="lens-s">The same problem in operations terms</div></div><button class="icon-btn" id="lensClose" aria-label="Close lens"><svg viewBox="0 0 20 20"><path d="M5 5l10 10M15 5 5 15" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/></svg></button></div>
    ${L.length ? `<div class="lens-cols"><span>Compute</span><span></span><span>Supply chain</span></div>
    ${L.map((r, i) => `<div class="lens-row" style="animation-delay:${i * 70}ms"><span class="c">${esc(r.compute)}</span><span class="ar">&rarr;</span><span class="s">${esc(r.supply_chain)}</span><span class="n">${esc(r.note)}</span></div>`).join('')}`
    : '<div class="khint">The lens loads from the server. It is not reachable right now.</div>'}`
  $('#lensClose').addEventListener('click', () => setLens(false))
  $('#lensBtn').addEventListener('click', () => setLens(!state.lensOpen))
}

function setLens(open) {
  state.lensOpen = open
  const el = $('#lens')
  if (open) { el.hidden = false; el.querySelectorAll('.lens-row').forEach((r) => { r.style.animation = 'none'; void r.offsetWidth; r.style.animation = '' }) }
  else el.hidden = true
  $('#lensBtn').classList.toggle('on', open)
}

/* ---------------- dock + asking ---------------- */
let chipsT = 0
function initDock() {
  const dock = $('#dock')
  const input = $('#askInput')
  const chips = $('#dockChips')
  chips.innerHTML = (state.meta?.suggestions || []).map((s) => `<button class="sugg" type="button">${esc(s)}</button>`).join('')
  chips.querySelectorAll('.sugg').forEach((b) => b.addEventListener('mousedown', (e) => { e.preventDefault(); input.blur(); ask(b.textContent) }))
  input.addEventListener('focus', () => { clearTimeout(chipsT); dock.classList.add('chips-on') })
  input.addEventListener('blur', () => { chipsT = setTimeout(() => dock.classList.remove('chips-on'), 150) })
  $('#askForm').addEventListener('submit', (e) => {
    e.preventDefault()
    const t = input.value.trim()
    if (!t) return
    input.value = ''
    ask(t)
  })
  $('#sendBtn').addEventListener('click', () => $('#askForm').requestSubmit())
  $('#micBtn').addEventListener('click', () => (listening ? voice.stopListening() : listen()))
  $('#muteBtn').addEventListener('click', () => toggleMute())
  $('#presentBtn').addEventListener('click', () => (present.isPresenting() ? present.stopPresent() : startTour()))
  $('#bannerRetry').addEventListener('click', () => location.reload())
  if (!voice.micAvailable()) micUnavailable(false)
}

function toggleMute(force) {
  const m = typeof force === 'boolean' ? force : !state.muted
  voice.setMuted(m)
  toast(m ? 'Voice muted. Captions stay on.' : 'Voice on.')
}

let listening = false
function listen() {
  if (present.isPresenting()) return
  const dock = $('#dock')
  const tr = $('#dockTranscript')
  const ok = voice.startListening({
    onInterim: (t) => { tr.innerHTML = `<span class="you">listening</span> ${esc(t)}` },
    onFinal: (t) => { if (t) ask(t) },
    onError: (code) => {
      if (['network', 'not-allowed', 'service-not-allowed', 'audio-capture', 'unsupported'].includes(code)) micUnavailable(true)
    },
    onEnd: () => { listening = false; dock.classList.remove('listening') },
  })
  if (ok) { listening = true; dock.classList.add('listening'); tr.innerHTML = '<span class="you">listening</span>' }
}

let micWarned = false
function micUnavailable(say) {
  $('#micBtn').hidden = true
  $('#askInput').placeholder = 'Type a question. Voice input is not available here.'
  if (say && !micWarned && line('mic_unavailable')) { micWarned = true; voice.speak(line('mic_unavailable')) }
}

const UI = [
  [/\b(present|presentation|tour|walk me through|demo)\b/i, () => startTour()],
  [/\b(stop|cancel|quiet|enough)\b/i, () => { present.stopPresent(); day.pause(); voice.stop(); say('stopped') }],
  [/\bunmute\b/i, () => toggleMute(false)],
  [/\bmute\b/i, () => toggleMute(true)],
  [/\b(show|open|go to)\b.*\b(map|command|home)\b/i, () => setView('command', { speakIt: true })],
  [/\b(show|open|go to)\b.*\b(knowledge|ontology|graph)\b/i, () => setView('knowledge', { speakIt: true })],
  [/\b(show|open|go to)\b.*\b(evidence|findings)\b/i, () => setView('evidence', { speakIt: true })],
  [/\b(show|open|go to)\b.*\b(interfaces?|agent card)\b/i, () => setView('interfaces', { speakIt: true })],
  [/\b(show|open|go to)\b.*\b(monitor)\b/i, () => setView('monitor', { speakIt: true })],
  [/^\s*play( the day)?\b/i, () => { setView('command'); day.play() }],
  [/^\s*pause\b/i, () => day.pause()],
  [/\bapprove\b/i, () => cmd.decide('approve'), () => state.gate === 'pending'],
  [/\breject\b/i, () => cmd.decide('reject'), () => state.gate === 'pending'],
  [/\b(supply chain|lens)\b/i, () => { setLens(!state.lensOpen); if (state.lensOpen) say('lens') }],
]

function say(k, skipIfMuted) { const s = uiLine(k); if (s && !(skipIfMuted && state.muted)) voice.speak(s) }

function uiCommand(text) {
  for (const [re, fn, guard] of UI) {
    if (re.test(text) && (!guard || guard())) { fn(); return true }
  }
  return false
}

const PLANNY = /\b(plan|schedule|training|train|etl|pipeline|batch|move|what about|and on|june|july|august|may|today|tomorrow)\b/i

export async function ask(text, { present: inPresent = false, signal } = {}) {
  const tr = $('#dockTranscript')
  tr.innerHTML = `<span class="you">you</span> ${esc(text)}`
  $('#dockReply').hidden = true
  if (!inPresent && uiCommand(text)) return null
  if (!state.serverUp) { const e = line('error'); voice.speak(e || { caption: 'The server is not reachable. Start it with python -m agentic.serve.' }); return null }

  voice.setOrb('thinking')
  const optimistic = state.dataAvailable && PLANNY.test(text)
  if (optimistic) { setView('command'); cmd.stripBusy() }
  const r = await api('/api/ask', { method: 'POST', body: { text, context: state.context } })
  voice.setOrb('idle')
  // a stopped tour must not change the screen afterwards
  if (signal && signal.aborted) { if (optimistic) cmd.restoreStrip(); return null }
  if (!r.ok) {
    if (optimistic) cmd.restoreStrip()
    showReply(r.error?.message || 'The request failed.', 'Error')
    if (!inPresent) voice.speak(r.error?.speech || line('error'))
    return null
  }
  const d = r.data
  if (d.context) state.context = d.context
  if (d.view && d.view !== state.view) setView(d.view)
  if (d.intent === 'propose_migration' && d.data) {
    await Promise.all([
      cmd.applyPlan(d.data, { autoPlay: !inPresent, present: inPresent }),
      inPresent ? null : voice.speak(d.speech),
    ])
  } else {
    if (optimistic) cmd.restoreStrip()
    views.applyAskData(d.intent, d.data, d.args)
    if (!inPresent && d.answer && d.answer !== d.speech?.caption) showReply(d.answer, d.intent?.replace(/_/g, ' '))
    if (!inPresent) voice.speak(d.speech)
  }
  return d
}

function showReply(text, title) {
  const r = $('#dockReply')
  r.innerHTML = `<button class="rx" aria-label="Close">&times;</button><div class="rt">${esc(title || 'Answer')}</div>${esc(text)}`
  r.hidden = false
  r.querySelector('.rx').addEventListener('click', () => { r.hidden = true })
}

function startTour() {
  if (present.isPresenting()) return
  setLens(false)
  $('#dockReply').hidden = true
  present.startPresent()
}

/* ---------------- keyboard ---------------- */
function initKeys() {
  let spaceDown = false
  document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); togglePalette(); return }
    if (paletteOpen()) return
    if (e.key === 'Escape') {
      if (present.isPresenting()) present.stopPresent()
      voice.stop(); voice.stopListening(); day.pause(); setLens(false)
      $('#dockReply').hidden = true
      document.activeElement?.blur?.()
      return
    }
    const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName) || document.activeElement?.isContentEditable
    if (typing || e.ctrlKey || e.metaKey || e.altKey) return
    if (e.key === ' ') {
      e.preventDefault()
      if (!e.repeat && !spaceDown && voice.micAvailable()) { spaceDown = true; listen() }
      return
    }
    if (/^[1-5]$/.test(e.key)) { setView(VIEWS[+e.key - 1]); return }
    const k = e.key.toLowerCase()
    if (k === 'p') { present.isPresenting() ? present.stopPresent() : startTour(); return }
    if (k === 'm') { toggleMute(); return }
    if (k === 'l') { setLens(!state.lensOpen); return }
    if (e.key === 'ArrowRight') { e.preventDefault(); if (present.isPresenting()) present.skipStep(); else day.scrub(1); return }
    if (e.key === 'ArrowLeft') { e.preventDefault(); if (!present.isPresenting()) day.scrub(-1) }
  })
  document.addEventListener('keyup', (e) => {
    if (e.key === ' ' && spaceDown) { spaceDown = false; voice.stopListening() }
  })
}

function paletteItems() {
  const items = [
    ...VIEWS.map((v, i) => ({ group: 'Views', label: `Go to ${v[0].toUpperCase()}${v.slice(1)}`, hint: String(i + 1), icon: String(i + 1), run: () => setView(v) })),
    { group: 'Actions', label: 'Present the 3 minute tour', hint: 'P', icon: '>', run: () => startTour() },
    { group: 'Actions', label: 'Play the day', icon: '>', keys: 'scrubber', run: () => { setView('command'); day.play({ from: 0 }) } },
    { group: 'Actions', label: 'Run reasoner', icon: 'R', keys: 'ontology knowledge', run: () => { setView('knowledge'); views.runReasoner() } },
    { group: 'Actions', label: 'Run evals', icon: 'E', keys: 'interfaces tests', run: () => { setView('interfaces'); views.runEvals() } },
    { group: 'Actions', label: 'Approve the pending plan', icon: 'A', run: () => cmd.decide('approve') },
    { group: 'Actions', label: 'Reject the pending plan', icon: 'X', run: () => cmd.decide('reject') },
    { group: 'Actions', label: 'Toggle supply chain lens', hint: 'L', icon: 'L', run: () => setLens(!state.lensOpen) },
    { group: 'Actions', label: state.muted ? 'Unmute voice' : 'Mute voice', hint: 'M', icon: 'M', run: () => toggleMute() },
  ]
  for (const j of state.meta?.jobs || []) {
    items.push({ group: 'Jobs', label: `Plan: ${j.label}`, icon: 'J', keys: j.job, hint: j.flexible ? 'flexible' : 'fixed', run: () => { setView('command'); cmd.setJob(j.job) } })
  }
  return items
}

document.addEventListener('keydown', (e) => {
  if (!entered && e.key === 'Enter' && !$('#enterBtn')?.disabled) { e.preventDefault(); enter() }
})

// stray errors should never surface as uncaught
window.addEventListener('unhandledrejection', (e) => { console.warn('[gridshift] unhandled', e.reason); e.preventDefault() })

boot()

export { closePalette }
