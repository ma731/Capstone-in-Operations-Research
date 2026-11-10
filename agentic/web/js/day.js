// Play the day: the hourly scrubber, the playhead and the three-way tonnes race.

import { state, emit } from './state.js'
import { carbonColor, clamp, fmtFixed, esc } from './util.js'

const HOUR_MS = 700
let scrubEl = null
let playBtn = null
let cols = []
let playhead = null
let raf = 0
let lastTs = 0
let playResolve = null
let playTimer = 0

const pad = (n) => String(n).padStart(2, '0')
const sum = (a) => (a || []).reduce((x, y) => x + y, 0)

export function initDay() {
  scrubEl = document.getElementById('scrubber')
  renderScrubber(null)
}

export function renderScrubber(plan) {
  if (!scrubEl) return
  const P = plan && plan.plan
  const hr = P && P.hourly
  scrubEl.innerHTML = `
    <div class="scrub-ctl">
      <button class="play-btn" id="playBtn" aria-label="Play the day" title="Play the day">
        <svg viewBox="0 0 20 20" class="ic-play"><path d="M6 4.5v11l9-5.5z" fill="currentColor"/></svg>
      </button>
      <span class="scrub-lab">Play day</span>
    </div>
    <div class="scrub-body" id="scrubBody">
      <div class="scrub-cols" id="scrubCols"></div>
      <div class="scrub-axis">${Array.from({ length: 24 }, (_, i) => `<span>${i % 3 === 0 ? pad(i) : ''}</span>`).join('')}</div>
      <div class="playhead" id="playhead"></div>
    </div>`
  playBtn = scrubEl.querySelector('#playBtn')
  playhead = scrubEl.querySelector('#playhead')
  const colsEl = scrubEl.querySelector('#scrubCols')
  cols = []

  if (!hr || !state.dataAvailable) {
    playBtn.disabled = true
    colsEl.innerHTML = Array.from({ length: 24 }, () => '<div class="scol"></div>').join('')
    cols = [...colsEl.children]
    playhead.style.display = 'none'
    return
  }

  // stacked load per zone, each segment coloured by that zone's carbon that hour
  const zones = P.zones
  let maxCol = 0
  for (let i = 0; i < 24; i++) maxCol = Math.max(maxCol, zones.reduce((a, z) => a + (hr.load_with_migration_mwh[z]?.[i] || 0), 0))
  maxCol = maxCol || 1
  for (let i = 0; i < 24; i++) {
    const c = document.createElement('div')
    c.className = 'scol'
    c.dataset.h = i
    let tip = `${pad(i)}:00 UTC`
    for (const z of zones) {
      const load = hr.load_with_migration_mwh[z]?.[i] || 0
      const g = hr.actual_g_per_kwh[z]?.[i]
      const s = document.createElement('div')
      s.className = 'sseg'
      s.style.height = `${(load / maxCol) * 100}%`
      s.style.backgroundColor = carbonColor(g, 0.85)
      c.appendChild(s)
      tip += `\n${z}: ${fmtFixed(load, 2)} MWh at ${fmtFixed(g, 0)} g`
    }
    c.title = tip
    colsEl.appendChild(c)
    cols.push(c)
  }

  playBtn.addEventListener('click', () => togglePlay())
  const body = scrubEl.querySelector('#scrubBody')
  const fromX = (e) => {
    const r = colsEl.getBoundingClientRect()
    const i = clamp(Math.floor(((e.clientX - r.left) / r.width) * 24), 0, 23)
    pause()
    setHour(i + 0.999)
  }
  body.addEventListener('pointerdown', (e) => {
    fromX(e)
    body.setPointerCapture?.(e.pointerId)
    const move = (ev) => fromX(ev)
    const up = () => { body.removeEventListener('pointermove', move); body.removeEventListener('pointerup', up) }
    body.addEventListener('pointermove', move)
    body.addEventListener('pointerup', up)
  })
  paint()
}

export function setHour(h) {
  state.hour = clamp(h, 0, 24)
  paint()
  emit('hour', state.hour)
}

// cumulative tonnes up to hour h, smooth within the hour
function cumul(series, h) {
  if (!series) return null
  if (h >= 24) return sum(series)
  const i = Math.floor(h)
  return sum(series.slice(0, i)) + (h - i) * (series[i] || 0)
}

