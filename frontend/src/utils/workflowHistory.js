import { cloneDeep, isEqual } from 'lodash-es'

const transientKeys = new Set([
  'selected', 'computedPosition', 'handleBounds', 'dimensions', 'initialized',
  'isParent', 'resizing', 'dragging', 'events', 'sourceNode', 'targetNode',
])

// Vue Flow's toObject JSON-roundtrips data, which discards template conditions.
export function workflowSnapshot(nodes, edges) {
  const clean = item => cloneDeep(Object.fromEntries(Object.entries(item)
    .filter(([key, value]) => !transientKeys.has(key) && value !== undefined)))
  const realNodes = nodes.filter(node => !node.shadow)
  const ids = new Set(realNodes.map(node => node.id))
  return {
    nodes: realNodes.map(node => {
      const result = clean(node)
      for (const field of Object.values(result.data?.template || {})) {
        delete field.hide
        delete field.group_collpased
      }
      return result
    }),
    edges: edges.filter(edge => !edge.shadow && ids.has(edge.source) && ids.has(edge.target)).map(edge => {
      const result = clean(edge)
      for (const key of ['sourceX', 'sourceY', 'targetX', 'targetY']) delete result[key]
      if (edge.originalStyle) result.style = cloneDeep(edge.originalStyle)
      delete result.originalStyle
      return result
    }),
  }
}

export function createWorkflowHistory(limit = 50) {
  let past = []
  let future = []
  let current
  return {
    reset(snapshot) {
      current = cloneDeep(snapshot)
      past = [current]
      future = []
    },
    observe(snapshot) {
      if (!current || isEqual(current, snapshot)) return false
      current = cloneDeep(snapshot)
      future = []
      return true
    },
    commit() {
      if (!current || isEqual(past.at(-1), current)) return
      past.push(current)
      if (past.length > limit + 1) past.shift()
    },
    settle(snapshot) {
      current = cloneDeep(snapshot)
      past[past.length - 1] = current
    },
    undo() {
      this.commit()
      if (past.length < 2) return
      future.push(past.pop())
      current = past.at(-1)
      return cloneDeep(current)
    },
    redo() {
      if (!future.length) return
      current = future.pop()
      past.push(current)
      return cloneDeep(current)
    },
    get canUndo() { return past.length > 1 || (current && !isEqual(past.at(-1), current)) },
    get canRedo() { return future.length > 0 },
  }
}

export function isHistoryTextTarget(target) {
  return !!target?.closest?.('input, textarea, select, [contenteditable]:not([contenteditable="false"]), .cm-editor, .code-editor, [role="dialog"], .ant-modal')
}
