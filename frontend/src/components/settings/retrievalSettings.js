export const rerankOptions = backends => Object.entries(backends || {}).map(([provider, backend]) => ({
  value: provider,
  label: provider,
  children: Object.entries(backend.models || {}).filter(([, model]) => model.enabled !== false)
    .map(([key, model]) => ({ value: key, label: `${key} (${model.id || key})` })),
})).filter(provider => provider.children.length)

export const validRerankSelection = (backends, selection) => {
  if (!selection || (!selection.provider && !selection.model)) return true
  return rerankOptions(backends).some(provider => provider.value === selection.provider &&
    provider.children.some(model => model.value === selection.model))
}

// Only explicit additions touch the draft; existing endpoint credentials and model settings win.
export const addVekaiPreset = (settings, kind, { address, modelId }) => {
  if (!['embedding', 'rerank'].includes(kind)) throw new Error('invalid_preset')
  const endpointId = `vekai-${kind}`
  const key = endpointId
  const existingBackend = settings.llm_settings?.[`${kind}_backends`]?.local
  // An existing model is never rebound, even if its endpoint was subsequently removed.
  if (Object.hasOwn(existingBackend?.models || {}, key)) return false

  const url = new URL(address.trim())
  if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || !modelId.trim()) {
    throw new Error('invalid_preset')
  }
  if (kind === 'embedding' && url.pathname === '/') url.pathname = '/v1'
  // vv-llm appends paths verbatim; the rerank mapping already includes /v1.
  if (kind === 'rerank') url.pathname = url.pathname.replace(/\/v1\/?$/, '/')
  const apiBase = url.href.replace(/\/+$/, '')
  const existingEndpoint = settings.llm_settings?.endpoints?.find(endpoint => endpoint.id === endpointId)
  if (existingEndpoint) {
    let existingBase
    try {
      existingBase = new URL(existingEndpoint.api_base).href.replace(/\/+$/, '')
    } catch {
      throw new Error('endpoint_conflict')
    }
    if (existingBase !== apiBase) throw new Error('endpoint_conflict')
  }

  // Validate conflicts before initializing any draft objects.
  const llm = settings.llm_settings ||= {}
  llm.endpoints ||= []
  const backends = llm[`${kind}_backends`] ||= {}
  const backend = backends.local ||= { models: {}, default_endpoint: null }
  backend.models ||= {}
  if (!existingEndpoint) {
    llm.endpoints.push({ id: endpointId, api_base: apiBase, api_key: '', endpoint_type: 'default' })
  }
  backend.models[key] = {
    id: modelId.trim(), enabled: true, endpoints: [endpointId],
    protocol: kind === 'embedding' ? 'openai_embeddings' : 'custom_json_http',
    ...(kind === 'rerank' ? {
      request_mapping: {
        method: 'POST', path: '/v1/rerank',
        body_template: { model: '${model_id}', query: '${query}', documents: '${documents}', top_n: '${top_n}' },
      },
      response_mapping: { results_path: '$.results[*]', field_map: { index: 'index', relevance_score: 'relevance_score' } },
    } : {}),
  }
  return true
}
