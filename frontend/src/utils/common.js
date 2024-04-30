/**
 * @Author: Bi Ying
 * @Date:   2022-07-19 14:45:35
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-05-01 02:30:09
 */
import { h } from 'vue'
import {
  Helpcenter,
  CircleFourLine,
  DocDetail,
  Picture,
  Robot,
  FourArrows,
  Printer,
  Data,
  EditOne,
  Tool,
  ClickTap,
  CoordinateSystem,
  RadarThree,
} from '@icon-park/vue-next'

export const currentTourVersion = 1

export const chatModelOptions = [
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
    ]
  },
]

const flattenModelOptions = (options, showProvider = true) => {
  const flattenedOptions = [];

  options.forEach(option => {
    if (option.children && option.children.length > 0) {
      option.children.forEach(child => {
        flattenedOptions.push({
          label: showProvider ? `${option.label}/${child.label}` : child.label,
          value: showProvider ? `${option.value}/${child.value}` : child.value,
        });
      });
    }
  });

  return flattenedOptions;
}

export const flattenedChatModelOptions = flattenModelOptions(chatModelOptions)


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