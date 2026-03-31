import { createTemplateData as createBaseTemplateData } from './OpenAI.js'

export function createTemplateData() {
  const template = createBaseTemplateData()
  template.task_name = 'llms.x_ai'
  template.template.llm_model.value = 'grok-2-1212'
  template.template.llm_model.options = [
    { value: 'grok-2-1212', label: 'grok-2-1212' },
    { value: 'grok-2-vision-1212', label: 'grok-2-vision-1212' },
  ]
  return template
}
