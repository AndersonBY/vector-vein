export const FEATURE_FLAGS = Object.freeze({
  schedule: 'desktop.schedule',
  experimentalLlmProviders: 'desktop.experimental_llm_providers',
  agentWorkspace: 'desktop.agent_workspace',
  documentTools: 'desktop.document_tools',
})

export const desktopFeatureFlags = Object.freeze({
  [FEATURE_FLAGS.schedule]: true,
  [FEATURE_FLAGS.experimentalLlmProviders]: true,
  [FEATURE_FLAGS.agentWorkspace]: true,
  [FEATURE_FLAGS.documentTools]: true,
})

export function isFeatureEnabled(flagKey) {
  return desktopFeatureFlags[flagKey] !== false
}
