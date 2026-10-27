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
  template.template.llm_model.value = ''
  template.template.llm_model.options = []
  for (const [name, value] of [['model_preference', 'custom'], ['reasoning_effort', 'default']]) {
    template.template[name] = { name, display_name: name, value, show: false, type: 'str', field_type: 'input' }
  }
  return template
}
