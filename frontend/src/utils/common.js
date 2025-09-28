/**
 * @Author: Bi Ying
 * @Date:   2022-07-19 14:45:35
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-08-07 18:00:26
 */
import { h, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { TypographyText, Tag, Flex } from 'ant-design-vue'
import {
  Tool,
  Data,
  Robot,
  EditOne,
  Printer,
  Effects,
  Picture,
  ClickTap,
  DocDetail,
  FourArrows,
  Helpcenter,
  RadarThree,
  CircleFourLine,
  CoordinateSystem,
} from '@icon-park/vue-next'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from "@/stores/userSettings"

export const currentTourVersion = 1

export const nonLocalChatModelOptions = [
  {
    label: "OpenAI",
    value: "OpenAI",
    children: [
      {
        label: "gpt-35-turbo",
        value: "gpt-35-turbo",
      },
      {
        label: "gpt-4",
        value: "gpt-4",
      },
      {
        label: "gpt-4o",
        value: "gpt-4o",
      },
      {
        label: "gpt-4o-mini",
        value: "gpt-4o-mini",
      },
      {
        label: "gpt-4.1",
        value: "gpt-4.1",
      },
      {
        label: "o1-mini",
        value: "o1-mini",
      },
      {
        label: "o1-preview",
        value: "o1-preview",
      },
      {
        label: "o3-mini",
        value: "o3-mini",
      },
      {
        label: "o3-mini-high",
        value: "o3-mini-high",
      },
      {
        label: "o4-mini",
        value: "o4-mini",
      },
      {
        label: "o4-mini-high",
        value: "o4-mini-high",
      },
      {
        label: "gpt-5",
        value: "gpt-5",
      },
      {
        label: "gpt-5-high",
        value: "gpt-5-high",
      },
      {
        label: "gpt-5-mini",
        value: "gpt-5-mini",
      },
      {
        label: "gpt-5-nano",
        value: "gpt-5-nano",
      },
      {
        label: "gpt-5-chat-latest",
        value: "gpt-5-chat-latest",
      },
      {
        label: "gpt-5-codex",
        value: "gpt-5-codex",
      },
    ]
  },
  {
    label: "MiniMax",
    value: "MiniMax",
    children: [
      {
        label: "abab6.5s-chat",
        value: "abab6.5s-chat",
      },
      {
        label: "MiniMax-Text-01",
        value: "MiniMax-Text-01",
      },
      {
        label: "MiniMax-M1",
        value: "MiniMax-M1",
      },
    ]
  },
  {
    label: "ZhiPuAI",
    value: "ZhiPuAI",
    children: [
      {
        "value": "glm-4.5",
        "label": "glm-4.5"
      },
      {
        "value": "glm-4.5-x",
        "label": "glm-4.5-x"
      },
      {
        "value": "glm-4.5-air",
        "label": "glm-4.5-air",
      },
      {
        "value": "glm-4.5-airx",
        "label": "glm-4.5-airx",
      },
      {
        "value": "glm-4.5-flash",
        "label": "glm-4.5-flash",
      },
      {
        "value": "glm-4-plus",
        "label": "glm-4-plus",
      },
      {
        label: "glm-4-long",
        value: "glm-4-long",
      },
      {
        label: "glm-zero-preview",
        value: "glm-zero-preview",
      },
    ]
  },
  {
    label: "Qwen",
    value: "Qwen",
    children: [
      {
        "value": "qwen3-max",
        "label": "qwen3-max",
      },
      {
        "value": "qwen3-235b-a22b-instruct-2507",
        "label": "qwen3-235b-a22b-instruct-2507",
      },
      {
        "value": "qwen3-coder-480b-a35b-instruct",
        "label": "qwen3-coder-480b-a35b-instruct",
      },
      {
        "value": "qwen3-235b-a22b",
        "label": "qwen3-235b-a22b",
      },
      {
        "value": "qwen3-235b-a22b-thinking",
        "label": "qwen3-235b-a22b-thinking",
      },
      {
        "value": "qwen3-next-80b-a3b-thinking",
        "label": "qwen3-next-80b-a3b-thinking",
      },
      {
        "value": "qwen3-next-80b-a3b-instruct",
        "label": "qwen3-next-80b-a3b-instruct",
      },
      {
        "value": "qwen3-vl-plus",
        "label": "qwen3-vl-plus",
      },
      {
        "value": "qwen3-coder-plus",
        "label": "qwen3-coder-plus",
      },
      {
        "value": "qwen3-coder-flash",
        "label": "qwen3-coder-flash",
      },
      {
        "value": "qwen3-32b",
        "label": "qwen3-32b",
      },
      {
        "value": "qwen3-32b-thinking",
        "label": "qwen3-32b-thinking",
      },
      {
        "value": "qwen3-30b-a3b",
        "label": "qwen3-30b-a3b",
      },
      {
        "value": "qwen3-30b-a3b-thinking",
        "label": "qwen3-30b-a3b-thinking",
      },
      {
        "value": "qwen3-14b",
        "label": "qwen3-14b",
      },
      {
        "value": "qwen3-14b-thinking",
        "label": "qwen3-14b-thinking",
      },
      {
        "value": "qwen3-8b",
        "label": "qwen3-8b",
      },
      {
        "value": "qwen3-8b-thinking",
        "label": "qwen3-8b-thinking",
      },
      {
        "value": "qwen3-4b",
        "label": "qwen3-4b",
      },
      {
        "value": "qwen3-4b-thinking",
        "label": "qwen3-4b-thinking",
      },
      {
        "value": "qwen3-1.7b",
        "label": "qwen3-1.7b",
      },
      {
        "value": "qwen3-1.7b-thinking",
        "label": "qwen3-1.7b-thinking",
      },
      {
        "value": "qwen3-0.6b",
        "label": "qwen3-0.6b",
      },
      {
        "value": "qwen3-0.6b-thinking",
        "label": "qwen3-0.6b-thinking",
      },
      {
        "value": "qwen2.5-7b-instruct",
        "label": "qwen2.5-7b-instruct"
      },
      {
        "value": "qwen2.5-14b-instruct",
        "label": "qwen2.5-14b-instruct"
      },
      {
        "value": "qwen2.5-32b-instruct",
        "label": "qwen2.5-32b-instruct"
      },
      {
        "value": "qwq-32b",
        "label": "qwq-32b"
      },
      {
        "value": "qwen2.5-coder-32b-instruct",
        "label": "qwen2.5-coder-32b-instruct"
      },
      {
        "value": "qwen2.5-72b-instruct",
        "label": "qwen2.5-72b-instruct"
      },
    ]
  },
  {
    label: "Moonshot",
    value: "Moonshot",
    children: [
      {
        label: "moonshot-v1-8k",
        value: "moonshot-v1-8k",
      },
      {
        label: "moonshot-v1-32k",
        value: "moonshot-v1-32k",
      },
      {
        label: "moonshot-v1-128k",
        value: "moonshot-v1-128k",
      },
      {
        label: "kimi-latest",
        value: "kimi-latest",
      },
      {
        label: "kimi-k2-0905-preview",
        value: "kimi-k2-0905-preview",
      },
      {
        label: "kimi-k2-turbo-preview",
        value: "kimi-k2-turbo-preview",
      },
    ]
  },
  {
    label: "Anthropic",
    value: "Anthropic",
    children: [
      {
        label: "claude-3-5-sonnet",
        value: "claude-3-5-sonnet-20241022",
      },
      {
        label: "claude-3-5-haiku",
        value: "claude-3-5-haiku-20241022",
      },
      {
        label: "claude-3-7-sonnet",
        value: "claude-3-7-sonnet-20250219",
      },
      {
        label: "claude-3-7-sonnet-thinking",
        value: "claude-3-7-sonnet-thinking",
      },
      {
        label: "claude-sonnet-4-20250514",
        value: "claude-sonnet-4-20250514",
      },
      {
        label: "claude-sonnet-4-20250514-thinking",
        value: "claude-sonnet-4-20250514-thinking",
      },
      {
        label: "claude-opus-4-20250514",
        value: "claude-opus-4-20250514",
      },
      {
        label: "claude-opus-4-20250514-thinking",
        value: "claude-opus-4-20250514-thinking",
      },
    ]
  },
  {
    label: "Mistral",
    value: "Mistral",
    children: [
      {
        label: "mixtral-8x7b",
        value: "mixtral-8x7b",
      },
      {
        label: "mistral-small",
        value: "mistral-small",
      },
      {
        label: "mistral-medium",
        value: "mistral-medium",
      },
      {
        label: "mistral-large",
        value: "mistral-large",
      },
    ]
  },
  {
    label: "DeepSeek",
    value: "DeepSeek",
    children: [
      {
        label: "deepseek-v3",
        value: "deepseek-chat",
      },
      {
        label: "deepseek-r1",
        value: "deepseek-reasoner",
      },
    ]
  },
  {
    label: "Yi",
    value: "Yi",
    children: [
      {
        label: "yi-lightning",
        value: "yi-lightning",
      },
    ]
  },
  {
    label: "Gemini",
    value: "Gemini",
    children: [
      {
        label: "gemini-2.5-pro",
        value: "gemini-2.5-pro",
      },
      {
        label: "gemini-2.5-flash",
        value: "gemini-2.5-flash",
      },
    ]
  },
]

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

export const getChatModelOptions = (flat = false) => {
  const userSettings = useUserSettingsStore()
  const { setting } = storeToRefs(userSettings)
  const customModels = Object.entries(setting.value.data?.custom_llms).map(([family, models]) => {
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
  const chatModels = nonLocalChatModelOptions.concat(customModels)
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

export const nodeCategoryOptions = [
  {
    name: 'assistedNodes',
    icon: h(Helpcenter),
  },
  {
    name: 'controlFlows',
    icon: h(CircleFourLine),
  },
  {
    name: 'fileProcessing',
    icon: h(DocDetail),
  },
  {
    name: 'imageGeneration',
    icon: h(Picture),
  },
  {
    name: 'mediaEditing',
    icon: h(Effects),
  },
  {
    name: 'llms',
    icon: h(Robot),
  },
  {
    name: 'mediaProcessing',
    icon: h(FourArrows),
  },
  {
    name: 'outputs',
    icon: h(Printer),
  },
  {
    name: 'textProcessing',
    icon: h(EditOne),
  },
  {
    name: 'tools',
    icon: h(Tool),
  },
  {
    name: 'triggers',
    icon: h(ClickTap),
  },
  {
    name: 'vectorDb',
    icon: h(CoordinateSystem),
  },
  {
    name: 'relationalDb',
    icon: h(Data),
  },
  {
    name: 'webCrawlers',
    icon: h(RadarThree),
  },
]

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