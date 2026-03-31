import { h } from 'vue'
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

import { FEATURE_FLAGS } from '@/config/featureFlags'
import { localNodeCategoryManifest, localPlannedNodeManifest } from '@/config/localNodeManifest'

export const nodeCategoryManifest = [
  { name: 'assistedNodes', icon: Helpcenter },
  { name: 'controlFlows', icon: CircleFourLine },
  { name: 'fileProcessing', icon: DocDetail },
  { name: 'imageGeneration', icon: Picture },
  { name: 'mediaEditing', icon: Effects },
  { name: 'llms', icon: Robot },
  { name: 'mediaProcessing', icon: FourArrows },
  { name: 'outputs', icon: Printer },
  { name: 'textProcessing', icon: EditOne },
  { name: 'tools', icon: Tool },
  { name: 'triggers', icon: ClickTap },
  { name: 'vectorDb', icon: CoordinateSystem },
  { name: 'relationalDb', icon: Data },
  { name: 'webCrawlers', icon: RadarThree },
  ...localNodeCategoryManifest,
]

export const nodeCategoryOptions = nodeCategoryManifest.map((item) => ({
  name: item.name,
  icon: h(item.icon),
}))

// Runtime registration still relies on import.meta.glob while the manifest
// acts as the single source of truth for desktop in-scope node metadata.
export const plannedNodeManifest = {
  ScheduleTrigger: {
    category: 'triggers',
    frontendComponent: 'ScheduleTrigger',
    backendTask: 'triggers.schedule_trigger',
    featureFlag: FEATURE_FLAGS.schedule,
    tags: ['schedule', 'trigger', 'cron'],
    status: 'available',
  },
  WorkflowSelector: {
    category: 'controlFlows',
    frontendComponent: 'WorkflowSelector',
    backendTask: 'control_flows.workflow_selector',
    featureFlag: null,
    tags: ['workflow', 'branch', 'selector'],
    status: 'available',
  },
  HumanFeedback: {
    category: 'controlFlows',
    frontendComponent: 'HumanFeedback',
    backendTask: 'control_flows.human_feedback',
    featureFlag: null,
    tags: ['approval', 'human-in-the-loop', 'pause'],
    status: 'available',
  },
  DocumentConvert: {
    category: 'fileProcessing',
    frontendComponent: 'DocumentConvert',
    backendTask: 'file_processing.document_convert',
    featureFlag: FEATURE_FLAGS.documentTools,
    tags: ['document', 'convert', 'office'],
    status: 'available',
  },
  CustomModel: {
    category: 'llms',
    frontendComponent: 'CustomModel',
    backendTask: 'llms.custom_model',
    featureFlag: FEATURE_FLAGS.experimentalLlmProviders,
    tags: ['llm', 'custom', 'provider'],
    status: 'available',
  },
  UniversalLlm: {
    category: 'llms',
    frontendComponent: 'UniversalLlm',
    backendTask: 'llms.universal_llm',
    featureFlag: FEATURE_FLAGS.experimentalLlmProviders,
    tags: ['llm', 'universal', 'endpoint'],
    status: 'available',
  },
  BaiduWenxin: {
    category: 'llms',
    frontendComponent: 'BaiduWenxin',
    backendTask: 'llms.baidu_wenxin',
    featureFlag: FEATURE_FLAGS.experimentalLlmProviders,
    tags: ['llm', 'baidu', 'wenxin'],
    status: 'available',
  },
  Stepfun: {
    category: 'llms',
    frontendComponent: 'Stepfun',
    backendTask: 'llms.stepfun',
    featureFlag: FEATURE_FLAGS.experimentalLlmProviders,
    tags: ['llm', 'stepfun'],
    status: 'available',
  },
  XAi: {
    category: 'llms',
    frontendComponent: 'XAi',
    backendTask: 'llms.x_ai',
    featureFlag: FEATURE_FLAGS.experimentalLlmProviders,
    tags: ['llm', 'xai', 'grok'],
    status: 'available',
  },
  ...localPlannedNodeManifest,
}
