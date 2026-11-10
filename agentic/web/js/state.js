// Shared state and a tiny event bus. Every module reads from here.

export const state = {
  health: null,
  meta: null,
  serverUp: false,
  dataAvailable: false,
  view: 'command',
  req: { job: 'llm_training', day: '2025-06-15', share: 0.3 },
  plan: null,           // last /api/plan object
  planState: 'idle',    // idle | loading | ok | error | offline
  planError: null,
  sweep: null,
  context: {},          // conversation context from /api/ask
  hour: 24,             // 0..24, 24 means the full day has played
  playing: false,
  gate: 'none',         // none | pending | approved | rejected
  stripLit: 0,
  audit: [],
  muted: false,
  presenting: false,
  lensOpen: false,
  findings: null,
  graph: null,
  drift: null,
  evals: null,
  interfaces: null,
}

const subs = new Map()
export function on(evt, fn) {
  if (!subs.has(evt)) subs.set(evt, new Set())
  subs.get(evt).add(fn)
  return () => subs.get(evt).delete(fn)
}
export function emit(evt, payload) {
  const s = subs.get(evt)
  if (!s) return
  for (const fn of [...s]) {
    try { fn(payload) } catch (e) { console.warn('[gridshift]', evt, e) }
  }
}
