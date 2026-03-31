import { useModelCatalogStore } from "@/stores/modelCatalog"

export const LLM_NODE_PROVIDER_MAP = {
  OpenAI: "OpenAI",
  ChatGLM: "ZhiPuAI",
  Gemini: "Gemini",
  AliyunQwen: "Qwen",
  Claude: "Anthropic",
  Deepseek: "DeepSeek",
  MiniMax: "MiniMax",
  Moonshot: "Moonshot",
  LingYiWanWu: "Yi",
  XAi: "xAI",
  Stepfun: "StepFun",
  BaiduWenxin: "Ernie",
  Groq: "Groq",
  Baichuan: "Baichuan",
}

export function mergeTemplateIntoFields(fieldsData, templateData) {
  Object.entries(templateData.template).forEach(([key, value]) => {
    fieldsData.value[key] = fieldsData.value[key] || value
    if (value.is_output) {
      fieldsData.value[key].is_output = true
    }
  })
}

export function findProviderChildren(optionGroups, provider) {
  const providerEntry = (optionGroups || []).find((item) => item.value === provider)
  return providerEntry ? providerEntry.children || [] : []
}

export function flattenProviderModelOptions(optionGroups) {
  const flattened = []
  for (const provider of optionGroups || []) {
    for (const child of provider.children || []) {
      flattened.push({
        value: `${provider.value}/${child.value}`,
        label: `${provider.value}/${child.label}`,
      })
    }
  }
  return flattened
}

export async function hydrateTemplateModelField(fieldsData, provider, fieldName = "llm_model") {
  const store = useModelCatalogStore()
  await store.ensureLoaded()

  if (!fieldsData?.value?.[fieldName] || !provider) {
    return
  }

  const providerOptions = findProviderChildren(store.generalModelOptions, provider)
  if (providerOptions.length === 0) {
    return
  }

  fieldsData.value[fieldName].options = providerOptions.map((item) => ({
    value: item.value,
    label: item.label,
  }))

  const currentValue = fieldsData.value[fieldName].value
  const currentValid = providerOptions.some((item) => item.value === currentValue)
  if (!currentValid) {
    fieldsData.value[fieldName].value = providerOptions[0].value
  }
}

export async function hydrateFlattenedModelField(fieldsData, fieldName = "llm_model") {
  const store = useModelCatalogStore()
  await store.ensureLoaded()

  if (!fieldsData?.value?.[fieldName]) {
    return
  }

  const flattened = flattenProviderModelOptions(store.generalModelOptions)
  if (flattened.length === 0) {
    return
  }

  fieldsData.value[fieldName].options = flattened
  const currentValue = fieldsData.value[fieldName].value
  const currentValid = flattened.some((item) => item.value === currentValue)
  if (!currentValid) {
    fieldsData.value[fieldName].value = flattened[0].value
  }
}
