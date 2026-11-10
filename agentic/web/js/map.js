// Dot-matrix map of North America. Regions glow by carbon, work flows as particles.

import { state, on } from './state.js'
import { fitCanvas, carbonRGB, reduced, clamp, lerp, easeInOut, fmt } from './util.js'

const LOWER48 = [[-124.7,48.4],[-122.8,49],[-95.2,49],[-94.6,48.7],[-89.6,48],[-84.5,46.5],[-82.5,45.3],[-82.4,43],[-83.1,42],[-79,42.9],[-79,43.3],[-76.3,44.2],[-74.7,45],[-71.5,45],[-69.2,47.4],[-67.8,47.1],[-67,45],[-70.2,43.6],[-70.6,42.6],[-70,41.7],[-71.9,41.3],[-74,40.6],[-74.1,39.6],[-75.5,38.8],[-76,36.9],[-75.5,35.2],[-77.9,33.9],[-79.9,32.6],[-81.4,30.7],[-80,26.8],[-80.4,25.2],[-81.8,26.1],[-82.7,28],[-84,30],[-86.5,30.4],[-89.4,30.2],[-89.4,29],[-93.8,29.7],[-95,29.2],[-97.2,27.6],[-97.4,25.9],[-99.1,26.4],[-101.4,29.8],[-103.1,29],[-104.7,29.9],[-106.5,31.8],[-108.2,31.3],[-111.1,31.3],[-114.8,32.5],[-117.1,32.5],[-118.5,34],[-120.6,34.6],[-122.4,37.2],[-123.8,39.8],[-124.2,42],[-124.1,46.3]]
const ONTARIO = [[-84.5,46.5],[-80,46.4],[-78,45.9],[-74.5,45.6],[-74.7,45],[-76.3,44.2],[-79,43.3],[-79.2,42.8],[-82.5,42],[-82.5,43],[-81.7,44.5]]

const inPoly = (x, y, poly) => {
  let inside = false
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i]; const [xj, yj] = poly[j]
    if ((yi > y) !== (yj > y) && x < ((xj - xi) * (y - yi)) / (yj - yi) + xi) inside = !inside
  }
  return inside
}
// unit space from the spec projection: x=(lon+125)/59, y=(50-lat)/26
const toU = (lon, lat) => [(lon + 125) / 59, (50 - lat) / 26]

let canvas = null
let stage = null
let dots = []
let zones = []          // [{id, name, short, u, v, lon, lat}]
let cam = { cu: 0.5, cv: 0.5, z: 1 }
let camFrom = null; let camTo = null; let camT0 = 0
let particles = []
let waveT0 = 0
let dispHour = 24
let hover = null
let running = false
let lastNow = 0

// derived from the current plan
let P = null            // plan.plan (detail)
let planZones = new Set()
let homeZone = null
let fixedZone = null
let maxLoad = 1
let maxFlowRate = 1
let flowArcs = []

export function initMap(meta) {
  canvas = document.getElementById('mapCanvas')
  stage = document.getElementById('map')
  zones = (meta?.zones || []).map((z) => { const [u, v] = toU(z.lon, z.lat); return { ...z, u, v } })

  dots = []
  const step = 0.9
  for (let lat = 24.4; lat <= 49.6; lat += step) {
    for (let lon = -124.8; lon <= -66.5; lon += step) {
      if (inPoly(lon, lat, LOWER48) || inPoly(lon, lat, ONTARIO)) {
        const [u, v] = toU(lon, lat)
        let best = -1; let bd = 1e9
        zones.forEach((z, i) => {
          const dx = (lon - z.lon) * 0.79; const dy = lat - z.lat
          const d = Math.sqrt(dx * dx + dy * dy)
          if (d < bd) { bd = d; best = i }
        })
        dots.push({ u, v, zi: best, d: bd, wave: Math.hypot(u - 0.18, (v - 0.55) * 0.55) })
      }
    }
  }
  replayWave()

  canvas.addEventListener('mousemove', (e) => {
    const r = canvas.getBoundingClientRect()
    const mx = e.clientX - r.left; const my = e.clientY - r.top
    hover = null
    let bd = 22
    for (const z of zones) {
      const [x, y] = project(z.u, z.v, r.width, r.height)
      const d = Math.hypot(mx - x, my - y)
      if (d < bd) { bd = d; hover = z }
    }
    canvas.style.cursor = hover ? 'help' : 'default'
  })
  canvas.addEventListener('mouseleave', () => { hover = null })

  on('view', () => ensureLoop())
  document.addEventListener('visibilitychange', () => ensureLoop())
  window.addEventListener('resize', () => ensureLoop())
  ensureLoop()
}

export function replayWave() { waveT0 = performance.now() }

