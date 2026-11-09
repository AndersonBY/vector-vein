export const interactionTarget = question => Object.fromEntries(
  ['sessionId', 'turnId', 'generation', 'interactionId', 'operationId', 'attempt', 'requestDigest'].map(key => [key, question[key]])
)

export function interactionAnswer(question, selected, text) {
  if (text.trim()) return { kind: 'text', text: text.trim() }
  const spec = question?.answerSpec
  if (!spec || spec.kind === 'text' || !selected.length) return null
  if (spec.kind === 'single' && selected.length !== 1) return null
  if (selected.some(value => !spec.options.includes(value))) return null
  return { kind: spec.kind, selected: [...selected], custom: [] }
}

export function mergeTaskTimeline(messages = [], timeline = []) {
  const answeredTurns = new Set(timeline.filter(item => item.kind === 'assistant').map(item => item.turn_id))
  const result = [...timeline, ...messages.filter(item => item.role === 'user' || !answeredTurns.has(item.turn_id)).map(item => ({
    ...item, id: item.mid, kind: item.role, text: item.content, final: item.role === 'assistant',
  }))]
  return result.sort((a, b) => (Date.parse(a.created_at) - Date.parse(b.created_at)) || ((a.kind === 'user' ? 0 : 1) - (b.kind === 'user' ? 0 : 1)))
}

export const taskIsActive = status => ['PENDING', 'PROCESSING', 'WAITING_FOR_WORKFLOW'].includes(status)
export const taskNeedsPolling = (status, disconnected = false) => disconnected || [
  'PENDING', 'PROCESSING', 'WAITING_FOR_USER', 'WAITING_FOR_APPROVAL', 'WAITING_FOR_WORKFLOW', 'PAUSED',
].includes(status)

