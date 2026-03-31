import { createTemplateData as createBaseTemplateData } from './OpenAI.js'

export function createTemplateData() {
  const template = createBaseTemplateData()
  template.task_name = 'llms.stepfun'
  template.template.llm_model.value = 'step-2-16k'
  template.template.llm_model.options = [
    { value: 'step-1v-8k', label: 'step-1v-8k' },
    { value: 'step-2-16k', label: 'step-2-16k' },
  ]
  return template
}
