import { reactive, watch, onScopeDispose } from 'vue'

export function useModelEndpointTest(getInput, request, t) {
  const state = reactive({ loading: false, completed: false, error: '', content: '', reasoningContent: '' })
  let epoch = 0
  const clear = () => {
    epoch += 1
    Object.assign(state, { loading: false, completed: false, error: '', content: '', reasoningContent: '' })
  }
  watch(getInput, clear, { deep: true, flush: 'sync' })
  onScopeDispose(clear)

  const submit = async () => {
    if (state.loading || !getInput().active) return
    clear()
    const currentEpoch = epoch
    const input = getInput()
    if (!input.endpoint) {
      state.error = t('settings.select_endpoint')
      return
    }
    if (!input.modelId?.trim() || !input.message?.trim()) {
      state.error = t('settings.model_test_input_required')
      return
    }
    const endpoint = JSON.parse(JSON.stringify(input.endpoint))
    try {
      if (typeof endpoint.credentials === 'string') {
        endpoint.credentials = endpoint.credentials.trim() ? JSON.parse(endpoint.credentials) : {}
      }
    } catch {
      state.error = t('settings.credentials_parse_failed')
      return
    }
    state.loading = true
    try {
      const response = await request('test_model_endpoint', {
        backend: input.backend, endpoint, model_id: input.modelId.trim(), message: input.message,
      })
      if (epoch !== currentEpoch) return
      if (response?.status !== 200) {
        state.error = typeof response?.msg === 'string' ? response.msg : t('settings.model_test_failed')
        return
      }
      state.completed = true
      state.content = typeof response.data?.content === 'string' ? response.data.content : ''
      state.reasoningContent = typeof response.data?.reasoning_content === 'string' ? response.data.reasoning_content : ''
    } catch {
      if (epoch === currentEpoch) state.error = t('settings.model_test_failed')
    } finally {
      if (epoch === currentEpoch) state.loading = false
    }
  }
  return { state, submit }
}
