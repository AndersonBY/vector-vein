import { hasModelOption } from './modelSelection'

export const MODEL_PREFERENCES = ['default', 'high_performance', 'low_cost']
export const REASONING_EFFORTS = ['default', 'none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']

export function validModelPair(options, provider, model) {
  return hasModelOption(options, provider) && hasModelOption(options.find(item => item.value === provider)?.children || [], model)
}

export function availableReasoningEfforts(backends, provider, model) {
  const key = provider?.startsWith('_local__') ? 'local' : provider?.toLowerCase()
  const efforts = backends?.[key]?.models?.[model]?.capabilities?.reasoning_efforts
  return REASONING_EFFORTS.filter(effort => effort === 'default' || (Array.isArray(efforts) ? efforts.includes(effort) : effort !== 'none'))
}
