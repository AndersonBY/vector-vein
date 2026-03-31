import { createTemplateData as createBaseTemplateData } from './OpenAI.js'

export function createTemplateData() {
  const template = createBaseTemplateData()
  template.task_name = 'llms.custom_model'
  template.template.model_family = {
    required: false,
    placeholder: '',
    show: false,
    value: '',
    options: [],
    name: 'model_family',
    display_name: 'model_family',
    type: 'str',
    clear_after_run: false,
    list: true,
    field_type: 'select',
  }
  template.template.llm_model.options = []
  return template
}
