// Command view: controls, workflow strip, KPIs, approval gate, audit log, sweep curve.

import { state, emit } from './state.js'
import { api, qs } from './api.js'
import * as day from './day.js'
import * as map from './map.js'
import { speak } from './voice.js'
import { esc, h, delay, fmt, fmtFixed, animateNumber, typeText, setLoading, setError, toast, dayLabel, reduced, clamp } from './util.js'

const STEP_TITLES = ['Ontology check', 'Forecast', 'Optimise', 'Explain', 'Human approval']
const ILLUSTRATION = 'one day, scored on realised carbon. Thesis metric: out-of-sample CVaR95.'
const SHARES = [0, 0.1, 0.2, 0.3, 0.4, 0.5]

let planSeq = 0
let sweepSeq = 0
let stripTypers = []

const el = (id) => document.getElementById(id)

export function initCommand() {
  renderControls()
  renderLegend()
  renderStrip(null)
  renderKpis()
  renderGate()
  renderAudit()
  renderSweep()
}

// ---------- controls ----------
function renderControls() {
  const meta = state.meta
  const chips = el('jobChips')
  chips.innerHTML = ''
  for (const j of meta?.jobs || []) {
    const b = h('button', { class: 'chip', 'data-job': j.job, title: j.flexible ? `Flexible: may move within ${j.portfolio || 'its portfolio'}` : 'Fixed: user-facing, never moves' },
      `${esc(j.label)} <span class="tag">${j.flexible ? 'flex' : 'fixed'}</span>`)
    b.addEventListener('click', () => setJob(j.job))
    chips.appendChild(b)
  }
  const dayIn = el('dayInput')
  const range = meta?.day_range || state.health?.day_range
  if (range) { dayIn.min = range.first; dayIn.max = range.last }
  dayIn.addEventListener('change', () => {
    if (!dayIn.value) return
    state.req.day = dayIn.value
    loadPlan({ autoPlay: true, speakIt: true })
  })
  const share = el('shareInput')
  let t = 0
  share.addEventListener('input', () => {
    syncShare(+share.value)
    clearTimeout(t)
    t = setTimeout(() => { state.req.share = +(+share.value).toFixed(1); loadPlan({ quiet: true }) }, 260)
  })
  syncControls()
}

function syncShare(v) {
  const share = el('shareInput')
  share.value = v
  share.style.setProperty('--p', `${(v / 0.5) * 100}%`)
  el('shareVal').textContent = `${Math.round(v * 100)}%`
}

export function syncControls() {
  const off = !state.dataAvailable
  document.querySelectorAll('#jobChips .chip').forEach((c) => {
    c.classList.toggle('on', c.dataset.job === state.req.job)
    c.disabled = off
  })
  const dayIn = el('dayInput')
  dayIn.value = state.req.day
  dayIn.disabled = off
  el('shareInput').disabled = off
  syncShare(state.req.share)
}

function renderLegend() {
  const s = state.meta?.carbon_scale
  const lg = el('carbonLegend')
  if (!s) { lg.innerHTML = ''; return }
  lg.innerHTML = `<span class="legend-t">Carbon intensity, ${esc(s.unit)}</span><div class="legend-bar"></div>
    <div class="legend-ticks"><span>${s.min}</span><span>200</span><span>450</span><span>${s.max}</span></div>`
}

export function setJob(job, opts = {}) {
  state.req.job = job
  syncControls()
  return loadPlan({ autoPlay: true, speakIt: true, ...opts })
}

