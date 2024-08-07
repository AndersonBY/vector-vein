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
    ]
  },
  {
    label: "MiniMax",
    value: "MiniMax",
    children: [
      {
        label: "abab5.5-chat",
        value: "abab5.5-chat",
      },
      {
        label: "abab6-chat",
        value: "abab6-chat",
      },
      {
        label: "abab6.5s-chat",
        value: "abab6.5s-chat",
      },
    ]
  },
  {
    label: "ZhiPuAI",
    value: "ZhiPuAI",
    children: [
      {
        label: "glm-3-turbo",
        value: "glm-3-turbo",
      },
      {
        label: "glm-4",
        value: "glm-4",
      },
      {
        label: "glm-4-0520",
        value: "glm-4-0520",
      },
      {
        label: "glm-4-air",
        value: "glm-4-air",
      },
      {
        label: "glm-4-airx",
        value: "glm-4-airx",
      },
      {
        label: "glm-4-flash",
        value: "glm-4-flash",
      },
      {
        label: "glm-4v",
        value: "glm-4v",
      },
    ]
  },
  {
    label: "Qwen",
    value: "Qwen",
    children: [
      {
        label: "qwen1.5-7b-chat",
        value: "qwen1.5-7b-chat",
      },
      {
        label: "qwen1.5-14b-chat",
        value: "qwen1.5-14b-chat",
      },
      {
        label: "qwen1.5-32b-chat",
        value: "qwen1.5-32b-chat",
      },
      {
        label: "qwen1.5-72b-chat",
        value: "qwen1.5-72b-chat",
      },
      {
        label: "qwen1.5-110b-chat",
        value: "qwen1.5-110b-chat",
      },
      {
        label: "qwen2-72b-instruct",
        value: "qwen2-72b-instruct",
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
    ]
  },
  {
    label: "Anthropic",
    value: "Anthropic",
    children: [
      {
        label: "claude-3-haiku",
        value: "claude-3-haiku-20240307",
      },
      {
        label: "claude-3-sonnet",
        value: "claude-3-sonnet-20240229",
      },
      {
        label: "claude-3-opus",
        value: "claude-3-opus-20240229",
      },
      {
        label: "claude-3-5-sonnet",
        value: "claude-3-5-sonnet-20240620",
      },
    ]
  },
  {
    label: "Mistral",
    value: "Mistral",
    children: [
      {
        label: "mixtral-8x22b",
        value: "mixtral-8x22b",
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
        label: "deepseek-chat",
        value: "deepseek-chat",
      },
      {
        label: "deepseek-coder",
        value: "deepseek-coder",
      },
    ]
  },
  {
    label: "Yi",
    value: "Yi",
    children: [
      {
        label: "yi-large",
        value: "yi-large",
      },
      {
        label: "yi-large-turbo",
        value: "yi-large-turbo",
      },
      {
        label: "yi-medium",
        value: "yi-medium",
      },
      {
        label: "yi-medium-200k",
        value: "yi-medium-200k",
      },
      {
        label: "yi-spark",
        value: "yi-spark",
      },
      // {
      //   label: "yi-vision",
      //   value: "yi-vision",
      // },
    ]
  },
  {
    label: "Groq",
    value: "Groq",
    children: [
      {
        label: "mixtral-8x7b-32768",
        value: "mixtral-8x7b-32768",
      },
      {
        label: "llama3-70b-8192",
        value: "llama3-70b-8192",
      },
      {
        label: "llama3-8b-8192",
        value: "llama3-8b-8192",
      },
      {
        label: "gemma-7b-it",
        value: "gemma-7b-it",
      },
    ]
  },
  {
    label: "Gemini",
    value: "Gemini",
    children: [
      {
        label: "gemini-1.5-pro",
        value: "gemini-1.5-pro",
      },
      {
        label: "gemini-1.5-flash",
        value: "gemini-1.5-flash",
      },
    ]
  },
]

export const getChatModelOptions = (flat = false) => {
  const userSettings = useUserSettingsStore()
  const { setting } = storeToRefs(userSettings)
  const chatModels = nonLocalChatModelOptions.concat(setting.value.data?.local_llms?.map((provider) => {
    return {
      value: '_local__' + provider.model_family,
      label: h(TypographyText, {}, () =>
        h(Flex, { gap: 'small', style: 'display: inline-flex;' }, () => [
          provider.model_family,
          h(Tag, { color: 'green', bordered: false }, () => 'Local')
        ])
      ),
      children: provider.models.map((model) => ({
        value: model.model_id,
        label: model.model_label,
      })),
    }
  }))
  if (flat) {
    return chatModels.map((item) => item.children).flat()
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
  'abab5.5-chat': '#eb3368',
  'abab6-chat': '#eb3368',
  'glm-3-turbo': '#3875F6',
  'glm-4': '#3875F6',
  'glm-4-0520': '#3875F6',
  'glm-4-air': '#3875F6',
  'glm-4-airx': '#3875F6',
  'glm-4-flash': '#3875F6',
  'qwen1.5-7b-chat': '#5444CB',
  'qwen1.5-14b-chat': '#5444CB',
  'qwen1.5-32b-chat': '#5444CB',
  'qwen1.5-72b-chat': '#5444CB',
  'qwen1.5-110b-chat': '#5444CB',
  'qwen2-72b-instruct': '#5444CB',
  'moonshot-v1-8k': '#0B0C0F',
  'moonshot-v1-32k': '#0B0C0F',
  'moonshot-v1-128k': '#0B0C0F',
  'claude-3-haiku-20240307': '#CA9F7B',
  'claude-3-opus-20240229': '#CA9F7B',
  'claude-3-sonnet-20240229': '#CA9F7B',
  'claude-3-5-sonnet-20240620': '#CA9F7B',
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
    system_prompt: 'You are an AI assistant from VectorVein(Chinese name: 向量脉络) and you can use automated workflows to do all kinds of tasks.',
    auto_run_workflow: false,
    opening_dialog: {
      text: 'Hello! How can I help you?',
      questions: [],
    }
  },
  'zh-CN': {
    system_prompt: '你是来自向量脉络的AI助手，你可以使用自动化工作流来完成各种任务。',
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