export function focusPulse() {
  if (!stage) return
  stage.classList.remove('focus-pulse'); void stage.offsetWidth; stage.classList.add('focus-pulse')
  replayWave()
}

export function setPlan(plan) {
  P = plan && plan.plan ? plan.plan : null
  planZones = new Set(P ? P.zones : [])
  homeZone = plan ? plan.home_zone : null
  fixedZone = plan && !P && plan.status === 'NOT_MOVABLE' ? plan.home_zone : null
  particles = []
  maxLoad = 1; maxFlowRate = 1; flowArcs = []
  if (P && P.hourly) {
    const hr = P.hourly
    let m = 0
    for (const z of P.zones) {
      for (const k of ['load_with_migration_mwh', 'load_time_shift_mwh', 'load_flat_mwh']) {
        for (const v of hr[k]?.[z] || []) m = Math.max(m, v)
      }
    }
    maxLoad = m || 1
    let fr = 0
    for (const f of P.flows || []) for (const v of f.by_hour_mwh || []) fr = Math.max(fr, v)
    maxFlowRate = fr || 1
    flowArcs = (P.flows || []).map((f) => ({ ...f, a: zones.find((z) => z.id === f.from), b: zones.find((z) => z.id === f.to), acc: 0 }))
      .filter((f) => f.a && f.b)
  }
  // camera: frame the plan's regions, or the whole map
  const focus = P ? zones.filter((z) => planZones.has(z.id)) : (fixedZone ? zones.filter((z) => z.id === fixedZone) : [])
  setCamera(focus)
  ensureLoop()
}

function setCamera(list) {
  let to = { cu: 0.5, cv: 0.5, z: 1 }
  if (list.length) {
    const pad = list.length === 1 ? 0.16 : 0.06
    const u0 = Math.min(...list.map((z) => z.u)) - pad; const u1 = Math.max(...list.map((z) => z.u)) + pad
    const v0 = Math.min(...list.map((z) => z.v)) - pad * 1.5; const v1 = Math.max(...list.map((z) => z.v)) + pad * 1.5
    const z = clamp(Math.min(0.92 / (u1 - u0), 0.92 / ((v1 - v0) * 1)), 1, 3.4)
    to = { cu: (u0 + u1) / 2, cv: (v0 + v1) / 2, z }
  }
  camFrom = { ...cam }; camTo = to; camT0 = performance.now()
  if (reduced()) { cam = to; camTo = null }
}

// map area inside the stage, leaving room for the overlay controls
function frame(w, h) {
  const top = 78; const bottom = 40; const side = 18
  const uh = Math.max(60, h - top - bottom)
  const mw = Math.min(w - side * 2, uh * 1.8)
  return { mw, mh: mw / 1.8, cx: w / 2, cy: top + uh / 2 }
}
function project(u, v, w, h) {
  const f = frame(w, h)
  return [f.cx + (u - cam.cu) * f.mw * cam.z, f.cy + (v - cam.cv) * f.mh * cam.z]
}

// hourly value with smooth interpolation; h >= 24 means the day mean
function valAt(arr, h) {
  if (!arr || !arr.length) return null
  if (h >= 24) return arr.reduce((a, b) => a + b, 0) / arr.length
  const i = clamp(Math.floor(h), 0, arr.length - 1)
  const j = Math.min(i + 1, arr.length - 1)
  const f = clamp(h - i, 0, 1)
  return arr[i] + (arr[j] - arr[i]) * f
}

function ensureLoop() {
  const visible = state.view === 'command' && document.visibilityState === 'visible'
  if (visible && !running && canvas) { running = true; lastNow = performance.now(); requestAnimationFrame(draw) }
}