// ---------- plan loading ----------
export async function loadPlan({ autoPlay = false, speakIt = false, quiet = false, present = false } = {}) {
  if (!state.dataAvailable) { showOffline(); return null }
  const my = ++planSeq
  state.planState = 'loading'
  if (!quiet) stripBusy()
  if (!state.plan) setLoading(el('kpis'), 5)
  el('stageMsg').hidden = true
  const r = await api(`/api/plan?${qs(state.req)}`)
  if (my !== planSeq) return null
  if (!r.ok) {
    state.planState = 'error'
    state.planError = r.error
    if (r.error && r.error.code === 'data_unavailable') { state.dataAvailable = false; emit('data', false); showOffline(); return null }
    renderStrip(null)
    setError(el('kpis'), r.error, () => loadPlan({ autoPlay, speakIt }), { title: 'Could not plan this day' })
    stageMessage(r.error?.message || 'The plan could not be computed.', true)
    if (speakIt && r.error?.speech) speak(r.error.speech)
    return null
  }
  await applyPlan(r.data, { autoPlay, speakIt, quiet, present })
  return r.data
}

export async function applyPlan(plan, { autoPlay = false, speakIt = false, quiet = false, present = false } = {}) {
  if (!plan) return
  const prevKey = state.plan ? `${state.plan.job}|${state.plan.day}` : ''
  state.plan = plan
  state.planState = 'ok'
  state.req = { job: plan.job || state.req.job, day: plan.day || state.req.day, share: plan.transfer_share ?? state.req.share }
  state.context = { ...state.context, job: state.req.job, day: state.req.day }
  syncControls()
  el('stageMsg').hidden = true

  state.gate = 'none'
  renderGate()
  map.setPlan(plan)
  day.pause()
  day.renderScrubber(plan)
  renderKpis()
  day.setHour(autoPlay || present ? 0 : 24)
  renderStrip(plan)
  el('flowsNote').innerHTML = plan.plan?.flows_note ? `<b>Flows:</b> ${esc(plan.plan.flows_note)}` : ''

  if (`${plan.job}|${plan.day}` !== prevKey || !state.sweep) loadSweep()
  else renderSweep()

  if (!plan.plan) stageMessage(notMovableText(plan), false)
  if (speakIt && plan.speech) speak(plan.speech)
  emit('plan', plan)

  if (present) { setStripLit(1, { busyNext: true }); return }
  if (quiet) { setStripLit(plan.plan ? 5 : 1, { instant: true }); if (plan.status === 'PENDING_APPROVAL') showGate({ quiet: true }); return }
  if (autoPlay && plan.plan) day.play({ from: 0 })
  await animateStrip(plan.plan ? 5 : 1)
  if (plan.status === 'PENDING_APPROVAL' && state.plan === plan) showGate()
}

function notMovableText(plan) {
  const s1 = plan.steps?.[0]?.lines?.join(' ')
  return s1 || plan.speech?.caption || 'This job cannot move.'
}

function stageMessage(text, amber) {
  const m = el('stageMsg')
  m.textContent = text
  m.classList.toggle('amber', !!amber)
  m.hidden = false
}

export function showOffline() {
  state.plan = null
  state.planState = 'offline'
  map.setPlan(null)
  day.renderScrubber(null)
  renderStrip(null, { offline: true })
  renderKpis()
  state.gate = 'none'
  renderGate()
  renderSweep()
  syncControls()
  const line = state.meta?.lines?.data_offline?.caption || 'The licensed grid data is not installed on this machine, so live plans are off.'
  stageMessage(line, true)
  el('flowsNote').innerHTML = ''
}

// ---------- workflow strip ----------
function renderStrip(plan, { offline = false } = {}) {
  const strip = el('strip')
  stripTypers.forEach((c) => c.abort()); stripTypers = []
  state.stripLit = 0
  const steps = plan?.steps || []
  strip.innerHTML = STEP_TITLES.map((t, i) => {
    const s = steps.find((x) => x.n === i + 1)
    const title = s?.title || t
    const full = s ? (s.lines || []).join(' ') : ''
    const shown = s ? (s.headline || full) : ''
    const muted = plan && !s ? ' muted' : ''
    return `<div class="step${muted}" data-n="${i + 1}" title="${esc(full)}">
      <div class="step-h"><span class="step-n">${i + 1}</span><span class="step-t">${esc(title)}</span></div>
      <div class="step-l" data-full="${esc(shown)}">${offline && i === 0 ? 'Live plans need the licensed grid data.' : ''}</div>
      <div class="step-fill"></div></div>`
  }).join('')
}