function paint() {
  const h = state.hour
  const plan = state.plan
  const P = plan && plan.plan
  // scrubber
  if (cols.length && P) {
    const cur = h >= 24 ? -1 : Math.floor(h)
    cols.forEach((c, i) => {
      c.classList.toggle('cur', i === cur)
      c.classList.toggle('past', h >= 24 || i < cur)
    })
    if (playhead) {
      playhead.style.display = h >= 24 ? 'none' : ''
      playhead.style.left = `${(Math.min(h, 24) / 24) * 100}%`
    }
  }
  // hour readout
  const big = document.getElementById('hourBig')
  const sub = document.getElementById('hourSub')
  if (big && sub) {
    if (!P || !state.dataAvailable) { big.textContent = '--:--'; sub.textContent = 'UTC' }
    else if (h >= 24) { big.textContent = '24 h'; sub.textContent = 'Full day, UTC' }
    else { big.textContent = `${pad(Math.floor(h))}:00`; sub.textContent = `UTC, hour ${Math.floor(h) + 1} of 24` }
  }
  if (playBtn) {
    playBtn.innerHTML = state.playing
      ? '<svg viewBox="0 0 20 20"><rect x="5" y="4.5" width="3.5" height="11" rx="1" fill="currentColor"/><rect x="11.5" y="4.5" width="3.5" height="11" rx="1" fill="currentColor"/></svg>'
      : '<svg viewBox="0 0 20 20"><path d="M6 4.5v11l9-5.5z" fill="currentColor"/></svg>'
    playBtn.setAttribute('aria-label', state.playing ? 'Pause' : 'Play the day')
  }
  paintRace()
}

export function paintRace() {
  const root = document.getElementById('kpis')
  if (!root) return
  const rows = root.querySelectorAll('.race-row')
  if (!rows.length) return
  const P = state.plan && state.plan.plan
  const tb = P && P.hourly && P.hourly.tonnes_by_hour
  const h = state.hour
  const vals = !tb || !state.dataAvailable ? [null, null, null]
    : h >= 24 ? [P.tonnes_flat, P.tonnes_time_shift_only, P.tonnes_with_migration]
      : [cumul(tb.flat, h), cumul(tb.time_shift, h), cumul(tb.migration, h)]
  const max = P ? (P.tonnes_flat || Math.max(...vals.filter((v) => v !== null), 1)) : 1
  rows.forEach((r, i) => {
    const bar = r.querySelector('.race-bar')
    const v = r.querySelector('.race-v')
    if (vals[i] === null || vals[i] === undefined) { bar.style.width = '0%'; v.textContent = '--'; return }
    bar.style.width = `${clamp((vals[i] / max) * 100, 0, 100)}%`
    v.textContent = `${fmtFixed(vals[i], 2)} t`
  })
  const foot = root.querySelector('.race-span')
  if (foot) foot.textContent = !P ? '' : h >= 24 ? 'whole day, 00:00 to 24:00 UTC' : `00:00 to ${pad(Math.floor(h))}:${pad(Math.floor((h % 1) * 60))} UTC`
}

export function play({ from } = {}) {
  if (!state.plan || !state.plan.plan || !state.dataAvailable) return Promise.resolve()
  if (from !== undefined) state.hour = from
  else if (state.hour >= 24) state.hour = 0
  state.playing = true
  emit('playing', true)
  cancelAnimationFrame(raf)
  lastTs = 0
  const p = new Promise((res) => { playResolve = res })
  // hour follows wall time, so a hidden tab (no rAF) still finishes on schedule
  const h0 = state.hour; const t0 = performance.now()
  const step = () => {
    if (!state.playing) return false
    state.hour = Math.min(24, h0 + (performance.now() - t0) / HOUR_MS)
    paint()
    emit('hour', state.hour)
    if (state.hour >= 24) { finish(); return false }
    return true
  }
  const tick = () => { if (step()) raf = requestAnimationFrame(tick) }
  clearInterval(playTimer)
  playTimer = setInterval(() => { if (!state.playing) clearInterval(playTimer); else step() }, 300)
  raf = requestAnimationFrame(tick)
  paint()
  return p
}

function finish() {
  state.playing = false
  cancelAnimationFrame(raf)
  clearInterval(playTimer)
  paint()
  emit('playing', false)
  const r = playResolve; playResolve = null
  r?.()
}

export function pause() { if (state.playing) finish() }
export function togglePlay() { if (state.playing) pause(); else play() }

export function scrub(delta) {
  if (!state.plan || !state.plan.plan) return
  pause()
  const cur = state.hour >= 24 ? 24 : Math.floor(state.hour)
  const next = clamp(cur + delta, 0, 24)
  setHour(next >= 24 ? 24 : next + 0.999)
}

export function raceHTML() {
  return `<div class="race">
    <div class="race-row flat"><span class="race-l"><i></i>Run flat</span><div class="race-track"><div class="race-bar"></div></div><span class="race-v">--</span></div>
    <div class="race-row ts"><span class="race-l"><i></i>Shift hours only</span><div class="race-track"><div class="race-bar"></div></div><span class="race-v">--</span></div>
    <div class="race-row mig"><span class="race-l"><i></i>Shift and move</span><div class="race-track"><div class="race-bar"></div></div><span class="race-v">--</span></div>
    <div class="race-foot"><span>Cumulative ${esc('t CO2eq')}</span><span class="race-span"></span></div>
  </div>`
}
