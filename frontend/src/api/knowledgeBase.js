import baseAPI from './base'

export function knowledgeBaseAPI(action, payload = {}) {
  return baseAPI(`knowledge_base__${action}`, payload)
}

export async function knowledgeRequest(action, payload = {}) {
  const response = await knowledgeBaseAPI(action, payload)
  if (response?.status !== 200) {
    const error = new Error('knowledge_request_failed')
    error.code = response?.data?.error_code
    error.status = response?.status
    throw error
  }
  return response.data
}

export function knowledgeErrorKey(error, fallback = 'operation_failed') {
  const code = error?.status === 409 && error?.code !== 'name_conflict' ? 'conflict' : error?.code
  return `knowledgeBase.${['conflict', 'name_conflict', 'not_found', 'unsupported_type', 'file_too_large', 'unsafe_path', 'file_missing'].includes(code) ? code : fallback}`
}