// put the strip back as it was after an optimistic start that was not a plan
export function restoreStrip() {
  if (!state.plan) { renderStrip(null, { offline: !state.dataAvailable }); return }
  renderStrip(state.plan)
  setStripLit(state.plan.plan ? 5 : 1, { instant: true })
}

export function stripBusy() {
  const steps = [...el('strip').querySelectorAll('.step')]
  steps.forEach((s) => { s.classList.remove('active', 'done', 'pending', 'ok-approved', 'busy'); const l = s.querySelector('.step-l'); if (l) l.textContent = '' })
  steps[0]?.classList.add('busy')
  state.stripLit = 0
}

export function setStripLit(n, { instant = false, busyNext = false } = {}) {
  const steps = [...el('strip').querySelectorAll('.step')]
  steps.forEach((s, i) => {
    const k = i + 1
    s.classList.remove('busy')
    if (k <= n && !s.classList.contains('muted')) {
      const fresh = !s.classList.contains('active')
      s.classList.add('active')
      if (k < n || k < 5) s.classList.add('done')
      if (fresh) {
        const l = s.querySelector('.step-l')
        const full = l.dataset.full || ''
        if (instant || reduced()) l.textContent = full
        else { const c = new AbortController(); stripTypers.push(c); typeText(l, full, { cps: 160, signal: c.signal }) }
      }
    } else if (k > n) {
      s.classList.remove('active', 'done', 'pending', 'ok-approved')
    }
  })
  if (busyNext && steps[n] && !steps[n].classList.contains('muted')) steps[n].classList.add('busy')
  if (n >= 5) markGateStep()
  state.stripLit = n
}

export async function animateStrip(to) {
  for (let i = state.stripLit + 1; i <= to; i++) {
    setStripLit(i, { busyNext: i < to })
    await delay(reduced() ? 0 : 520)
  }
}

function markGateStep() {
  const s5 = el('strip').querySelector('.step[data-n="5"]')
  if (!s5) return
  s5.classList.toggle('pending', state.gate === 'pending')
  s5.classList.toggle('ok-approved', state.gate === 'approved')
  s5.classList.toggle('done', state.gate === 'approved' || state.gate === 'rejected')
}

