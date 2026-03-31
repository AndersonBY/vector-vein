import { defineStore } from 'pinia'

import { settingAPI } from '@/api/user'

const STORAGE_KEY = 'modelCatalogPayload'
const STORAGE_TTL_MS = 30 * 60 * 1000

const EMPTY_PAYLOAD = {
  providers: [],
  endpoints: [],
  models: [],
  modelFamilies: [],
  providerMap: {},
  endpointMap: {},
  familyMap: {},
  llmBackends: {},
  embeddingProviders: [],
  embeddingModels: [],
  embeddingProviderMap: {},
  embeddingBackends: {},
  customFamilies: {},
}

const getCachedPayload = () => {
  try {
    const cached = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}')
    if (!cached?.payload || typeof cached.payload !== 'object' || Array.isArray(cached.payload)) {
      return {}
    }
    const cachedAt = Number(cached.cachedAt || 0)
    if (cachedAt <= 0 || Date.now() - cachedAt > STORAGE_TTL_MS) {
      return {}
    }
    return cached.payload
  } catch (error) {
    return {}
  }
}

const prettifyProviderName = (providerKey) => {
  const providerNameMap = {
    aliyun_qwen: 'Qwen',
    anthropic: 'Anthropic',
    baichuan: 'Baichuan',
    baidu_wenxin: 'Baidu Wenxin',
    chat_glm: 'ChatGLM',
    custom_model: 'Custom Model',
    custom: 'Custom',
    deepseek: 'DeepSeek',
    ernie: 'Ernie',
    gemini: 'Gemini',
    groq: 'Groq',
    jina: 'Jina',
    ling_yi_wan_wu: 'LingYiWanWu',
    local: 'Local',
    mini_max: 'MiniMax',
    minimax: 'MiniMax',
    moonshot: 'Moonshot',
    open_ai: 'OpenAI',
    openai: 'OpenAI',
    qwen: 'Qwen',
    cohere: 'Cohere',
    siliconflow: 'Siliconflow',
    stepfun: 'StepFun',
    voyage: 'Voyage',
    universal_llm: 'Universal LLM',
    x_ai: 'xAI',
    xai: 'xAI',
    yi: 'Yi',
    zhipuai: 'ZhiPuAI',
    zhipuai: 'ZhiPuAI',
  }
  return providerNameMap[providerKey] || providerKey.replaceAll('_', ' ')
}

const getBackendModelEntries = (models) => {
  if (!models || typeof models !== 'object' || Array.isArray(models)) {
    return []
  }
  return Object.entries(models).reverse()
}

const buildCatalogPayload = (settingPayload) => {
  const settingData = settingPayload?.data || {}
  const llmSettings = settingData.llm_settings || {}
  const backends = llmSettings.backends || {}
  const embeddingBackends = llmSettings.embedding_backends || {}
  const endpoints = llmSettings.endpoints || []
  const customFamilies = settingData.custom_llms || {}

  const endpointMap = endpoints.reduce((result, endpoint) => {
    if (endpoint?.id) {
      result[endpoint.id] = endpoint
    }
    return result
  }, {})

  const models = []
  const modelFamilies = []
  const providerMap = {}
  const familyMap = {}
  const embeddingModels = []
  const embeddingProviders = []
  const embeddingProviderMap = {}

  Object.entries(backends).forEach(([providerKey, providerValue]) => {
    const backendModels = providerValue?.models || {}
    const providerModels = getBackendModelEntries(backendModels).map(([modelKey, modelValue]) => {
      const endpointsForModel = Array.isArray(modelValue?.endpoints) ? modelValue.endpoints : []
      return {
        provider: providerKey,
        family: providerKey,
        key: modelKey,
        id: modelValue?.id || modelKey,
        endpoints: endpointsForModel,
        endpointLabels: endpointsForModel.map((endpointId) => endpointMap[endpointId]?.id || endpointId),
        isCustom: false,
      }
    })

    models.push(...providerModels)
    providerMap[providerKey] = {
      key: providerKey,
      label: prettifyProviderName(providerKey),
      modelCount: providerModels.length,
      families: [providerKey],
    }
    modelFamilies.push({
      key: providerKey,
      label: prettifyProviderName(providerKey),
      provider: providerKey,
      isCustom: false,
      modelCount: providerModels.length,
    })
    familyMap[providerKey] = providerModels
  })

  const localFamilyKey = 'custom_llms'
  const customFamilyModels = []
  Object.entries(customFamilies).forEach(([familyName, familyModels]) => {
    const normalizedModels = (familyModels || []).map((modelName) => ({
      provider: localFamilyKey,
      family: familyName,
      key: modelName,
      id: modelName,
      endpoints: [],
      endpointLabels: [],
      isCustom: true,
    }))
    customFamilyModels.push(...normalizedModels)
    modelFamilies.push({
      key: familyName,
      label: familyName,
      provider: localFamilyKey,
      isCustom: true,
      modelCount: normalizedModels.length,
    })
    familyMap[familyName] = normalizedModels
  })

  if (customFamilyModels.length > 0) {
    providerMap[localFamilyKey] = {
      key: localFamilyKey,
      label: 'Custom LLMs',
      modelCount: customFamilyModels.length,
      families: Object.keys(customFamilies),
    }
    models.push(...customFamilyModels)
  }

  Object.entries(embeddingBackends).forEach(([providerKey, providerValue]) => {
    const backendModels = providerValue?.models || {}
    const providerModels = getBackendModelEntries(backendModels).map(([modelKey, modelValue]) => {
      const endpointsForModel = Array.isArray(modelValue?.endpoints) ? modelValue.endpoints : []
      return {
        provider: providerKey,
        key: modelKey,
        id: modelValue?.id || modelKey,
        endpoints: endpointsForModel,
        endpointLabels: endpointsForModel.map((endpointId) => endpointMap[endpointId]?.id || endpointId),
        dimensions: modelValue?.dimensions ?? null,
        protocol: modelValue?.protocol || '',
      }
    })

    if (providerModels.length === 0) {
      return
    }

    const providerLabel = prettifyProviderName(providerKey)
    embeddingModels.push(...providerModels)
    embeddingProviderMap[providerKey] = {
      key: providerKey,
      label: providerLabel,
      modelCount: providerModels.length,
      defaultEndpoint: providerValue?.default_endpoint || '',
      models: providerModels,
    }
    embeddingProviders.push({
      key: providerKey,
      label: providerLabel,
      modelCount: providerModels.length,
    })
  })

  return {
    providers: Object.values(providerMap),
    endpoints,
    models,
    modelFamilies,
    providerMap,
    endpointMap,
    familyMap,
    llmBackends: backends,
    embeddingProviders,
    embeddingModels,
    embeddingProviderMap,
    embeddingBackends,
    customFamilies,
  }
}

