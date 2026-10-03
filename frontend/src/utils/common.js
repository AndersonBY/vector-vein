/**
 * @Author: Bi Ying
 * @Date:   2022-07-19 14:45:35
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-08-07 18:00:26
 */
import { h, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { TypographyText, Tag, Flex } from 'ant-design-vue'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from "@/stores/userSettings"

export const currentTourVersion = 1

const flattenModelOptions = (options, showProvider = true, valueType = 'String') => {
  const flattenedOptions = [];

  options.forEach(option => {
    if (option.children && option.children.length > 0) {
      option.children.forEach(child => {
        const optionLabelText = option.labelText ?? option.label
        let valueWithProvider = `${option.value}⋄${child.value}`
        if (valueType === 'Array') {
          valueWithProvider = [option.value, child.value]
        }
        flattenedOptions.push({
          label: showProvider ? `${optionLabelText}/${child.label}` : child.label,
          value: showProvider ? valueWithProvider : child.value,
        });
      });
    }
  });

  return flattenedOptions;
}

const CHAT_PROVIDER_LABEL_MAP = {
  anthropic: 'Anthropic',
  baichuan: 'Baichuan',
  deepseek: 'DeepSeek',
  ernie: 'Ernie',
  gemini: 'Gemini',
  groq: 'Groq',
  minimax: 'MiniMax',
  mistral: 'Mistral',
  moonshot: 'Moonshot',
  openai: 'OpenAI',
  qwen: 'Qwen',
  stepfun: 'StepFun',
  xai: 'xAI',
  xiaomi: 'Xiaomi',
  yi: 'Yi',
  zhipuai: 'ZhiPuAI',
}

const getDynamicChatModelOptions = (settingData) => {
  const backends = settingData?.llm_settings?.backends
  if (!backends || typeof backends !== 'object' || Array.isArray(backends)) {
    return []
  }

  return Object.entries(backends)
    .filter(([providerKey]) => providerKey !== 'local')
    .map(([providerKey, providerValue]) => {
      const models = providerValue?.models
      if (!models || typeof models !== 'object' || Array.isArray(models)) {
        return null
      }

      const children = Object.entries(models)
        .filter(([, model]) => model?.enabled !== false)
        .reverse()
        .map(([modelKey, modelValue]) => ({
          value: modelKey,
          label: modelValue?.id || modelKey,
        }))

      if (children.length === 0) {
        return null
      }

      const providerLabel = CHAT_PROVIDER_LABEL_MAP[providerKey] || providerKey
      return {
        value: providerLabel,
        label: providerLabel,
        children,
      }
    })
    .filter(Boolean)
}

export const getChatModelOptions = (flat = false) => {
  const userSettings = useUserSettingsStore()
  const { setting } = storeToRefs(userSettings)
  const nonLocalModels = getDynamicChatModelOptions(setting.value.data)
  const customModels = Object.entries(setting.value.data?.custom_llms || {}).map(([family, models]) => {
    const children = models.map((model) => ({
      value: model,
      label: model,
    }))
    return {
      value: '_local__' + family,
      label: h(TypographyText, {}, () =>
        h(Flex, { gap: 'small', style: 'display: inline-flex;' }, () => [
          family,
          h(Tag, { color: 'green', bordered: false }, () => 'Local')
        ])
      ),
      labelText: family,
      children: children,
    }
  })
  const chatModels = nonLocalModels.concat(customModels)
  if (flat) {
    return flattenModelOptions(chatModels, true)
  } else {
    return chatModels
  }
}

export const statusColorMap = {
  'INVALID': 'red',
  'EXPIRED': 'orange',
  'DELETING': 'red',
  'DELETED': 'orange',
  'VALID': 'green',
  'ERROR': 'red',
  'CREATING': 'blue',
  'NOT_STARTED': 'default',
  'QUEUED': 'blue',
  'RUNNING': 'cyan',
  'FINISHED': 'green',
  'FAILED': 'red',
  'IN': 'red',
  'PR': 'blue',
  'VA': 'green',
  'DE': 'orange',
  'EX': 'orange',
}

export const backgroundColors = [
  '#FC8DCA',
  '#C37EDB',
  '#B7A6F6',
  '#88A3E2',
  '#AAECFC',
  '#5C4B51',
  '#8CBEB2',
  '#F2EBBF',
  '#F3B562',
  '#F06060',
]

export const modelTagBackgroundColorMap = {
  'gpt-35-turbo': '#19c37d',
  'gpt-4': '#000',
  'gpt-4o': '#000',
  'gpt-4o-mini': '#000',
  'abab5.5-chat': '#eb3368',
  'abab6-chat': '#eb3368',
  'glm-3-turbo': '#3875F6',
  'glm-4': '#3875F6',
  'glm-4-0520': '#3875F6',
  'glm-4-air': '#3875F6',
  'glm-4-airx': '#3875F6',
  'glm-4-flash': '#3875F6',
  'glm-4-plus': '#3875F6',
  'glm-4v-plus': '#3875F6',
  'qwen1.5-7b-chat': '#5444CB',
  'qwen1.5-14b-chat': '#5444CB',
  'qwen1.5-32b-chat': '#5444CB',
  'qwen1.5-72b-chat': '#5444CB',
  'qwen1.5-110b-chat': '#5444CB',
  'qwen2-72b-instruct': '#5444CB',
  'qwen2.5-7b-instruct': '#5444CB',
  'qwen2.5-14b-instruct': '#5444CB',
  'qwen2.5-72b-instruct': '#5444CB',
  'moonshot-v1-8k': '#0B0C0F',
  'moonshot-v1-32k': '#0B0C0F',
  'moonshot-v1-128k': '#0B0C0F',
  'claude-3-haiku-20240307': '#CA9F7B',
  'claude-3-opus-20240229': '#CA9F7B',
  'claude-3-sonnet-20240229': '#CA9F7B',
  'claude-3-5-sonnet-20241022': '#CA9F7B',
  'claude-3-5-haiku-20241022': '#CA9F7B',
  'mixtral-8x7b': '#FF7000',
  'mistral-small': '#FF7000',
  'mistral-medium': '#FF7000',
  'mistral-large': '#FF7000',
  'deepseek-chat': '#556AF5',
  'deepseek-coder': '#556AF5',
  'yi-large': '#133426',
  'yi-large-turbo': '#133426',
  'yi-medium': '#133426',
  'yi-medium-200k': '#133426',
  'yi-spark': '#133426',
  'yi-lightning': '#133426',
  'grok-beta': '#000000',
}

export const modelProviderTagBgColorMap = {
  'AliyunQwen': '#5444CB',
  'Baichuan': '#EE8137',
  'ChatGLM': '#3875F6',
  'Claude': '#CA9F7B',
  'Anthropic': '#CA9F7B',
  'Deepseek': '#556AF5',
  'Gemini': '#1D43F5',
  'Groq': '#f55036',
  'LingYiWanWu': '#133426',
  'LocalLlm': '#0aafc8',
  'MiniMax': '#eb3368',
  'Mistral': '#FF7000',
  'Moonshot': '#0B0C0F',
  'OpenAI': '#000',
  'XAi': '#000000',
}

export const databaseColumnTypes = [
  'INTEGER',
  'REAL',
  'TEXT',
  'VARCHAR',
  'BOOLEAN',
  'DATETIME',
]

export const websiteBase = computed(() => {
  return 'https://' + (useUserSettingsStore().setting.data.website_domain ?? 'vectorvein.ai')
})

export const defaultSettings = {
  'en-US': {
    system_prompt: 'You are an AI assistant from VectorVein(Chinese name: 向量脉络) and you can use automated workflows to do all kinds of tasks.\nNow the time is {{time}}.',
    auto_run_workflow: false,
    opening_dialog: {
      text: 'Hello! How can I help you?',
      questions: [],
    }
  },
  'zh-CN': {
    system_prompt: '你是来自向量脉络的AI助手，你可以使用自动化工作流来完成各种任务。\n现在的时间是 {{time}}。',
    auto_run_workflow: false,
    opening_dialog: {
      text: '您好！有什么可以帮助您的？',
      questions: [],
    }
  }
}

export const agentVoiceOptions = computed(() => {
  const { t, te } = useI18n()
  const userSettings = useUserSettingsStore()
  const { setting } = storeToRefs(userSettings)
  const reechoVoices = setting.value.data?.tts?.reecho?.voices ?? []
  const azureVoices = setting.value.data?.tts?.azure?.voices ?? []
  const options = [
    {
      value: 'openai',
      label: 'openai',
      children: [
        {
          "value": "alloy",
          "label": "alloy",
        },
        {
          "value": "echo",
          "label": "echo",
        },
        {
          "value": "fable",
          "label": "fable",
        },
        {
          "value": "onyx",
          "label": "onyx",
        },
        {
          "value": "nova",
          "label": "nova",
        },
        {
          "value": "shimmer",
          "label": "shimmer",
        },
      ]
    },
    {
      value: 'minimax',
      label: 'minimax',
      children: [
        {
          "value": "male-qn-qingse",
          "label": "male-qn-qingse",
        },
        {
          "value": "male-qn-jingying",
          "label": "male-qn-jingying",
        },
        {
          "value": "male-qn-badao",
          "label": "male-qn-badao",
        },
        {
          "value": "male-qn-daxuesheng",
          "label": "male-qn-daxuesheng",
        },
        {
          "value": "female-shaonv",
          "label": "female-shaonv",
        },
        {
          "value": "female-yujie",
          "label": "female-yujie",
        },
        {
          "value": "female-chengshu",
          "label": "female-chengshu",
        },
        {
          "value": "female-tianmei",
          "label": "female-tianmei",
        },
        {
          "value": "presenter_male",
          "label": "presenter_male",
        },
        {
          "value": "presenter_female",
          "label": "presenter_female",
        },
        {
          "value": "audiobook_male_1",
          "label": "audiobook_male_1",
        },
        {
          "value": "audiobook_male_2",
          "label": "audiobook_male_2",
        },
        {
          "value": "audiobook_female_1",
          "label": "audiobook_female_1",
        },
        {
          "value": "audiobook_female_2",
          "label": "audiobook_female_2",
        },
        {
          "value": "male-qn-qingse-jingpin",
          "label": "male-qn-qingse-jingpin",
        },
        {
          "value": "male-qn-jingying-jingpin",
          "label": "male-qn-jingying-jingpin",
        },
        {
          "value": "male-qn-badao-jingpin",
          "label": "male-qn-badao-jingpin",
        },
        {
          "value": "male-qn-daxuesheng-jingpin",
          "label": "male-qn-daxuesheng-jingpin",
        },
        {
          "value": "female-shaonv-jingpin",
          "label": "female-shaonv-jingpin",
        },
        {
          "value": "female-yujie-jingpin",
          "label": "female-yujie-jingpin",
        },
        {
          "value": "female-chengshu-jingpin",
          "label": "female-chengshu-jingpin",
        },
        {
          "value": "female-tianmei-jingpin",
          "label": "female-tianmei-jingpin",
        },
      ]
    },
    {
      value: 'piper',
      label: 'piper',
      children: [
        {
          value: 'default',
          label: 'default',
        }
      ]
    },
    {
      value: 'reecho',
      label: 'Reecho',
      children: reechoVoices.map((voice) => {
        return {
          value: voice.voice_id,
          label: voice.voice_label,
        }
      })
    },
    {
      value: 'azure',
      label: 'Azure',
      children: azureVoices.map((voice) => {
        return {
          value: voice.voice_id,
          label: voice.voice_label,
        }
      })
    },
  ]
  options.forEach((provider) => {
    provider.children.forEach((voice) => {
      if (te(`voiceOptions.${provider.value}_${voice.value}`) === false) return
      voice.label = t(`voiceOptions.${provider.value}_${voice.value}`)
    })
  })
  return options
})