// ---------- KPIs ----------
export function renderKpis() {
  const k = el('kpis')
  k.dataset.state = 'ok'
  const plan = state.plan
  const P = plan?.plan

  if (!state.dataAvailable) {
    k.innerHTML = `<div class="panel-h"><span class="panel-t"><b>Day result</b></span><span class="pill pill-amber"><i></i>Data offline</span></div>
      <div class="kpi-top"><div><div class="kpi-big dash">--</div><div class="kpi-cap">Live plans need the licensed hourly grid data, which is not installed here.</div></div></div>
      ${day.raceHTML()}
      <div class="kpi-note">Nothing on this panel is estimated or filled in. Evidence, Knowledge and Interfaces still work.</div>`
    day.paintRace()
    return
  }
  if (plan && !P) {
    const st = plan.status === 'NOT_MOVABLE' ? 'Not movable' : plan.status === 'UNKNOWN_JOB' ? 'Unknown job' : (plan.status || '')
    k.innerHTML = `<div class="panel-h"><span class="panel-t"><b>${esc(plan.label || plan.job)}</b></span><span class="pill pill-amber"><i></i>${esc(st)}</span></div>
      <div class="explain">${esc(notMovableText(plan))}</div>
      <div class="kpi-note">No plan is drafted, so there is nothing to approve. Fixed jobs stay in their home region.</div>`
    return
  }
  if (!P) {
    k.innerHTML = `<div class="panel-h"><span class="panel-t"><b>Day result</b></span></div>
      <div class="kpi-top"><div><div class="kpi-big dash">--</div><div class="kpi-cap">Pick a job and a day, or ask: "Plan the model training for June 15th".</div></div></div>
      ${day.raceHTML()}`
    day.paintRace()
    return
  }
  const explain = plan.steps?.find((s) => s.key === 'explain')?.lines?.join(' ') || plan.summary || ''
  const pct = P.transfer_budget_mwh ? clamp(P.moved_mwh / P.transfer_budget_mwh, 0, 1) : 0
  const C = 2 * Math.PI * 27
  k.innerHTML = `
    <div class="panel-h"><span class="panel-t"><b>${esc(plan.label || plan.job)}</b>, ${esc(dayLabel(plan.day))}</span><span class="panel-t">logistics ${Math.round((plan.transfer_share ?? 0) * 100)}%</span></div>
    <div class="kpi-top">
      <div class="kpi-main">
        <div class="kpi-big"><span id="kpiSave">0</span><small>%</small></div>
        <div class="kpi-cap">lower emissions than <b>shifting hours only</b>, from also moving work</div>
      </div>
      <div class="kpi-side"><div class="v"><span id="kpiFlat">0</span><small>%</small></div><div class="l">lower than running flat</div></div>
    </div>
    <div class="badge-ill"><b>ILLUSTRATION</b><span>${esc(ILLUSTRATION)}</span></div>
    ${day.raceHTML()}
    <div class="kpi-mid">
      <div class="ring" title="Moved work out of the transfer budget">
        <svg viewBox="0 0 66 66"><circle class="rbg" cx="33" cy="33" r="27" fill="none" stroke-width="6"/>
        <circle class="rfg" id="ringFg" cx="33" cy="33" r="27" fill="none" stroke-width="6" stroke-linecap="round" stroke-dasharray="${C}" stroke-dashoffset="${C}"/></svg>
        <div class="ring-c"><span><span id="ringV">0</span><small>of ${esc(fmt(P.transfer_budget_mwh))} MWh</small></span></div>
      </div>
      <div class="explain clamp4" title="${esc(explain)}"><b>${esc(fmt(P.moved_mwh, 2))} MWh moved</b> of a ${esc(fmt(P.transfer_budget_mwh))} MWh logistics budget (${esc(fmt(P.work_mwh))} MWh of work). ${esc(explain)}</div>
    </div>
`
  animateNumber(el('kpiSave'), P.saving_pct, { format: (n) => fmtFixed(n, 1) })
  animateNumber(el('kpiFlat'), P.saving_vs_flat_pct, { format: (n) => fmtFixed(n, 1) })
  animateNumber(el('ringV'), P.moved_mwh, { format: (n) => fmtFixed(n, 1) })
  requestAnimationFrame(() => { const r = el('ringFg'); if (r) r.style.strokeDashoffset = String(C * (1 - pct)) })
  day.paintRace()
}

// ---------- approval gate ----------
export function showGate({ quiet = false } = {}) {
  if (!state.plan || state.plan.status !== 'PENDING_APPROVAL') return
  state.gate = 'pending'
  renderGate()
  const g = el('gate')
  if (!quiet) { g.classList.remove('slam'); void g.offsetWidth; g.classList.add('slam') }
  markGateStep()
}

