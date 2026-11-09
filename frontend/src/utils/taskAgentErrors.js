const categories = new Set(['unknown', 'authentication', 'permission', 'quota', 'model_not_found', 'not_found', 'parameter', 'context_length', 'request_too_large', 'rate_limit', 'timeout', 'connection', 'service', 'request', 'configuration', 'credentials_missing', 'reasoning'])
export const modelFailureCategory = failure => categories.has(failure?.category) ? failure.category : 'unknown'
export const taskModelFailure = entry => entry.model_failure || (entry.kind === 'error' && entry.text === 'model_outcome_unknown' ? { category: 'unknown' } : null)
export const modelHttpStatus = failure => Number.isInteger(failure?.http_status) && failure.http_status >= 400 && failure.http_status <= 599 ? failure.http_status : null

const skillErrorCodes = new Set([
  'invalid_frontmatter',
  'missing_skill_md',
  'invalid_path',
  'symlink_rejected',
  'invalid_source',
  'invalid_archive',
  'duplicate_entry',
  'too_many_files',
  'file_too_large',
  'bundle_too_large',
  'invalid_encoding',
  'invalid_file',
  'invalid_skill',
  'invalid_skill_selection',
  'skill_not_found',
  'skill_disabled',
  'duplicate_skill_name',
  'skill_unavailable',
])

const mcpErrorCodes = new Set([
  'invalid_name',
  'invalid_description',
  'invalid_transport',
  'invalid_timeout',
  'invalid_command',
  'invalid_args',
  'invalid_cwd',
  'invalid_url',
  'invalid_env',
  'invalid_header',
  'invalid_tools',
  'unknown_tool',
  'executable_not_found',
  'authentication_failed',
  'timeout',
  'connection_failed',
  'protocol_error',
  'invalid_tool_schema',
  'tool_schema_too_large',
  'too_many_tools',
  'duplicate_tool_name',
  'tool_namespace_collision',
  'tool_metadata_too_large',
  'secret_in_tool_metadata',
  'invalid_pagination_cursor',
  'server_disabled',
  'invalid_mcp_tool_selection',
  'mcp_tool_not_found',
  'mcp_server_disabled',
  'mcp_server_stale',
  'mcp_tool_disabled',
])

export const formatIntegrationError = (response, t, fallbackKey = 'workspace.taskAgentSpace.save_failed') => {
  if (!response) return t(fallbackKey)
  if (response.status === 409) {
    return t('workspace.taskAgentSpace.integration_conflict')
  }
  if (response.status === 404) {
    return t('workspace.taskAgentSpace.integration_not_found')
  }
  const err = response.data?.integration_error
  if (err && typeof err === 'object') {
    const kind = err.kind === 'mcp' ? 'mcp' : 'skills'
    const code = String(err.code || '')
    const known = kind === 'mcp' ? mcpErrorCodes.has(code) : skillErrorCodes.has(code)
    const key = known
      ? `workspace.taskAgentSpace.integration_error_${kind}_${code}`
      : `workspace.taskAgentSpace.integration_error_${kind}_default`
    return t(key)
  }
  return t(fallbackKey)
}

export const extractSkillDiagnostics = response => {
  const list = response?.data?.integration_error?.diagnostics
  if (!Array.isArray(list)) return []
  return list.filter(item => typeof item === 'string' && item.trim()).slice(0, 10)
}