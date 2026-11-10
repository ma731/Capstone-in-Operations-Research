// Knowledge, Evidence, Monitor and Interfaces views.

import { state, emit } from './state.js'
import { api } from './api.js'
import { speak } from './voice.js'
import { esc, h, delay, fmt, fmtFixed, animateNumber, setLoading, setError, reduced, clamp, easeInOut, jsonHTML, monthLabel, toast } from './util.js'

const el = (id) => document.getElementById(id)
const plain = (t) => String(t || '').replace(/CVaR_?\{?0?\.95\}?/g, 'CVaR95 (worst 5% of days)')
const inflight = {}

// load once, share the promise
async function fetchOnce(key, path, opts) {
  if (state[key]) return { ok: true, data: state[key] }
  if (inflight[key]) return inflight[key]
  inflight[key] = api(path, opts).then((r) => { if (r.ok) state[key] = r.data; delete inflight[key]; return r })
  return inflight[key]
}

export function prefetch() {
  ensureFindings(); ensureGraph(); ensureInterfaces()
  if (state.dataAvailable) ensureDrift()
}

export function onViewShown(v) {
  if (v === 'knowledge') ensureGraph()
  if (v === 'evidence') ensureFindings().then(() => animateEvidence())
  if (v === 'monitor') ensureDrift().then(() => animateDrift())
  if (v === 'interfaces') ensureInterfaces()
}

/* =================== KNOWLEDGE =================== */
let kg = { reasoned: false, sel: null, nodes: new Map(), edges: [], drawn: false }

export async function ensureGraph() {
  const g = el('kgraph')
  if (state.graph) { if (!kg.drawn) drawGraph(); return state.graph }
  setLoading(g, 6); setLoading(el('kside'), 4)
  const r = await fetchOnce('graph', '/api/graph')
  if (!r.ok) {
    setError(g, r.error, () => ensureGraph(), { title: 'Ontology graph unavailable' })
    el('kside').innerHTML = ''
    return null
  }
  drawGraph()
  return state.graph
}

// layered left to right: rules, jobs, data centres, grid regions, portfolios
const COLS = { class: 92, job: 270, datacenter: 470, region: 680, portfolio: 892 }
const PATH_PREDS = new Set(['runsAt', 'locatedIn', 'memberOf', 'inPortfolio', 'hasRegion', 'homeRegion', 'reachableRegion'])

