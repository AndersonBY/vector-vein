/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 15:48:05
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 15:50:16
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "control_flows.random_choice",
    "has_inputs": true,
    "template": {
      "input": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": [],
        "name": "input",
        "display_name": "input",
        "type": "list",
        "list": false,
        "field_type": "select"
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
      }
    }
  }
}