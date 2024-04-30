/**
 * @Author: Bi Ying
 * @Date:   2024-04-14 22:57:39
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 00:25:50
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "triggers.button_trigger",
    "has_inputs": false,
    "template": {
      "button_text": {
        "required": true,
        "placeholder": "Run",
        "show": false,
        "value": "",
        "name": "button_text",
        "display_name": "button_text",
        "type": "str",
        "list": false,
        "field_type": "input"
      },
    }
  }
}