export function renderGate(stamp) {
  const g = el('gate')
  const plan = state.plan
  if (state.gate === 'none' || !plan || !plan.approval) { g.hidden = true; g.innerHTML = ''; return }
  g.hidden = false
  const a = plan.approval
  const decided = state.gate === 'approved' || state.gate === 'rejected'
  g.classList.toggle('decided', decided)
  g.innerHTML = `
    <div class="gate-h"><span class="gate-ic"><svg width="15" height="15" viewBox="0 0 20 20"><rect x="4" y="9" width="12" height="8" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M7 9V6.5a3 3 0 0 1 6 0V9" fill="none" stroke="currentColor" stroke-width="1.6"/></svg></span>
      <span class="gate-t">${decided ? 'Decision logged' : 'Sign-off needed'}</span>
      <span class="panel-t" style="margin-left:auto">S&amp;OP gate</span></div>
    <div class="gate-s">From the <b>${esc(a.required_from)}</b>. ${esc(a.reason || '')}</div>
    <div class="gate-btns">
      <button class="btn-approve" id="approveBtn" ${decided ? 'disabled' : ''}>Approve</button>
      <button class="btn-ghost btn-reject" id="rejectBtn" ${decided ? 'disabled' : ''}>Reject</button>
    </div>
    ${decided ? `<div class="gate-exec">executed: false. Logged for the ${esc(a.required_from)}; nothing ran.</div>` : ''}
    ${stamp ? `<div class="stamp ${state.gate === 'approved' ? 'ok' : 'no'}">${state.gate === 'approved' ? 'APPROVED · NOT EXECUTED' : 'REJECTED'}</div>` : ''}`
  g.querySelector('#approveBtn')?.addEventListener('click', () => decide('approve'))
  g.querySelector('#rejectBtn')?.addEventListener('click', () => decide('reject'))
}

export async function decide(decision, { by = 'Marco (presenter)', silent = false } = {}) {
  if (state.gate !== 'pending' || !state.plan) { toast('Nothing is waiting for approval.'); return null }
  const plan = state.plan
  el('approveBtn') && (el('approveBtn').disabled = true)
  el('rejectBtn') && (el('rejectBtn').disabled = true)
  const r = await api('/api/decision', { method: 'POST', body: { job: plan.job, day: plan.day, share: plan.transfer_share ?? state.req.share, decision, by } })
  if (!r.ok) {
    toast(r.error?.message || 'The decision could not be logged.')
    renderGate()
    return null
  }
  state.gate = r.data.status === 'APPROVED_NOT_EXECUTED' ? 'approved' : 'rejected'
  if (Array.isArray(r.data.audit)) state.audit = r.data.audit
  renderGate(true)
  markGateStep()
  renderAudit(true)
  if (!silent && r.data.speech) speak(r.data.speech)
  emit('decision', r.data)
  return r.data
}

export function renderAudit(fresh) {
  const a = el('audit')
  const rows = state.audit || []
  a.innerHTML = `<div class="panel-h"><span class="panel-t"><b>Audit log</b></span><span class="panel-t">in memory, newest first</span></div>
    ${rows.length ? `<div class="audit-list">${rows.map((r, i) => `
      <div class="audit-row" style="${fresh && i === 0 ? '' : 'animation:none'}">
        <span class="d ${r.decision === 'approve' ? 'approve' : 'reject'}">${r.decision === 'approve' ? 'Approved' : 'Rejected'}</span>
        <span class="m">${esc(r.job)}, ${esc(r.day)}, by ${esc(r.by)}</span>
        <span class="x">executed: ${r.executed === true ? 'true' : 'false'}</span>
      </div>`).join('')}</div>`
      : '<div class="audit-empty">No decisions yet. Every approval or rejection is logged here. Nothing is ever executed.</div>'}`
}

// ---------- sweep ----------
export async function loadSweep() {
  const s = el('sweep')
  if (!state.dataAvailable) { renderSweep(); return }
  const my = ++sweepSeq
  if (!state.sweep) setLoading(s, 3)
  const r = await api(`/api/sweep?${qs({ job: state.req.job, day: state.req.day, shares: SHARES.join(',') })}`)
  if (my !== sweepSeq) return
  if (!r.ok) {
    state.sweep = null
    if (state.plan && !state.plan.plan) { renderSweep(); return }
    setError(s, r.error, () => loadSweep(), { title: 'Saving curve unavailable' })
    return
  }
  state.sweep = r.data
  renderSweep(true)
}

