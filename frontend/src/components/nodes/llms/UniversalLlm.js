import { createTemplateData as createBaseTemplateData } from './OpenAI.js'

export function createTemplateData() {
  const template = createBaseTemplateData()
  template.task_name = 'llms.universal_llm'
  template.template.model_provider = {
    required: false,
    placeholder: '',
    show: false,
    value: 'OpenAI',
    options: [],
    name: 'model_provider',
    display_name: 'model_provider',
    type: 'str',
    list: true,
    field_type: 'select',
  }
  template.template.llm_model.value = 'gpt-4o-mini'
  template.template.llm_model.options = []
  return template
}