export const useModelCatalogStore = defineStore('modelCatalog', {
  state: () => ({
    payload: {
      ...EMPTY_PAYLOAD,
      ...getCachedPayload(),
    },
    loaded: false,
    loading: false,
    loadError: '',
    loadedAt: 0,
    _loadingPromise: null,
  }),
  getters: {
    providers: (state) => state.payload.providers || [],
    endpoints: (state) => state.payload.endpoints || [],
    models: (state) => state.payload.models || [],
    modelFamilies: (state) => state.payload.modelFamilies || [],
    providerMap: (state) => state.payload.providerMap || {},
    endpointMap: (state) => state.payload.endpointMap || {},
    familyMap: (state) => state.payload.familyMap || {},
    llmBackends: (state) => state.payload.llmBackends || {},
    embeddingProviders: (state) => state.payload.embeddingProviders || [],
    embeddingModels: (state) => state.payload.embeddingModels || [],
    embeddingProviderMap: (state) => state.payload.embeddingProviderMap || {},
    embeddingBackends: (state) => state.payload.embeddingBackends || {},
    customFamilies: (state) => state.payload.customFamilies || {},
    isStale: (state) => !state.loadedAt || Date.now() - state.loadedAt > STORAGE_TTL_MS,
    generalModelOptions() {
      const backends = this.llmBackends || {}
      return Object.entries(backends)
        .map(([providerKey, providerValue]) => {
          const providerLabel = prettifyProviderName(providerKey)
          const children = getBackendModelEntries(providerValue?.models).map(([modelKey, modelValue]) => ({
            value: modelKey,
            label: modelValue?.id || modelKey,
          }))
          if (children.length === 0) {
            return null
          }
          return {
            value: providerLabel,
            label: providerLabel,
            children,
          }
        })
        .filter(Boolean)
    },
    llmNodeOptions() {
      return this.generalModelOptions
    },
    embeddingModelOptions() {
      const backends = this.embeddingBackends || {}
      return Object.entries(backends)
        .map(([providerKey, providerValue]) => {
          const providerLabel = prettifyProviderName(providerKey)
          const children = getBackendModelEntries(providerValue?.models).map(([modelKey, modelValue]) => ({
            value: modelKey,
            label: modelValue?.id || modelKey,
            dimensions: modelValue?.dimensions ?? null,
            protocol: modelValue?.protocol || '',
          }))
          if (children.length === 0) {
            return null
          }
          return {
            value: providerKey,
            label: providerLabel,
            children,
          }
        })
        .filter(Boolean)
    },
  },
  actions: {
    setPayload(payload) {
      this.payload = {
        ...EMPTY_PAYLOAD,
        ...(payload || {}),
      }
      this.loaded = true
      this.loading = false
      this.loadError = ''
      this.loadedAt = Date.now()
      localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          payload: this.payload,
          cachedAt: this.loadedAt,
        })
      )
    },
    setPayloadFromSettings(settingPayload) {
      this.setPayload(buildCatalogPayload(settingPayload))
    },
    async ensureLoaded(force = false) {
      if (!force && this.loaded && !this.isStale) {
        return this.payload
      }
      if (this._loadingPromise) {
        return this._loadingPromise
      }

      this._loadingPromise = (async () => {
        this.loading = true
        try {
          const response = await settingAPI('get', {})
          this.setPayloadFromSettings(response.data)
          return this.payload
        } catch (error) {
          this.loadError = error?.message || 'load_failed'
          return this.payload
        } finally {
          this.loading = false
          this._loadingPromise = null
        }
      })()

      return this._loadingPromise
    },
    reset() {
      this.payload = {
        ...EMPTY_PAYLOAD,
      }
      this.loaded = false
      this.loading = false
      this.loadError = ''
      this.loadedAt = 0
      this._loadingPromise = null
      localStorage.removeItem(STORAGE_KEY)
    },
  },
})
