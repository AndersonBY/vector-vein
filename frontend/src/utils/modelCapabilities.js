import { CHAT_PROVIDER_LABEL_MAP } from './modelProviders.js'

export function resolveModelCapabilities(backends, provider, model, providerLabels = CHAT_PROVIDER_LABEL_MAP) {
  const backend = provider?.startsWith('_local__')
    ? 'local'
    : Object.keys(backends || {}).find(key => key === provider || providerLabels[key] === provider)
  const configured = backends?.[backend]?.models?.[model]
  const boolean = key => typeof configured?.[key] === 'boolean' ? configured[key] : null
  const tokens = key => typeof configured?.[key] === 'number' && configured[key] > 0 ? configured[key] : null
  return {
    native_multimodal: boolean('native_multimodal'),
    function_call_available: boolean('function_call_available'),
    response_format_available: boolean('response_format_available'),
    context_length: tokens('context_length'),
    max_output_tokens: tokens('max_output_tokens'),
  }
}
