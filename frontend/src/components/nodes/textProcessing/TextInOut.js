/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 01:22:11
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 01:22:48
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "text_processing.text_in_out",
    "has_inputs": true,
    "template": {
      "text": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": "",
        "name": "text",
        "display_name": "text",
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
        "field_type": "",
        "is_output": true
      },
    }
  }
}