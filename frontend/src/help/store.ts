/**
 * Tiny global store for the help UI (drawer + tour). Framework-free so that
 * `openTopic()` and `startTour()` can be called from anywhere (event handlers,
 * other modules, the browser console), and React reads it with useSyncExternalStore.
 */
import { useSyncExternalStore } from 'react'
import type { PageId } from './types'

export interface HelpState {
  /** topic shown in the drawer (null = closed) */
  topicId: string | null
  /** previous topics, for the drawer's Back button */
  history: string[]
  /** running tour */
  tour: { page: PageId; step: number } | null
  /** how many <HelpDrawer/> / <Tour/> are mounted (so HelpTip knows whether it can open the drawer) */
  drawerMounted: number
  tourMounted: number
}

let state: HelpState = { topicId: null, history: [], tour: null, drawerMounted: 0, tourMounted: 0 }
const listeners = new Set<() => void>()

function set(patch: Partial<HelpState>) {
  state = { ...state, ...patch }
  listeners.forEach((l) => l())
}

export function getHelpState(): HelpState {
  return state
}

export function subscribeHelp(l: () => void): () => void {
  listeners.add(l)
  return () => listeners.delete(l)
}

/** Open a topic in the drawer (pushes the current one onto the Back history). */
export function openTopic(id: string) {
  if (state.topicId === id) return
  set({ topicId: id, history: state.topicId ? [...state.history, state.topicId].slice(-20) : [] })
}

export function closeTopic() {
  set({ topicId: null, history: [] })
}

export function backTopic() {
  const h = [...state.history]
  const prev = h.pop()
  set({ topicId: prev ?? null, history: h })
}

export function startTour(page: PageId, step = 0) {
  set({ tour: { page, step }, topicId: null, history: [] })
}

export function setTourStep(step: number) {
  if (state.tour) set({ tour: { ...state.tour, step } })
}

export function endTour() {
  set({ tour: null })
}

export function registerMount(kind: 'drawer' | 'tour'): () => void {
  if (kind === 'drawer') set({ drawerMounted: state.drawerMounted + 1 })
  else set({ tourMounted: state.tourMounted + 1 })
  return () => {
    if (kind === 'drawer') set({ drawerMounted: Math.max(0, state.drawerMounted - 1) })
    else set({ tourMounted: Math.max(0, state.tourMounted - 1) })
  }
}

// ------------------------------------------------------------------ localStorage (safe)

const PREFIX = 'elnino.help.'

export function lsGet(key: string): string | null {
  try {
    return window.localStorage.getItem(PREFIX + key)
  } catch {
    return null
  }
}

export function lsSet(key: string, value: string | null) {
  try {
    if (value === null) window.localStorage.removeItem(PREFIX + key)
    else window.localStorage.setItem(PREFIX + key, value)
  } catch {
    /* storage blocked: the UI still works, it just does not remember */
  }
}

export function isTourDone(page: PageId): boolean {
  return lsGet(`tour.${page}.done`) === '1'
}

export function markTourDone(page: PageId) {
  lsSet(`tour.${page}.done`, '1')
}

/** Forget completed tours and collapsed guides (e.g. a "Reset help" button). */
export function resetHelpMemory() {
  try {
    const ls = window.localStorage
    for (let i = ls.length - 1; i >= 0; i--) {
      const k = ls.key(i)
      if (k && k.startsWith(PREFIX)) ls.removeItem(k)
    }
  } catch {
    /* ignore */
  }
}

// ------------------------------------------------------------------ React hook

export interface UseHelp extends HelpState {
  openTopic: typeof openTopic
  closeTopic: typeof closeTopic
  backTopic: typeof backTopic
  startTour: typeof startTour
  endTour: typeof endTour
  /** true when a <HelpDrawer/> is mounted: HelpTip then opens it instead of navigating */
  hasDrawer: boolean
}

export function useHelp(): UseHelp {
  const s = useSyncExternalStore(subscribeHelp, getHelpState, getHelpState)
  return { ...s, openTopic, closeTopic, backTopic, startTour, endTour, hasDrawer: s.drawerMounted > 0 }
}
