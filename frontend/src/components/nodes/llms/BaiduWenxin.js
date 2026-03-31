import { createTemplateData as createBaseTemplateData } from './OpenAI.js'

export function createTemplateData() {
  const template = createBaseTemplateData()
  template.task_name = 'llms.baidu_wenxin'
  template.template.llm_model.value = 'ernie-4.5'
  template.template.llm_model.options = [
    { value: 'ernie-3.5', label: 'ernie-3.5' },
    { value: 'ernie-4.0', label: 'ernie-4.0' },
    { value: 'ernie-4.5', label: 'ernie-4.5' },
  ]
  return template
}