function drawGraph() {
  const data = state.graph
  const g = el('kgraph')
  g.dataset.state = 'ok'
  const W = 1000; const H = 560
  const byKind = {}
  for (const n of data.nodes || []) (byKind[n.kind] ||= []).push(n)
  const pos = new Map()
  const top = 64; const bottom = 470
  const place = (kind, list, x) => {
    list.forEach((n, i) => {
      const span = Math.min(bottom - top, Math.max(60, (list.length - 1) * 44))
      const y0 = (top + bottom) / 2 - span / 2
      pos.set(n.id, { x, y: list.length === 1 ? (top + bottom) / 2 : y0 + (span * i) / (list.length - 1), kind })
    })
  }
  const sortLbl = (a, b) => String(a.label || a.id).localeCompare(String(b.label || b.id))
  // regions ordered west to east so lines barely cross
  const zoneLon = new Map((state.meta?.zones || []).map((z) => [z.id, z.lon]))
  const regions = (byKind.region || []).slice().sort((a, b) => (zoneLon.get(a.zone) ?? 0) - (zoneLon.get(b.zone) ?? 0))
  place('class', (byKind.class || []).slice().sort(sortLbl), COLS.class)
  place('job', (byKind.job || []).slice().sort(sortLbl), COLS.job)
  place('region', regions, COLS.region)
  // data centres and portfolios sit level with the regions they connect to
  const edges = data.edges || []
  const avgY = (id, preds) => {
    const ys = edges.filter((e) => preds.includes(e.predicate) && (e.source === id || e.target === id))
      .map((e) => pos.get(e.source === id ? e.target : e.source)).filter((p) => p && p.kind === 'region').map((p) => p.y)
    return ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : null
  }
  const spread = (list, kind, preds) => {
    const items = list.map((n, i) => ({ n, y: avgY(n.id, preds) ?? top + ((bottom - top) * (i + 0.5)) / list.length })).sort((a, b) => a.y - b.y)
    for (let i = 1; i < items.length; i++) items[i].y = Math.max(items[i].y, items[i - 1].y + 44)
    const over = items.length ? items[items.length - 1].y - bottom : 0
    if (over > 0) items.forEach((it) => { it.y -= over })
    items.forEach((it) => pos.set(it.n.id, { x: COLS[kind], y: Math.max(top, it.y), kind }))
  }
  spread(byKind.datacenter || [], 'datacenter', ['locatedIn'])
  spread(byKind.portfolio || [], 'portfolio', ['memberOf', 'inPortfolio', 'hasRegion'])
  // jobs level with their data centre
  ;(byKind.job || []).forEach((n) => {
    const e = edges.find((x) => x.source === n.id && x.predicate === 'runsAt')
    const p = e && pos.get(e.target)
    if (p) pos.set(n.id, { ...pos.get(n.id), y: p.y })
  })
  const jobs = (byKind.job || []).map((n) => pos.get(n.id)).sort((a, b) => a.y - b.y)
  for (let i = 1; i < jobs.length; i++) jobs[i].y = Math.max(jobs[i].y, jobs[i - 1].y + 40)
  const metrics = byKind.metric || []
  metrics.forEach((n, i) => pos.set(n.id, { x: W / 2 + (i - (metrics.length - 1) / 2) * 180, y: 528, kind: 'metric' }))
  ;(data.nodes || []).forEach((n, i) => { if (!pos.has(n.id)) pos.set(n.id, { x: 40 + (i % 20) * 46, y: 545, kind: n.kind }) })

  const path = (a, b) => {
    if (Math.abs(a.x - b.x) < 5) {
      const bend = 38 + Math.abs(a.y - b.y) * 0.18
      return `M${a.x},${a.y} C${a.x - bend},${a.y} ${b.x - bend},${b.y} ${b.x},${b.y}`
    }
    const mx = (a.x + b.x) / 2
    return `M${a.x},${a.y} C${mx},${a.y} ${mx},${b.y} ${b.x},${b.y}`
  }

  // only draw links a reader needs; class links are drawn for jobs and between classes
  const shown = (e, a, b) => {
    if (a.kind === 'metric' || b.kind === 'metric') return false
    if (e.predicate === 'type') return a.kind === 'job' || b.kind === 'job'
    return true
  }
  const edgesSvg = edges.map((e, i) => {
    const a = pos.get(e.source); const b = pos.get(e.target)
    if (!a || !b || !shown(e, a, b)) return ''
    const faint = e.predicate === 'reachableRegion' || e.predicate === 'homeRegion' || a.kind === 'class' || b.kind === 'class'
    const cls = `kg-edge${e.inferred ? ' inf' : ''}${faint ? ' faint' : ''}${e.predicate === 'hasRegion' ? ' hasreg' : ''}`
    return `<path class="${cls}" data-i="${i}" d="${path(a, b)}"><title>${esc(e.source)} ${esc(e.predicate)} ${esc(e.target)} (${esc(e.rule)})</title></path>`
  }).join('')

  const nodesSvg = (data.nodes || []).map((n) => {
    const p = pos.get(n.id)
    const label = esc(n.label || n.id)
    if (n.kind === 'class') {
      const w = Math.max(60, String(n.label || n.id).length * 6.3 + 18)
      return `<g class="kg-node k-class" data-id="${esc(n.id)}" transform="translate(${p.x},${p.y})"><rect x="${-w / 2}" y="-10" width="${w}" height="20" rx="10"/><text text-anchor="middle" dy="3.5">${label}</text><title>${label} (rule class)</title></g>`
    }
    const right = n.kind === 'region' || n.kind === 'job' || n.kind === 'datacenter'
    const anchor = n.kind === 'metric' ? 'middle' : n.kind === 'portfolio' ? 'middle' : right ? 'start' : 'end'
    const tx = n.kind === 'metric' || n.kind === 'portfolio' ? 0 : right ? 11 : -11
    const ty = n.kind === 'metric' || n.kind === 'portfolio' ? 22 : 4
    return `<g class="kg-node k-${esc(n.kind)}" data-id="${esc(n.id)}" transform="translate(${p.x},${p.y})"><circle r="${n.kind === 'job' ? 8 : n.kind === 'portfolio' ? 8 : 6}"/><text x="${tx}" y="${ty}" text-anchor="${anchor}">${label}</text><title>${label} (${esc(n.kind)})</title></g>`
  }).join('')

  const colHead = [['Rules', COLS.class], ['Jobs', COLS.job], ['Data centres', COLS.datacenter], ['Grid regions', COLS.region], ['Portfolios', COLS.portfolio]]
    .map(([t, x]) => `<text class="kg-col" x="${x}" y="24" text-anchor="middle">${t}</text>`).join('')

  g.innerHTML = `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid meet" role="img" aria-label="Ontology graph, layered from rules to portfolios">
    ${Object.values(COLS).map((x) => `<line x1="${x}" y1="36" x2="${x}" y2="${bottom + 14}" stroke="rgba(255,255,255,.035)"/>`).join('')}
    ${metrics.length ? `<rect class="kg-band" x="10" y="506" width="${W - 20}" height="44" rx="12"/><text class="kg-col" x="22" y="500">Metrics</text>` : ''}
    ${colHead}
    <g id="kgEdges">${edgesSvg}</g><g id="kgNodes">${nodesSvg}</g></svg>`
  kg.drawn = true
  kg.nodes = new Map((data.nodes || []).map((n) => [n.id, n]))
  kg.edges = edges
  if (kg.reasoned) g.querySelectorAll('.kg-edge.inf').forEach((p) => p.classList.add('drawn', 'dashed'))
  g.querySelectorAll('.kg-node').forEach((n) => n.addEventListener('click', () => selectNode(n.dataset.id)))
  g.querySelector('svg').addEventListener('click', (e) => { if (e.target.tagName === 'svg') selectNode(null) })
  renderKSide()
  if (kg.sel) selectNode(kg.sel)
}

