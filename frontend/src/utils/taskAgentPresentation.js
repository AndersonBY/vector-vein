export const taskStatusClass = status => ({
  COMPLETED: 'status-completed',
  PROCESSING: 'status-processing',
  PENDING: 'status-pending',
  WAITING_FOR_USER: 'status-attention',
  WAITING_FOR_APPROVAL: 'status-attention',
  WAITING_FOR_WORKFLOW: 'status-attention',
  FAILED: 'status-failed',
  INTERRUPTED: 'status-failed',
  PAUSED: 'status-paused',
}[status] || 'status-paused')

export const formatTaskTime = (value, locale = 'zh-CN') => {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  return new Intl.DateTimeFormat(locale, {
    month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(date)
}
