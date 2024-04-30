/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 02:55:28
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 02:57:15
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "output.workflow_invoke_output",
    "has_inputs": false,
    "template": {
      "value": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": "",
        "name": "value",
        "display_name": "value",
        "type": "any",
        "list": false,
        "field_type": "textarea"
      },
      "display_name": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": "",
        "name": "display_name",
        "display_name": "display_name",
        "type": "any",
        "list": false,
        "field_type": "input"
      },
    }
  }
}