function renderKSide(why) {
  const c = state.graph?.counts || {}
  const side = el('kside')
  side.dataset.state = 'ok'
  const sel = kg.sel ? kg.nodes.get(kg.sel) : null
  const facts = sel ? kg.edges.filter((e) => (e.source === sel.id || (e.target === sel.id && e.predicate === 'hasRegion')) && (kg.reasoned || !e.inferred)) : []
  side.innerHTML = `
    <div class="kcounts">
      <div class="kc big"><div class="v"><span id="kTriples">${kg.reasoned ? c.reasoned_triples : c.asserted_triples}</span> <span class="from">${kg.reasoned ? `from ${c.asserted_triples}` : 'asserted'}</span></div><div class="l">${kg.reasoned ? 'facts after reasoning (triples)' : 'facts written by hand (triples)'}</div></div>
      <div class="kc"><div class="v">${fmt(c.nodes, 0)}</div><div class="l">things in the model</div></div>
      <div class="kc"><div class="v"><span id="kInf">${kg.reasoned ? c.edges_inferred : 0}</span></div><div class="l">links the reasoner adds</div></div>
    </div>
    <button class="btn-ghost btn-violet" id="reasonBtn">${kg.reasoned ? 'Replay reasoner' : 'Run reasoner'}</button>
    <div class="klegend">
      <span><i></i>asserted fact</span><span><i class="inf"></i>inferred by the OWL RL reasoner</span><span><i class="hot"></i>selected job's chain</span>
    </div>
    ${why ? `<div class="kwhy"><div class="ksel-k">Agent answer</div>${why.map((w) => `<div>${esc(w)}</div>`).join('')}</div>` : ''}
    ${sel ? `<div><div class="ksel-k">${esc(sel.kind)}</div><div class="ksel-h">${esc(sel.label || sel.id)}</div></div>
      <div class="kfacts">${facts.length ? facts.map((e, i) => `<div class="kfact${e.inferred ? ' inf' : ''}" style="animation-delay:${i * 30}ms"><span><span class="p">${esc(e.predicate)}</span> ${esc(kg.nodes.get(e.source === sel.id ? e.target : e.source)?.label || (e.source === sel.id ? e.target : e.source))}</span><span class="r">${esc(e.inferred ? e.rule : 'asserted')}</span></div>`).join('') : '<div class="khint">No facts to show yet. Run the reasoner to add inferred ones.</div>'}</div>`
      : '<div class="khint">Click a job to light up the chain of facts that decides where it may run.</div>'}`
  side.querySelector('#reasonBtn').addEventListener('click', () => runReasoner())
}

export function selectNode(id, why) {
  kg.sel = id
  const g = el('kgraph')
  const svg = g.querySelector('svg')
  if (!svg) return
  svg.querySelectorAll('.hot,.sel').forEach((n) => n.classList.remove('hot', 'sel'))
  g.classList.toggle('focused', !!id)
  if (id) {
    const hotNodes = new Set([id]); const hotEdges = new Set()
    let frontier = [id]
    for (let depth = 0; depth < 3; depth++) {
      const next = []
      kg.edges.forEach((e, i) => {
        if (!PATH_PREDS.has(e.predicate)) return
        if (e.inferred && !kg.reasoned) return
        if (frontier.includes(e.source)) {
          // hasRegion from a portfolio only counts toward regions the job can reach
          hotEdges.add(i)
          if (!hotNodes.has(e.target)) { hotNodes.add(e.target); next.push(e.target) }
        }
      })
      frontier = next
    }
    svg.querySelectorAll('.kg-edge').forEach((p) => { if (hotEdges.has(+p.dataset.i)) p.classList.add('hot') })
    svg.querySelectorAll('.kg-node').forEach((n) => { if (hotNodes.has(n.dataset.id)) n.classList.add('hot') })
    svg.querySelector(`.kg-node[data-id="${CSS.escape(id)}"]`)?.classList.add('sel')
  }
  renderKSide(why)
}

export async function runReasoner() {
  if (!state.graph) { const ok = await ensureGraph(); if (!ok) return }
  const g = el('kgraph')
  const c = state.graph.counts || {}
  const inf = [...g.querySelectorAll('.kg-edge.inf')]
  kg.reasoned = false
  inf.forEach((p) => { p.classList.remove('drawn', 'dashed'); p.style.transition = 'none'; p.style.strokeDasharray = ''; p.style.strokeDashoffset = '' })
  renderKSide()
  const tri = el('kTriples'); const ie = el('kInf')
  if (tri) tri._v = c.asserted_triples
  const D = reduced() ? 0 : 2400
  kg.reasoned = true
  if (tri) animateNumber(tri, c.reasoned_triples, { format: (n) => fmtFixed(n, 0), duration: D || 1 })
  if (ie) animateNumber(ie, c.edges_inferred, { format: (n) => fmtFixed(n, 0), duration: D || 1 })
  const from = tri?.nextElementSibling
  if (from) from.textContent = `from ${c.asserted_triples}`
  const btn = el('reasonBtn'); if (btn) btn.textContent = 'Replay reasoner'
  inf.forEach((p, i) => {
    let len = 200
    try { len = p.getTotalLength() } catch { /* not laid out */ }
    p.style.strokeDasharray = `${len}`
    p.style.strokeDashoffset = `${len}`
    p.getBoundingClientRect()
    p.style.transition = `stroke-dashoffset .9s cubic-bezier(.23,1,.32,1) ${D ? (i / inf.length) * 1500 : 0}ms, opacity .3s ${D ? (i / inf.length) * 1500 : 0}ms`
    p.classList.add('drawn')
    p.style.strokeDashoffset = '0'
  })
  await delay(D + 300)
  inf.forEach((p) => { p.style.transition = ''; p.style.strokeDasharray = ''; p.style.strokeDashoffset = ''; p.classList.add('dashed') })
  renderKSide()
  if (kg.sel) selectNode(kg.sel)
}

