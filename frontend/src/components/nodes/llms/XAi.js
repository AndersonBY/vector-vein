import { createTemplateData as createBaseTemplateData } from './OpenAI.js'

export function createTemplateData() {
  const template = createBaseTemplateData()
  template.task_name = 'llms.x_ai'
  template.template.llm_model.value = ''
  template.template.llm_model.options = []
  return template
}