export const fileSize = bytes => bytes < 1024 ? `${bytes} B` : bytes < 1024 * 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${(bytes / 1024 / 1024).toFixed(1)} MB`

export function commandStatus(entry) {
  if (!['bash', 'check_background_command', 'stop_background_command'].includes(entry.tool_name)) return null
  if (['running', 'stopping', 'unknown', 'completed', 'failed', 'timeout', 'stopped'].includes(entry.command_status)) return entry.command_status
  if (entry.result?.truncated) return null
  try {
    const status = JSON.parse(entry.result.preview).status
    return ['running', 'stopping', 'unknown', 'completed', 'failed', 'timeout', 'stopped'].includes(status) ? status : null
  } catch { return null }
}

export const isMcpUnknown = entry => Boolean(
  entry?.status === 'unknown' || entry?.mcp_run?.status === 'UNKNOWN' || entry?.mcp_run?.dispatch_uncertain
)

export const isParkedMcpWait = (task, state, mcpRuns = []) => {
  if (!task || !['FAILED', 'PROCESSING'].includes(task.status) || state?.waitKind !== 'provider') return false
  if (!Array.isArray(mcpRuns) || !mcpRuns.length) return false
  const activeTurn = typeof task.current_turn_id === 'string' ? task.current_turn_id.trim() : ''
  if (!activeTurn) return false
  const turnRuns = mcpRuns.filter(run => run?.turn_id === activeTurn)
  if (!turnRuns.length) return false
  return turnRuns.some(run => run?.status === 'UNKNOWN' || Boolean(run?.dispatch_uncertain))
    && !turnRuns.some(run => ['ADMITTED', 'DISPATCHING'].includes(run?.status))
}

const mapMcpRunStatus = (entry, parsed = null) => {
  const mcpRun = entry?.mcp_run || null
  if (isMcpUnknown(entry) || parsed?.status === 'unknown') return 'unknown'
  const runStatus = mcpRun?.status
  if (runStatus === 'FINISHED') {
    return (parsed?.is_error || entry?.status === 'error') ? 'error' : 'success'
  }
  if (runStatus === 'FAILED') return 'error'
  if (runStatus === 'CANCELLED') return 'cancelled'
  if (runStatus === 'ADMITTED') return 'pending'
  if (runStatus === 'DISPATCHING') return 'running'
  if (parsed?.is_error || entry?.status === 'error') return 'error'
  if (entry?.status === 'cancelled') return 'cancelled'
  if (entry?.status === 'running') return 'running'
  if (entry?.status === 'pending') return 'pending'
  if (entry?.status === 'success' && parsed && typeof parsed === 'object') return 'success'
  return 'pending'
}

export const toolStatusKey = entry => entry?.status === 'error' && entry.tool_name === 'check_background_command'
  ? 'command_query_failed'
  : isMcpUnknown(entry)
    ? 'tool_status_unknown'
    : entry?.mcp_run
      ? 'tool_status_' + mapMcpRunStatus(entry)
      : 'tool_status_' + (entry?.status || 'pending')


export function taskActivityRows(entries) {
  const visible = entries.filter(entry => ['user', 'assistant', 'tool', 'sub_agent', 'question', 'error', 'memory_compact_completed', 'run_cancelled'].includes(entry.kind))
  const rows = []
  for (const entry of visible) {
    if (entry.kind !== 'tool') { rows.push(entry); continue }
    const previous = rows.at(-1)
    if (previous?.kind === 'activity' && previous.turn_id === entry.turn_id) previous.entries.push(entry)
    else rows.push({ id: `activity:${entry.id}`, kind: 'activity', turn_id: entry.turn_id, entries: [entry], created_at: entry.created_at })
  }
  return rows
}

export const toolDisplaySummary = entry => {
  const args = entry.arguments || {}
  const value = args.skill_name || args.path || args.file_path || args.command || args.task_description || args.query || args.pattern || (entry?.tool_name === 'activate_skill' ? args.name : '') || ''
  return typeof value === 'string' ? value.replace(/\s+/g, ' ').slice(0, 160) : ''
}

// Only a retained final response closes a segment; a pause or disconnect does not.
export function taskConversationRows(entries) {
  const rows = []
  const closedTurns = new Set(entries.filter(entry => entry.kind === 'assistant' && entry.final).map(entry => entry.turn_id))
  let steps = []
  const flush = endTime => {
    const details = taskActivityRows(steps)
    if (details.length && closedTurns.has(steps[0].turn_id)) {
      const attention = steps.some(item => item.kind === 'error' || item.kind === 'run_cancelled'
        || item.status === 'error' || item.status === 'cancelled' || item.mcp_run?.status === 'FAILED' || item.mcp_run?.status === 'CANCELLED'
        || isMcpUnknown(item) || ['unknown', 'running', 'stopping', 'failed', 'timeout'].includes(commandStatus(item))
        || (item.kind === 'sub_agent' && item.status !== 'completed'))
      const duration = Date.parse(endTime || steps.at(-1).created_at) - Date.parse(steps[0].created_at)
      rows.push({ id: `history:${steps[0].id}`, kind: 'history', entries: [...steps], attention,
        cycles: new Set(steps.map(item => item.cycle).filter(Number.isFinite)).size,
        duration: Number.isFinite(duration) ? Math.max(0, Math.floor(duration / 1000)) : 0 })
    } else rows.push(...details)
    steps = []
  }
  for (const entry of entries) {
    if (entry.kind === 'user' || entry.kind === 'question' || (steps.length && steps[0].turn_id !== entry.turn_id)) flush()
    if (entry.kind === 'user' || entry.kind === 'question') { rows.push(entry); continue }
    if (entry.kind === 'assistant' && entry.final) {
      flush(entry.created_at)
      rows.push(entry)
    } else steps.push(entry)
  }
  flush()
  return rows
}

const buildMcpFallbackPresentation = (entry, rawText = '') => {
  const mcpRun = entry?.mcp_run || null
  if (!mcpRun) return null
  const status = mapMcpRunStatus(entry)
  const isErr = status === 'error' || status === 'cancelled'
  return {
    text: rawText,
    mcp: {
      server_id: mcpRun.server_id || '',
      server_name: mcpRun.server_name || mcpRun.server_id || '',
      tool_name: mcpRun.tool_name || entry?.tool_name || '',
      namespaced_name: mcpRun.namespaced_name || entry?.tool_name || '',
      status,
      is_error: isErr,
      error_code: entry?.error_code || mcpRun.error_code || mcpRun.unknown_code || '',
      error_message: mcpRun.unknown_reason || '',
      text: rawText,
      structured_content: null,
      artifacts: Array.isArray(mcpRun.artifacts) ? mcpRun.artifacts : [],
      truncated: Boolean(entry?.result?.truncated),
    },
  }
}

export function toolResultPresentation(entry, text) {
  const mcpRun = entry?.mcp_run || null
  if (typeof text !== 'string' || !text.trim()) {
    if (mcpRun) return buildMcpFallbackPresentation(entry, '')
    return { text: typeof text === 'string' ? text : '' }
  }
  let parsed
  try {
    parsed = JSON.parse(text)
  } catch {
    if (mcpRun) return buildMcpFallbackPresentation(entry, text)
    return { text }
  }
  if (!parsed || typeof parsed !== 'object') {
    if (mcpRun) return buildMcpFallbackPresentation(entry, text)
    return { text }
  }
  if (['bash', 'check_background_command', 'stop_background_command'].includes(entry?.tool_name)
      && ['running', 'stopping', 'unknown', 'completed', 'failed', 'timeout', 'stopped'].includes(parsed.status) && typeof parsed.output === 'string') {
    return { text: parsed.output, command: parsed, raw: JSON.stringify(parsed, null, 2) }
  }
  if (parsed.untrusted_mcp_output === true || parsed.trust_boundary === 'untrusted_external_mcp_tool_output' || mcpRun) {
    const artifacts = Array.isArray(parsed.artifacts) && parsed.artifacts.length
      ? parsed.artifacts
      : (Array.isArray(mcpRun?.artifacts) ? mcpRun.artifacts : [])
    const status = mapMcpRunStatus(entry, parsed)
    const isErr = status === 'error' || status === 'cancelled'
    const bodyText = typeof parsed.text === 'string' ? parsed.text : (typeof parsed.error === 'string' ? parsed.error : '')
    const structured = parsed.structured_content !== undefined ? parsed.structured_content : null
    return {
      text: bodyText,
      mcp: {
        server_id: parsed.server_id || mcpRun?.server_id || '',
        server_name: parsed.server_name || mcpRun?.server_name || parsed.server_id || mcpRun?.server_id || '',
        tool_name: parsed.tool_name || mcpRun?.tool_name || entry?.tool_name || '',
        namespaced_name: parsed.namespaced_name || mcpRun?.namespaced_name || entry?.tool_name || '',
        status,
        is_error: isErr,
        error_code: parsed.error_code || entry?.error_code || mcpRun?.error_code || mcpRun?.unknown_code || '',
        error_message: typeof parsed.error === 'string' ? parsed.error : (mcpRun?.unknown_reason || ''),
        text: bodyText,
        structured_content: structured,
        artifacts,
        truncated: Boolean(parsed.truncated || entry?.result?.truncated),
      },
      raw: JSON.stringify(parsed, null, 2),
    }
  }
  return { text: JSON.stringify(parsed, null, 2) }
}

export function taskFileLink(href, project = false) {
  const path = href.startsWith('./') ? href.slice(2) : href
  let decoded
  try { decoded = decodeURIComponent(path) } catch { return null }
  if (decoded.replaceAll('\\', '/').split('/').some(part => part.toLowerCase() === '.knowledge')) {
    if (!path.startsWith('.knowledge/') || /%(?:2f|5c|2e|25)/i.test(path) || /[%\\:\0?#]/.test(decoded) || decoded.split('/').some(part => !part || part === '.' || part === '..')) return null
    return path
  }
  if (path.startsWith('inputs/') || path.startsWith('outputs/') || (project && path.startsWith('project-files/'))) return path
  if (project && path && !path.startsWith('#') && !path.startsWith('//') && (!/^[a-z][a-z0-9+.-]*:/i.test(path) || /^[a-z]:[/\\]/i.test(path))) return path
  return null
}