/* =================== EVIDENCE =================== */
export async function ensureFindings() {
  if (state.findings) { if (!el('rq-cards').dataset.ready) renderEvidence(); return state.findings }
  setLoading(el('rq-cards'), 3); setLoading(el('ladder'), 4); setLoading(el('rq3'), 4)
  const r = await fetchOnce('findings', '/api/findings')
  if (!r.ok) {
    const retry = () => ensureFindings()
    setError(el('rq-cards'), r.error, retry, { title: 'Thesis findings unavailable' })
    el('ladder').innerHTML = ''; el('rq3').innerHTML = ''
    return null
  }
  renderEvidence()
  return state.findings
}

function renderEvidence() {
  const f = state.findings
  const F = f.figures || {}; const T = f.findings || {}
  const lad = f.ladder || []
  const verdict = (i) => lad[i]?.verdict || ''
  const cards = el('rq-cards')
  cards.dataset.ready = '1'
  cards.dataset.state = 'ok'
  const thesis = '<span class="badge-thesis"><b>THESIS</b>out-of-sample CVaR95</span>'
  cards.innerHTML = `
    <div class="panel rq-card ${verdict(0)}">
      <div class="rq-k"><span class="rq-id">RQ1</span><span class="verdict ${verdict(0)}">${esc(verdict(0))}</span></div>
      <div class="rq-q">Does moving work between regions pay?</div>
      <div class="rq-v">${fmt(F.RQ1?.low_pct)} to ${fmt(F.RQ1?.high_pct)}<small>% lower</small></div>
      <div class="rq-t">${esc(plain(T.RQ1))}</div>${thesis}
    </div>
    <div class="panel rq-card ${verdict(1)}">
      <div class="rq-k"><span class="rq-id">RQ2</span><span class="verdict ${verdict(1)}">${esc(verdict(1))}</span></div>
      <div class="rq-q">Does modelling how regions move together pay?</div>
      <div class="rq-v">under ${fmt(F.RQ2?.max_gain_pct)}<small>% extra</small></div>
      <div class="rq-t">${esc(plain(T.RQ2))}</div>${thesis}
    </div>
    <div class="panel rq-card ${verdict(2)}">
      <div class="rq-k"><span class="rq-id">RQ3</span><span class="verdict ${verdict(2)}">${esc(verdict(2))}</span></div>
      <div class="rq-q">Does robust optimisation pay?</div>
      <div class="rq-v">${fmt(F.RQ3?.breakeven_severity_x)}x<small>shock to break even</small></div>
      <div class="rq-t">${esc(plain(T.RQ3))}</div>${thesis}
    </div>`

  // ladder: bar length follows the published figure where one exists
  const hi = F.RQ1?.high_pct || 1
  const widths = lad.map((l) => (l.verdict === 'pays' ? 100 : l.verdict === 'marginal' ? Math.max(6, ((F.RQ2?.max_gain_pct || 0) / hi) * 100) : 58))
  const ld = el('ladder')
  ld.dataset.state = 'ok'
  ld.innerHTML = `
    <div class="lad-h"><span class="lad-title">The price of sophistication</span><span class="badge-thesis"><b>THESIS</b>worst 5% of days</span></div>
    <div class="lad-axis"><span>Layer, simplest first</span><span>Value on the worst days</span></div>
    <div class="lad-rows">${lad.map((l, i) => `
      <div class="lad-row ${esc(l.verdict)}">
        <span class="lad-step">${i + 1}</span>
        <div class="lad-main">
          <div class="lad-top"><b>${esc(plain(l.layer))}</b><span class="verdict ${esc(l.verdict)}">${esc(l.verdict)}</span></div>
          <div class="lad-track"><div class="lad-bar" data-w="${widths[i]}">${esc(plain(l.value_label))}</div></div>
        </div>
      </div>`).join('')}</div>
    ${T.recommendation ? `<div class="lad-rec">${esc(plain(T.recommendation))}</div>` : ''}`

  renderGauge(F.RQ3 || {}, T.RQ3)
  el('evSource').innerHTML = `<span class="badge-thesis"><b>SOURCE</b>${esc(plain(f.source || 'Thesis results'))}</span><span>These are thesis results over many days, not the one-day illustration on the Command view.</span>`
}

const G = { cx: 200, cy: 182, r: 140 }
const ang = (v) => Math.PI - ((clamp(v, 1, 4) - 1) / 3) * Math.PI
const pt = (v, r = G.r) => [G.cx + Math.cos(ang(v)) * r, G.cy - Math.sin(ang(v)) * r]
function arc(v0, v1, r) {
  const [x0, y0] = pt(v0, r); const [x1, y1] = pt(v1, r)
  return `M${x0.toFixed(1)},${y0.toFixed(1)} A${r},${r} 0 0 1 ${x1.toFixed(1)},${y1.toFixed(1)}`
}

