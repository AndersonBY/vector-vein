/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 01:08:13
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 16:04:20
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "text_processing.template_compose",
    "has_inputs": true,
    "template": {
      "template": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "template",
        "display_name": "template",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output",
        "display_name": "output",
        "type": "str",
        "list": false,
        "field_type": "textarea",
        "is_output": true
      }
    }
  }
}