import { reactive } from 'vue'

/**
 * Minimal global toast store. Views call toast('已移入回收站', {
 * actionLabel: '撤销', onAction: restoreFn }) — the host component in
 * App.vue renders the stack. No dependencies, in-memory only.
 */
const state = reactive({ toasts: [] })
let seq = 0

export function toast(message, { actionLabel = '', onAction = null,
                                 duration = 4000, type = 'info' } = {}) {
  const id = ++seq
  const item = { id, message, actionLabel, onAction, type }
  state.toasts.push(item)
  if (duration > 0) {
    setTimeout(() => dismiss(id), duration)
  }
  return id
}

export function dismiss(id) {
  const i = state.toasts.findIndex((t) => t.id === id)
  if (i !== -1) state.toasts.splice(i, 1)
}

export function runAction(t) {
  try {
    if (t.onAction) t.onAction()
  } finally {
    dismiss(t.id)
  }
}

export function useToasts() {
  return state
}