function renderGauge(F3, text) {
  const be = F3.breakeven_severity_x
  const ob = F3.observed_severity_x || []
  const g = el('rq3')
  g.dataset.state = 'ok'
  const ticks = [1, 1.5, 2, 2.5, 3, 3.5, 4]
  g.innerHTML = `
    <div class="lad-h"><span class="lad-title">When does robust optimisation pay?</span><span class="badge-thesis"><b>THESIS</b>RQ3</span></div>
    <svg viewBox="0 0 400 236" role="img" aria-label="Shock severity gauge">
      <path d="${arc(1, 4, G.r)}" fill="none" stroke="#1d2226" stroke-width="22"/>
      ${be ? `<path d="${arc(be, 4, G.r)}" fill="none" stroke="rgba(227,179,65,.22)" stroke-width="22"/>` : ''}
      ${ob.length === 2 ? `<path d="${arc(ob[0], ob[1], G.r)}" fill="none" stroke="#45a8c4" stroke-width="22"/>` : ''}
      ${ticks.map((t) => { const [a, b] = pt(t, G.r + 15); const [c, d] = pt(t, G.r + 21); const [lx, ly] = pt(t, G.r + 33); return `<line x1="${a}" y1="${b}" x2="${c}" y2="${d}" stroke="#4a5358"/>${Number.isInteger(t) ? `<text class="g-tick" x="${lx}" y="${ly + 4}" text-anchor="middle">${t}x</text>` : ''}` }).join('')}
      ${be ? (() => { const [a, b] = pt(be, G.r - 16); const [c, d] = pt(be, G.r + 14); return `<line x1="${a}" y1="${b}" x2="${c}" y2="${d}" stroke="#e3b341" stroke-width="2.5"/>` })() : ''}
      <g id="needle"><line x1="${G.cx}" y1="${G.cy}" x2="${G.cx - G.r + 26}" y2="${G.cy}" stroke="#e9ecec" stroke-width="2" stroke-linecap="round"/><circle cx="${G.cx}" cy="${G.cy}" r="5" fill="#e9ecec"/></g>
      <text class="g-lbl data" x="${G.cx}" y="${G.cy + 30}" text-anchor="middle">Observed shocks: ${ob.length === 2 ? `${fmt(ob[0], 2)} to ${fmt(ob[1], 2)}x normal` : 'n/a'}</text>
      <text class="g-lbl amber" x="${G.cx}" y="${G.cy + 48}" text-anchor="middle">Break-even: about ${fmt(be)}x normal</text>
    </svg>
    <div class="rq3-cap">${esc(plain(text))}</div>`
  setNeedle(1)
}

function setNeedle(v) {
  const n = el('needle')
  if (!n) return
  const deg = ((clamp(v, 1, 4) - 1) / 3) * 180
  n.setAttribute('transform', `rotate(${deg} ${G.cx} ${G.cy})`)
}

export async function sweepNeedle() {
  const be = state.findings?.figures?.RQ3?.breakeven_severity_x
  if (!be) return
  if (reduced()) { setNeedle(be); return }
  const D = 1600; const t0 = performance.now()
  await new Promise((res) => {
    const tick = (now) => {
      const t = clamp((now - t0) / D, 0, 1)
      setNeedle(1 + (be - 1) * easeInOut(t))
      if (t < 1) requestAnimationFrame(tick); else res()
    }
    requestAnimationFrame(tick)
  })
}

export async function animateEvidence() {
  if (!state.findings) return
  const cards = [...el('rq-cards').querySelectorAll('.rq-card')]
  cards.forEach((c) => c.classList.remove('in'))
  el('ladder').querySelectorAll('.lad-bar').forEach((b) => { b.style.transition = 'none'; b.style.width = '0' })
  setNeedle(1)
  await delay(30)
  cards.forEach((c, i) => setTimeout(() => c.classList.add('in'), reduced() ? 0 : 120 * i))
  await growLadder()
  sweepNeedle()
}

export async function growLadder() {
  const bars = [...el('ladder').querySelectorAll('.lad-bar')]
  bars.forEach((b) => { b.style.transition = 'none'; b.style.width = '0' })
  el('ladder').getBoundingClientRect()
  bars.forEach((b, i) => {
    b.style.transition = `width 1.2s cubic-bezier(.23,1,.32,1) ${reduced() ? 0 : 250 * i}ms`
    b.style.width = `${b.dataset.w}%`
  })
  await delay(reduced() ? 0 : 1300)
}

/* =================== MONITOR =================== */
export async function ensureDrift() {
  const d = el('drift')
  if (state.drift) { if (!d.dataset.ready) renderDrift(); return state.drift }
  if (!state.dataAvailable) {
    d.dataset.state = 'error'
    d.innerHTML = `<div class="ps-error"><div class="err-t">Data offline</div><div class="err-m">${esc(state.meta?.lines?.data_offline?.caption || 'The drift monitor needs the licensed grid data, which is not installed on this machine.')}</div></div>`
    return null
  }
  setLoading(d, 8)
  const r = await fetchOnce('drift', '/api/drift?portfolio=all')
  if (!r.ok) { setError(d, r.error, () => ensureDrift(), { title: 'Drift report unavailable' }); return null }
  renderDrift()
  return state.drift
}