export function renderSweep(animate) {
  const s = el('sweep')
  s.dataset.state = 'ok'
  const sw = state.sweep
  const head = `<div class="panel-h"><span class="panel-t"><b>Saving vs logistics capacity</b></span><span class="badge-ill" style="padding:2px 6px"><b>ILLUSTRATION</b><span>one day</span></span></div>`
  if (!state.dataAvailable || !sw || !sw.points?.length || (state.plan && !state.plan.plan) || sw.job !== state.req.job) {
    s.innerHTML = `${head}<div class="audit-empty">${!state.dataAvailable ? 'Needs the licensed grid data.' : state.plan && !state.plan.plan ? 'Not movable, so there is no capacity to buy.' : 'Loading the curve for this job and day.'}</div>`
    return
  }
  const pts = sw.points
  const W = 320; const H = 108; const L = 30; const R = 10; const T = 12; const B = 18
  const maxY = Math.max(1, ...pts.map((p) => p.saving_pct)) * 1.15
  const x = (sh) => L + (sh / 0.5) * (W - L - R)
  const y = (v) => T + (1 - v / maxY) * (H - T - B)
  const line = pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.share).toFixed(1)},${y(p.saving_pct).toFixed(1)}`).join(' ')
  const area = `${line} L${x(pts[pts.length - 1].share).toFixed(1)},${y(0)} L${x(pts[0].share).toFixed(1)},${y(0)} Z`
  const cur = state.req.share
  const curP = pts.find((p) => Math.abs(p.share - cur) < 1e-6)
  s.innerHTML = `${head}
    <svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none" role="img" aria-label="Saving percent by transfer share">
      <defs><linearGradient id="sweepGrad" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="rgba(36,67,214,.16)"/><stop offset="1" stop-color="rgba(36,67,214,0)"/></linearGradient></defs>
      <line class="axis" x1="${L}" y1="${y(0)}" x2="${W - R}" y2="${y(0)}"/>
      <line class="grid-l" x1="${L}" y1="${y(maxY / 1.15)}" x2="${W - R}" y2="${y(maxY / 1.15)}"/>
      <text class="tick" x="${L - 5}" y="${y(maxY / 1.15) + 3}" text-anchor="end">${fmt(maxY / 1.15)}%</text>
      <text class="tick" x="${L - 5}" y="${y(0) + 3}" text-anchor="end">0%</text>
      <path class="area" d="${area}"/>
      <path class="curve" id="sweepCurve" d="${line}"/>
      ${pts.map((p) => `<text class="tick" x="${x(p.share)}" y="${H - 3}" text-anchor="middle">${Math.round(p.share * 100)}%</text>`).join('')}
      ${pts.map((p) => `<circle class="pt${Math.abs(p.share - cur) < 1e-6 ? ' on' : ''}" data-share="${p.share}" cx="${x(p.share)}" cy="${y(p.saving_pct)}" r="${Math.abs(p.share - cur) < 1e-6 ? 5 : 3.5}"><title>${Math.round(p.share * 100)}% capacity: ${fmt(p.saving_pct)}% saving, ${fmt(p.moved_mwh, 2)} MWh moved</title></circle>`).join('')}
      ${curP ? `<text class="lbl" x="${x(curP.share)}" y="${y(curP.saving_pct) - 9}" text-anchor="middle">${fmt(curP.saving_pct)}%</text>` : ''}
    </svg>
    <div class="sweep-cap">More logistics capacity, more saving, with diminishing returns. Click a point to re-plan.</div>`
  if (animate && !reduced()) {
    const c = s.querySelector('#sweepCurve')
    try {
      const len = c.getTotalLength()
      c.style.strokeDasharray = `${len}`; c.style.strokeDashoffset = `${len}`
      c.getBoundingClientRect()
      c.style.transition = 'stroke-dashoffset .9s cubic-bezier(.23,1,.32,1)'
      c.style.strokeDashoffset = '0'
    } catch { /* svg not laid out */ }
  }
  s.querySelectorAll('.pt').forEach((p) => p.addEventListener('click', () => {
    state.req.share = +p.dataset.share
    syncControls()
    loadPlan({ quiet: true })
  }))
}
