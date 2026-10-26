import { getWorkflowFailures, getWorkflowTaskTitleKey } from './workflowFailures.js'

const finite = value => typeof value === 'number' && Number.isFinite(value) && value >= 0 ? value : null
const text = value => typeof value === 'string' ? value.slice(0, 200) : ''
const states = new Set(['PENDING', 'RUNNING', 'WAITING', 'SUCCEEDED', 'FAILED', 'SKIPPED', 'STOPPED'])

export function getWorkflowTimeline(snapshot = {}, { active = false, status = '', now = Date.now(), fresh = false } = {}) {
  snapshot = snapshot && typeof snapshot === 'object' ? snapshot : {}
  const nodes = Array.isArray(snapshot.nodes) ? snapshot.nodes : []
  const timeline = snapshot.node_timeline && typeof snapshot.node_timeline === 'object' ? snapshot.node_timeline : {}
  const failed = ['FAILED', 'STOPPED'].includes(status) || getWorkflowFailures(snapshot).length > 0
  const eligible = nodes.filter(node => node && !node.ignored && !['triggers', 'assistedNodes'].includes(node.category))
  const ids = [...new Set([...eligible.map(node => node.id), ...Object.keys(timeline).filter(id => !nodes.some(node => node.id === id))])]
  return ids.map(id => {
    const node = eligible.find(node => node.id === id) || {}
    const hasEntry = !!timeline[id] && typeof timeline[id] === 'object'
    const entry = hasEntry ? timeline[id] : {}
    const duration = fresh ? null : hasEntry ? finite(entry.run_time) : finite(node.run_time) ?? finite(snapshot.node_run_time?.[id])
    const startedAt = fresh ? null : finite(entry.started_at)
    const finishedAt = fresh ? null : finite(entry.finished_at)
    let state = !fresh && states.has(entry.status) ? entry.status : ''
    if (!state && !fresh && !hasEntry) {
      if ((Array.isArray(snapshot.skipped_nodes) && snapshot.skipped_nodes.includes(id)) || node.data?.debug?.skipped) state = 'SKIPPED'
      else if (node.data?.status === 500 || (Array.isArray(snapshot.failures) && snapshot.failures.some(item => item?.node_id === id))) state = 'FAILED'
      else if (node.data?.status === 200) state = 'SUCCEEDED'
      else if (node.data?.status === 202 && active) state = 'RUNNING'
    }
    if (!state) state = active ? 'PENDING' : failed ? 'NOT_RUN' : 'UNKNOWN'
    if (state === 'PENDING' && !active) state = failed ? 'NOT_RUN' : 'UNKNOWN'
    let elapsed = duration
    if (elapsed === null && startedAt !== null && finishedAt !== null) elapsed = Math.max(0, (finishedAt - startedAt) / 1000)
    if (elapsed === null && active && ['RUNNING', 'WAITING'].includes(state) && startedAt !== null) elapsed = Math.max(0, (now - startedAt) / 1000)
    return { id, title: text(entry.title) || text(node.data?.title), type: text(entry.node_type) || text(node.type), category: text(node.category), taskName: text(entry.task_name), status: state, startedAt, finishedAt, elapsed }
  })
}

export function getTimelineNodeLabel(node, t, te) {
  const key = `components.nodes.${node.category}.${node.type}.title`
  const taskKey = getWorkflowTaskTitleKey(node.taskName)
  return node.title || (te(key) ? t(key) : taskKey && te(taskKey) ? t(taskKey) : node.type) || node.id
}