const ratioColor = (x) => {
  const stops = [[0.6, [52, 92, 110]], [1.0, [69, 168, 196]], [1.25, [227, 179, 65]], [1.5, [224, 90, 71]]]
  if (x <= stops[0][0]) return `rgb(${stops[0][1]})`
  for (let i = 1; i < stops.length; i++) {
    if (x <= stops[i][0]) {
      const [a, ca] = stops[i - 1]; const [b, cb] = stops[i]; const t = (x - a) / (b - a)
      return `rgb(${ca.map((c, k) => Math.round(c + (cb[k] - c) * t)).join(',')})`
    }
  }
  return 'rgb(224,90,71)'
}

function renderDrift() {
  const D = state.drift
  const d = el('drift')
  d.dataset.ready = '1'
  d.dataset.state = 'ok'
  const months = []
  for (const p of Object.values(D.portfolios || {})) for (const z of Object.values(p.zones || {})) for (const m of z.months || []) if (!months.includes(m.month)) months.push(m.month)
  months.sort()
  const cl = D.closest || {}
  const groups = Object.entries(D.portfolios || {}).map(([pid, p]) => `
    <div class="dgroup">
      <div class="dg-h"><span class="dg-t">${esc(p.label || pid)}</span><span class="dg-a">${esc(p.action || '')}</span></div>
      <div class="dgrid" style="--cols:${months.length}">
        <span></span>${months.map((m) => `<span class="dhead">${esc(monthLabel(m))}</span>`).join('')}
        ${Object.entries(p.zones || {}).map(([zid, z]) => `<span class="dzone" title="${esc(zid)}">${esc(z.name || zid)}</span>${months.map((m, ci) => {
          const c = (z.months || []).find((x) => x.month === m)
          if (!c) return '<span></span>'
          const isClosest = cl.portfolio === pid && cl.zone === zid && cl.month === m
          return `<span class="dcell${c.baseline ? ' base' : ''}${c.drift ? ' alert' : ''}${isClosest ? ' closest' : ''}" data-c="${ci}" style="background:${ratioColor(c.ratio)}" title="${esc(z.name || zid)}, ${esc(m)}: forecast error ${fmt(c.mae)} g/kWh, ${fmtFixed(c.ratio, 2)}x baseline${c.baseline ? ' (baseline month)' : ''}">${fmtFixed(c.ratio, 2)}</span>`
        }).join('')}`).join('')}
      </div>
    </div>`).join('')
  d.innerHTML = `
    <div class="drift-top">
      <div class="drift-sum">${esc(D.speech?.caption || '')}${cl.zone ? ` Closest: <b>${esc(cl.zone_name || cl.zone)}, ${esc(monthLabel(cl.month))}, ${fmtFixed(cl.ratio, 2)}x</b>.` : ''}</div>
      <div class="drift-legend">
        <span>error vs baseline</span><span>0.6x</span><div class="dl-bar"></div><span style="color:var(--red)">${fmt(D.threshold)}x alarm</span>
        <div class="dl-hatch"></div><span>baseline months</span><div class="dl-ring"></div><span>closest to alarm</span>
      </div>
    </div>
    <div class="drift-body">${groups}</div>
    <div class="drift-foot">${esc(D.period || '')}. Monthly forecast error (MAE) divided by the first ${fmt(D.baseline_months, 0)} months' error. ${fmt(D.alerts_total, 0)} alerts.</div>`
}

export async function animateDrift() {
  const cells = [...el('drift').querySelectorAll('.dcell')]
  cells.forEach((c) => c.classList.remove('in'))
  el('drift').getBoundingClientRect()
  if (reduced()) { cells.forEach((c) => c.classList.add('in')); return }
  cells.forEach((c) => { c.style.transitionDelay = `${(+c.dataset.c) * 70 + Math.random() * 60}ms`; c.classList.add('in') })
  await delay(1100)
  el('drift').querySelector('.dcell.closest')?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
}

/* =================== INTERFACES =================== */
export async function ensureInterfaces() {
  if (state.interfaces) { if (!el('a2a').dataset.ready) renderInterfaces(); return state.interfaces }
  setLoading(el('a2a'), 7); setLoading(el('mcp'), 4)
  renderEvalsShell()
  const r = await fetchOnce('interfaces', '/api/interfaces')
  if (!r.ok) {
    setError(el('a2a'), r.error, () => ensureInterfaces(), { title: 'Agent card unavailable' })
    setError(el('mcp'), r.error, () => ensureInterfaces(), { title: 'MCP listing unavailable' })
    return null
  }
  renderInterfaces()
  return state.interfaces
}

