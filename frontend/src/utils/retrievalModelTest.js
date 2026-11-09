import { reactive, watch, onScopeDispose } from 'vue'

export function retrievalTestEndpoints(model, defaultEndpoint, endpoints) {
  const bindings = model?.endpoints?.length ? model.endpoints : (defaultEndpoint ? [defaultEndpoint] : [])
  return bindings.map((binding, index) => {
    const id = typeof binding === 'string' ? binding : binding.endpoint_id
    return {
      value: String(index), label: typeof binding === 'object' && binding.model_id ? `${id} (${binding.model_id})` : id,
      binding, endpoint: endpoints.find(endpoint => endpoint.id === id),
    }
  })
}

export function useRetrievalModelTest(getInput, request, t) {
  const state = reactive({ loading: false, result: null, error: '' })
  let epoch = 0
  const clear = () => {
    epoch++
    Object.assign(state, { loading: false, result: null, error: '' })
  }
  watch(getInput, clear, { deep: true, flush: 'sync' })
  onScopeDispose(clear)
  const submit = async () => {
    const input = getInput()
    if (state.loading || !input.active) return
    clear()
    const current = epoch
    if (!input.modelKey?.trim() || !input.modelConfig) {
      state.error = t('settings.retrieval_test_error_invalid_config')
      return
    }
    if (!input.endpoint || !input.binding) {
      state.error = t('settings.retrieval_test_choose_endpoint')
      return
    }
    const payload = JSON.parse(JSON.stringify({
      kind: input.kind, backend: input.backend, model_key: input.modelKey.trim(),
      model_config: input.modelConfig, endpoint: input.endpoint, binding: input.binding,
    }))
    try {
      if (typeof payload.endpoint.credentials === 'string') {
        payload.endpoint.credentials = payload.endpoint.credentials.trim() ? JSON.parse(payload.endpoint.credentials) : {}
      }
    } catch {
      state.error = t('settings.credentials_parse_failed')
      return
    }
    state.loading = true
    try {
      const response = await request('test_retrieval_model', payload)
      if (current !== epoch) return
      if (response?.status === 200 && response.data?.kind === input.kind) {
        state.result = response.data
      } else {
        const allowed = ['invalid_config', 'auth_failed', 'not_found', 'timeout', 'connection_failed', 'invalid_response', 'request_failed']
        const code = response?.data?.error_code
        state.error = t(`settings.retrieval_test_error_${allowed.includes(code) ? code : 'request_failed'}`)
      }
    } catch {
      if (current === epoch) state.error = t('settings.retrieval_test_error_request_failed')
    } finally {
      if (current === epoch) state.loading = false
    }
  }
  return { state, submit }
}