function draw(now) {
  if (state.view !== 'command' || document.visibilityState !== 'visible') { running = false; return }
  const dt = Math.min(0.05, (now - lastNow) / 1000); lastNow = now
  const { ctx: g, w, h } = fitCanvas(canvas)
  g.clearRect(0, 0, w, h)
  const calm = reduced()

  if (camTo) {
    const t = clamp((now - camT0) / 1300, 0, 1)
    const e = easeInOut(t)
    cam = { cu: lerp(camFrom.cu, camTo.cu, e), cv: lerp(camFrom.cv, camTo.cv, e), z: lerp(camFrom.z, camTo.z, e) }
    if (t >= 1) camTo = null
  }
  // hour follows state with easing unless the day is playing
  const target = state.hour
  if (state.playing || calm || Math.abs(target - dispHour) > 12) dispHour = target
  else dispHour += (target - dispHour) * Math.min(1, dt * 8)
  const H = dispHour
  const hr = P?.hourly
  const live = state.dataAvailable && !!hr

  // per-zone current values
  const zv = new Map()
  for (const z of zones) {
    if (live && planZones.has(z.id)) {
      zv.set(z.id, {
        g: valAt(hr.actual_g_per_kwh?.[z.id], H),
        load: valAt(hr.load_with_migration_mwh?.[z.id], H),
        ghost: valAt(hr.load_time_shift_mwh?.[z.id], H),
      })
    }
  }

  // dots
  const f = frame(w, h)
  const dotR = clamp(f.mw * cam.z / 59 * 0.17, 0.9, 2.6)
  const waveAge = now - waveT0
  for (const d of dots) {
    const [x, y] = project(d.u, d.v, w, h)
    if (x < -4 || y < -4 || x > w + 4 || y > h + 4) continue
    const wa = calm ? 1 : clamp((waveAge - d.wave * 1500) / 450, 0, 1)
    if (wa <= 0) continue
    const z = zones[d.zi]
    const val = z && zv.get(z.id)
    if (val && val.g !== null) {
      const k = Math.exp(-(d.d * d.d) / (2 * 2.3 * 2.3))
      const [r, gg, b] = carbonRGB(val.g)
      g.fillStyle = `rgba(${r},${gg},${b},${(0.12 + 0.62 * k) * wa})`
    } else {
      const dim = P && z && !planZones.has(z.id)
      g.fillStyle = `rgba(150,172,163,${(dim ? 0.09 : 0.16) * wa})`
    }
    g.beginPath(); g.arc(x, y, dotR, 0, Math.PI * 2); g.fill()
  }

  // flows: faint arcs + particles
  if (live && flowArcs.length) {
    g.save()
    g.globalCompositeOperation = 'lighter'
    for (const fl of flowArcs) {
      const [ax, ay] = project(fl.a.u, fl.a.v, w, h)
      const [bx, by] = project(fl.b.u, fl.b.v, w, h)
      const mx = (ax + bx) / 2; const my = (ay + by) / 2
      const dx = bx - ax; const dy = by - ay
      const len = Math.hypot(dx, dy) || 1
      const cx = mx - (dy / len) * len * 0.28; const cy = my + (dx / len) * len * 0.28 - len * 0.08
      fl.geo = { ax, ay, bx, by, cx, cy }
      const rate = H >= 24 ? (fl.mwh / 24) / maxFlowRate : valAt(fl.by_hour_mwh, H) / maxFlowRate
      g.beginPath(); g.moveTo(ax, ay); g.quadraticCurveTo(cx, cy, bx, by)
      g.strokeStyle = `rgba(168,255,53,${calm ? 0.15 + 0.6 * rate : 0.07 + 0.2 * rate})`
      g.lineWidth = calm ? 1 + rate * 4 : 1 + rate * 1.5
      g.stroke()
      if (!calm && rate > 0.001) {
        fl.acc += dt * rate * 16
        while (fl.acc >= 1) { fl.acc -= 1; particles.push({ fl, t: 0, sp: 0.55 + Math.random() * 0.25, j: (Math.random() - 0.5) * 6 }) }
      }
    }
    for (const p of particles) {
      p.t += dt * p.sp
      const q = p.fl.geo
      if (!q) continue
      for (let k = 0; k < 4; k++) {
        const t = clamp(p.t - k * 0.025, 0, 1)
        const x = (1 - t) * (1 - t) * q.ax + 2 * (1 - t) * t * (q.cx + p.j) + t * t * q.bx
        const y = (1 - t) * (1 - t) * q.ay + 2 * (1 - t) * t * (q.cy + p.j) + t * t * q.by
        const a = (1 - k / 4) * Math.sin(Math.PI * clamp(p.t, 0, 1))
        g.fillStyle = k === 0 ? `rgba(220,255,170,${a})` : `rgba(168,255,53,${a * 0.45})`
        g.beginPath(); g.arc(x, y, k === 0 ? 2.2 : 1.6, 0, Math.PI * 2); g.fill()
      }
    }
    particles = particles.filter((p) => p.t < 1)
    if (particles.length > 400) particles.splice(0, particles.length - 400)
    g.restore()
  }

  // nodes
  const pulse = calm ? 0.5 : (Math.sin(now / 420) + 1) / 2
  for (const z of zones) {
    const [x, y] = project(z.u, z.v, w, h)
    const val = zv.get(z.id)
    const inPlan = planZones.has(z.id)
    const dim = (P && !inPlan) || (!P && fixedZone && z.id !== fixedZone)
    if (val && val.g !== null) {
      const [r, gg, b] = carbonRGB(val.g)
      const rad = 5 + 15 * Math.sqrt(Math.max(0, val.load) / maxLoad)
      const ghost = 5 + 15 * Math.sqrt(Math.max(0, val.ghost) / maxLoad)
      const glow = g.createRadialGradient(x, y, rad * 0.3, x, y, rad * 2.6)
      glow.addColorStop(0, `rgba(${r},${gg},${b},0.55)`); glow.addColorStop(1, `rgba(${r},${gg},${b},0)`)
      g.fillStyle = glow; g.beginPath(); g.arc(x, y, rad * 2.6, 0, Math.PI * 2); g.fill()
      g.fillStyle = `rgba(${r},${gg},${b},0.92)`
      g.beginPath(); g.arc(x, y, rad, 0, Math.PI * 2); g.fill()
      g.strokeStyle = 'rgba(7,11,10,.65)'; g.lineWidth = 1; g.stroke()
      // ghost ring: where the load would sit with hour shifting only
      g.setLineDash([3, 3]); g.strokeStyle = 'rgba(243,248,245,.55)'; g.lineWidth = 1
      g.beginPath(); g.arc(x, y, ghost, 0, Math.PI * 2); g.stroke(); g.setLineDash([])
      if (z.id === homeZone) {
        g.strokeStyle = `rgba(243,248,245,${0.35 + 0.4 * pulse})`; g.lineWidth = 1.5
        g.beginPath(); g.arc(x, y, rad + 6 + pulse * 2, 0, Math.PI * 2); g.stroke()
      }
      label(g, z, x, y, rad, `${fmt(val.g, 0)} g`, `rgb(${r},${gg},${b})`, z.id === homeZone)
    } else {
      const isFixed = z.id === fixedZone
      const rad = isFixed ? 7 : 3.6
      g.fillStyle = isFixed ? 'rgba(245,183,61,.9)' : dim ? 'rgba(120,140,132,.35)' : 'rgba(169,188,180,.7)'
      g.beginPath(); g.arc(x, y, rad, 0, Math.PI * 2); g.fill()
      if (isFixed) {
        g.strokeStyle = `rgba(245,183,61,${0.3 + 0.5 * pulse})`; g.lineWidth = 1.5
        g.beginPath(); g.arc(x, y, rad + 5 + pulse * 3, 0, Math.PI * 2); g.stroke()
      }
      label(g, z, x, y, rad, isFixed ? 'fixed' : null, isFixed ? '#f5b73d' : null, false, dim)
    }
  }

  // hover card
  if (hover) {
    const [x, y] = project(hover.u, hover.v, w, h)
    const val = zv.get(hover.id)
    const lines = [hover.name || hover.id]
    if (val) {
      lines.push(`${fmt(val.g, 0)} gCO2eq/kWh ${H >= 24 ? 'day mean' : 'actual'}`)
      lines.push(`${fmt(val.load, 2)} MWh this hour`)
    } else lines.push(P ? 'Not in this job\'s portfolio' : 'No plan loaded')
    g.font = '500 11px Inter, system-ui'
    const bw = Math.max(...lines.map((l) => g.measureText(l).width)) + 18
    const bh = lines.length * 15 + 10
    let bx = x + 14; let by = y - bh - 8
    if (bx + bw > w - 6) bx = x - bw - 14
    if (by < 6) by = y + 14
    g.fillStyle = 'rgba(13,19,17,.95)'; g.strokeStyle = 'rgba(39,53,49,1)'; g.lineWidth = 1
    roundRect(g, bx, by, bw, bh, 8); g.fill(); g.stroke()
    lines.forEach((l, i) => { g.fillStyle = i === 0 ? '#f3f8f5' : '#a9bcb4'; g.fillText(l, bx + 9, by + 18 + i * 15) })
  }

  requestAnimationFrame(draw)
}

function label(g, z, x, y, rad, val, col, home, dim) {
  const left = z.lon < -117.5
  g.textBaseline = 'middle'
  g.textAlign = left ? 'right' : 'left'
  const ox = left ? x - rad - 7 : x + rad + 7
  g.font = '600 11px "IBM Plex Mono", ui-monospace'
  g.fillStyle = dim ? 'rgba(126,147,137,.55)' : 'rgba(243,248,245,.92)'
  const name = z.short || z.id
  g.fillText(home ? `${name} · home` : name, ox, y - (val ? 6 : 0))
  if (val) {
    g.font = '500 10.5px "IBM Plex Mono", ui-monospace'
    g.fillStyle = col || '#a9bcb4'
    g.fillText(val, ox, y + 7)
  }
  g.textAlign = 'left'
}

function roundRect(g, x, y, w, h, r) {
  g.beginPath(); g.moveTo(x + r, y); g.arcTo(x + w, y, x + w, y + h, r); g.arcTo(x + w, y + h, x, y + h, r)
  g.arcTo(x, y + h, x, y, r); g.arcTo(x, y, x + w, y, r); g.closePath()
}