function renderInterfaces() {
  const I = state.interfaces
  const a = el('a2a')
  a.dataset.ready = '1'
  a.dataset.state = 'ok'
  const M = I.mcp || {}
  const tools = M.tools || []
  const ro = tools.filter((t) => t.read_only).length
  const skills = (I.agent_card?.skills || []).map((s) => s.name || s.id).filter(Boolean)
  a.innerHTML = `
    <div class="panel-h"><span class="panel-t"><b>Who can call Gridshift</b></span><span class="panel-t">A2A ${esc(I.a2a?.protocol_version || '')}, MCP ${esc(M.transport || '')}</span></div>
    <div class="if-cards">
      <div class="if-card"><span class="how">Voice and this console</span><span class="who">People</span><span class="what">Ask in plain English. Every answer is spoken, captioned and shown on screen.</span></div>
      <div class="if-card"><span class="how">A2A: whole tasks</span><span class="who">Other AI agents</span><span class="what">Send a task, get a finished answer back.${skills.length ? ` Skills: ${esc(skills.join(', '))}.` : ''}</span></div>
      <div class="if-card"><span class="how">MCP: single tools</span><span class="who">AI tools and IDEs</span><span class="what">${tools.length} tools and ${(M.resources || []).length} resources; ${ro} of ${tools.length} tools are read only.</span></div>
    </div>
    <div class="if-rules">
      <div class="if-rule if-ro"><span class="dot"></span><div><b>Reading is safe</b>Looking up jobs, forecasts, findings and the ontology changes nothing.</div></div>
      <div class="if-rule if-dr"><span class="dot"></span><div><b>Moves are drafts</b>A cross-region move comes back as a draft for the operations lead. Nothing executes.</div></div>
    </div>
    <div class="panel-h" style="margin:4px 0 0"><span class="panel-t"><b>Try it</b> as another agent would</span><span class="panel-t">${esc(I.a2a?.endpoint || '/a2a')}</span></div>
    <form class="a2a-form" id="a2aForm"><input id="a2aIn" value="Where can the nightly ETL move?" aria-label="Task for the agent"><button class="btn-primary" type="submit">Send task</button></form>
    <div class="wire"><span class="wire-node" id="wClient">Client agent</span><div class="wire-line"><span class="packet" id="packet"></span></div><span class="wire-node" id="wAgent">Gridshift</span></div>
    <div class="a2a-answer" id="a2aAns" hidden></div>
    <details class="raw" id="a2aIO" hidden><summary>JSON-RPC request and response</summary><div class="a2a-io"><div><div class="io-lab" style="padding:8px 12px 0">Request</div><pre class="json" id="a2aReq"></pre></div><div><div class="io-lab" style="padding:8px 12px 0">Response</div><pre class="json" id="a2aRes"></pre></div></div></details>
    <details class="raw" id="cardDetails"><summary>Agent card JSON ${esc(I.a2a?.card_url || '')}</summary><pre class="json" id="cardJson"></pre></details>`
  el('cardDetails').addEventListener('toggle', (e) => { if (e.target.open && !el('cardJson').textContent) typeJSON(el('cardJson'), I.agent_card || {}) })
  el('a2aForm').addEventListener('submit', (e) => { e.preventDefault(); sendA2A(el('a2aIn').value) })

  const m = el('mcp')
  m.dataset.state = 'ok'
  m.innerHTML = `
    <div class="panel-h"><span class="panel-t"><b>MCP server</b> ${esc(M.server || '')}</span><span class="panel-t">${esc(M.transport || '')}</span></div>
    <div class="khint"><code>${esc(M.run || '')}</code></div>
    ${M.error ? `<div class="khint" style="color:var(--amber)">${esc(M.error)}</div>` : ''}
    <div class="mcp-sub">Tools</div>
    <div class="mcp-list">${tools.map((t, i) => `<div class="mcp-item" style="animation-delay:${i * 40}ms"><span class="ic">fn</span><div><div class="nm">${esc(t.name)}</div><div class="ds" title="${esc(t.description)}">${esc(t.description)}</div></div><span class="ro${t.read_only ? '' : ' w'}">${t.read_only ? 'READ ONLY' : t.destructive ? 'DESTRUCTIVE' : 'DRAFT ONLY'}</span></div>`).join('') || '<div class="khint">No tools listed.</div>'}</div>
    <div class="mcp-sub">Resources</div>
    <div class="mcp-list">${(M.resources || []).map((r, i) => `<div class="mcp-item" style="animation-delay:${i * 40}ms"><span class="ic">res</span><div><div class="nm">${esc(r.uri)}</div><div class="ds" title="${esc(r.description)}">${esc(r.description)}</div></div><span class="ro">${esc(r.mime_type || '')}</span></div>`).join('') || '<div class="khint">No resources listed.</div>'}</div>`
}

function typeJSON(pre, obj) {
  const lines = jsonHTML(obj).split('\n')
  pre.innerHTML = ''
  if (reduced()) { pre.innerHTML = lines.join('\n'); return }
  let i = 0
  const iv = setInterval(() => {
    pre.insertAdjacentHTML('beforeend', lines.slice(i, i + 3).join('\n') + (i + 3 < lines.length ? '\n' : ''))
    i += 3
    if (i >= lines.length) clearInterval(iv)
  }, 16)
}

async function movePacket(back) {
  const p = el('packet')
  if (!p) return
  p.classList.toggle('back', !!back)
  if (reduced()) return
  const anim = p.animate([{ left: back ? '100%' : '0%', opacity: 1 }, { left: back ? '0%' : '100%', opacity: 1 }], { duration: 600, easing: 'cubic-bezier(.77,0,.175,1)' })
  await anim.finished.catch(() => {})
  p.style.opacity = '0'
}

