// Ctrl+K command palette.

import { esc } from './util.js'

let items = []
let shown = []
let idx = 0
let getItems = () => []

export function initPalette(provider) {
  getItems = provider
  const input = document.getElementById('palInput')
  const wrap = document.getElementById('palette')
  input.addEventListener('input', () => { idx = 0; render() })
  input.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); idx = Math.min(shown.length - 1, idx + 1); render() }
    else if (e.key === 'ArrowUp') { e.preventDefault(); idx = Math.max(0, idx - 1); render() }
    else if (e.key === 'Enter') { e.preventDefault(); runAt(idx) }
    else if (e.key === 'Escape') { e.preventDefault(); closePalette() }
  })
  wrap.addEventListener('mousedown', (e) => { if (e.target === wrap) closePalette() })
  document.getElementById('paletteBtn').addEventListener('click', () => openPalette())
}

export const paletteOpen = () => !document.getElementById('palette').hidden

export function openPalette() {
  items = getItems()
  idx = 0
  const input = document.getElementById('palInput')
  input.value = ''
  document.getElementById('palette').hidden = false
  render()
  setTimeout(() => input.focus(), 0)
}

export function closePalette() { document.getElementById('palette').hidden = true }
export function togglePalette() { if (paletteOpen()) closePalette(); else openPalette() }

function render() {
  const q = document.getElementById('palInput').value.trim().toLowerCase()
  const words = q.split(/\s+/).filter(Boolean)
  shown = items.filter((it) => { const hay = `${it.group} ${it.label} ${it.keys || ''}`.toLowerCase(); return words.every((w) => hay.includes(w)) })
  const list = document.getElementById('palList')
  if (!shown.length) { list.innerHTML = '<div class="pal-empty">No matches.</div>'; return }
  let html = ''; let g = ''
  shown.forEach((it, i) => {
    if (it.group !== g) { g = it.group; html += `<div class="pal-group">${esc(g)}</div>` }
    html += `<div class="pal-item${i === idx ? ' on' : ''}" role="option" data-i="${i}"><span class="ic">${esc(it.icon || '>')}</span>${esc(it.label)}${it.hint ? `<span class="hint">${esc(it.hint)}</span>` : ''}</div>`
  })
  list.innerHTML = html
  list.querySelectorAll('.pal-item').forEach((n) => {
    n.addEventListener('mousemove', () => { if (idx !== +n.dataset.i) { idx = +n.dataset.i; render() } })
    n.addEventListener('click', () => runAt(+n.dataset.i))
  })
  list.querySelector('.pal-item.on')?.scrollIntoView({ block: 'nearest' })
}

function runAt(i) {
  const it = shown[i]
  if (!it) return
  closePalette()
  try { it.run() } catch (e) { console.warn('[gridshift] palette', e) }
}
