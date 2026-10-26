const text = (value, limit = 1500) => typeof value === 'string' ? value.slice(0, limit) : ''

export function getWorkflowFailures(snapshot) {
  if (!snapshot || typeof snapshot !== 'object') return []
  const nodes = Array.isArray(snapshot.nodes) ? snapshot.nodes : []
  const failures = Array.isArray(snapshot.failures) ? snapshot.failures : []
  const result = failures.filter(item => item && typeof item === 'object').slice(0, 8).map(item => {
    const nodeId = text(item.node_id, 200)
    const node = nodes.find(node => node?.id === nodeId)
    return {
      nodeId,
      nodeName: text(item.node_name, 200) || text(node?.data?.title, 200),
      taskName: text(item.task_name, 200),
      code: text(item.code, 200),
      exceptionType: text(item.exception_type, 200),
      message: text(item.message),
    }
  }).filter(item => Object.values(item).some(Boolean))
  if (result.length === 0 && text(snapshot.error_task)) {
    result.push({ taskName: text(snapshot.error_task, 200) })
  }
  return result
}

export function getWorkflowTaskTitleKey(taskName) {
  if (typeof taskName !== 'string' || !/^[a-zA-Z_]+\.[a-zA-Z_]+$/.test(taskName)) return ''
  const [rawCategory, rawNode] = taskName.split('.')
  let category = rawCategory.replace(/_([a-z])/g, (_, letter) => letter.toUpperCase())
  if (category === 'output') category = 'outputs'
  let node = rawNode.split('_').filter(Boolean).map(word => word[0].toUpperCase() + word.slice(1)).join('')
  if (node === 'OpenAi') node = 'OpenAI'
  if (node === 'ChatGlm') node = 'ChatGLM'
  if (node === 'SearchData' && category === 'vectorDb') node = 'Search'
  return `components.nodes.${category}.${node}.title`
}

export function getWorkflowRunStatus(response) {
  if (response?.status === 102 || response?.msg === 'PAUSED' || response?.data?.status === 'PAUSED') return ''
  if (response?.msg === 'STOPPED' || response?.data?.status === 'STOPPED') return 'STOPPED'
  if (response?.status === 500 || response?.data?.status === 'FAILED' ||
      getWorkflowFailures(response?.data?.data).length > 0) return 'FAILED'
  return response?.status === 200 ? 'FINISHED' : ''
}

export function getWorkflowFailureSnapshot(snapshot, result) {
  if (getWorkflowFailures(snapshot).length > 0) return snapshot
  if (typeof result !== 'string') return {}
  try {
    const value = JSON.parse(result)
    return value && typeof value === 'object' ? value : {}
  } catch {
    return {}
  }
}