function taskText(res) {
  const t = res && res.result
  if (!t) return { state: 'error', text: res?.error?.message || 'No result.' }
  const parts = [...(t.status?.message?.parts || []), ...((t.artifacts || [])[0]?.parts || [])]
  const text = parts.find((p) => p.kind === 'text')?.text || ''
  return { state: t.status?.state || t.kind || 'done', text }
}

export async function sendA2A(text) {
  if (!text || !text.trim()) return
  const req = { jsonrpc: '2.0', id: Math.floor(Math.random() * 1e6), method: 'message/send', params: { message: { kind: 'message', role: 'user', messageId: crypto.randomUUID?.() || String(Date.now()), parts: [{ kind: 'text', text: text.trim() }] } } }
  el('wAgent')?.classList.remove('hot')
  const ans = el('a2aAns'); ans.hidden = false
  ans.innerHTML = '<div class="st">sending task</div>Waiting for the agent.'
  el('a2aIO').hidden = false
  el('a2aReq').innerHTML = jsonHTML(req)
  el('a2aRes').innerHTML = ''
  const [r] = await Promise.all([api('/a2a', { method: 'POST', body: req, timeout: 25000 }), movePacket(false)])
  el('wAgent')?.classList.add('hot')
  await movePacket(true)
  if (!r.ok) { ans.innerHTML = `<div class="st" style="color:var(--amber)">failed</div>${esc(r.error?.message || 'Request failed.')}`; return }
  const t = taskText(r.data)
  ans.innerHTML = `<div class="st">task ${esc(t.state)}</div>${esc(t.text)}`
  el('a2aRes').innerHTML = jsonHTML(r.data)
}

function renderEvalsShell() {
  const e = el('evals')
  if (e.dataset.ready) return
  e.dataset.ready = '1'
  e.innerHTML = `
    <div class="panel-h"><span class="panel-t"><b>Routing evals</b> labelled cases, run live</span><button class="btn-ghost btn-sm" id="evalBtn">Run evals</button></div>
    <div class="ev-acc">
      <div class="acc"><div class="acc-top"><span>Routing</span><b id="accR">--</b></div><div class="acc-track"><div class="acc-bar" id="accRb"></div></div></div>
      <div class="acc"><div class="acc-top"><span>End to end</span><b id="accE">--</b></div><div class="acc-track"><div class="acc-bar" id="accEb"></div></div></div>
    </div>
    <div class="ev-rows" id="evRows"><div class="khint">Every change is checked against labelled questions: does the agent pick the right tool, and is the final answer right?</div></div>`
  el('evalBtn').addEventListener('click', () => runEvals())
}

let evalRunning = null
export async function runEvals() {
  if (evalRunning) return evalRunning
  renderEvalsShell()
  const btn = el('evalBtn'); btn.disabled = true; btn.textContent = 'Running...'
  const rows = el('evRows')
  rows.innerHTML = '<div class="ps-skel"><div class="skel w80"></div><div class="skel w60"></div><div class="skel w80"></div></div>'
  el('accRb').style.width = '0'; el('accEb').style.width = '0'; el('accR').textContent = '--'; el('accE').textContent = '--'
  evalRunning = (async () => {
    const r = await api('/api/evals')
    btn.disabled = false; btn.textContent = 'Run again'
    if (!r.ok) { setError(rows, r.error, () => runEvals(), { title: 'Evals did not run' }); return null }
    state.evals = r.data
    rows.innerHTML = ''
    const list = r.data.rows || []
    let routed = 0; let e2e = 0
    for (let i = 0; i < list.length; i++) {
      const x = list[i]
      if (x.routed) routed++
      if (x.end_to_end) e2e++
      rows.insertAdjacentHTML('beforeend', `<div class="ev-r"><span class="q" title="${esc(x.q)}">${esc(x.q)}</span><span class="tickm ${x.routed ? 'y' : 'n'}">${x.routed ? 'ROUTED' : 'MISS'}</span><span class="tickm ${x.end_to_end ? 'y' : 'n'}">${x.end_to_end ? 'ANSWER OK' : 'WRONG'}</span></div>`)
      el('accRb').style.width = `${(routed / list.length) * 100}%`
      el('accEb').style.width = `${(e2e / list.length) * 100}%`
      el('accR').textContent = `${routed}/${list.length}`
      el('accE').textContent = `${e2e}/${list.length}`
      rows.lastElementChild?.scrollIntoView({ block: 'nearest' })
      await delay(reduced() ? 0 : 140)
    }
    el('accR').textContent = `${fmt(r.data.routing_accuracy * 100, 0)}%`
    el('accE').textContent = `${fmt(r.data.end_to_end_accuracy * 100, 0)}%`
    emit('evals', r.data)
    return r.data
  })()
  const out = await evalRunning
  evalRunning = null
  return out
}

/* =================== ask results routed to views =================== */
export function applyAskData(intent, data, args) {
  if (intent === 'migration_options' && data) {
    state.knowledgeWhy = data.why || null
    ensureGraph().then(() => {
      const job = data.job || args?.job
      if (job && kg.nodes.has(job)) selectNode(job, data.why)
      else renderKSide(data.why)
    })
  }
  if ((intent === 'findings' || intent === 'metrics')) ensureFindings()
  if (intent === 'drift' && data) { state.drift = data; delete el('drift').dataset.ready; renderDrift(); animateDrift() }
}

export { toast, speak, h }
