/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 14:54:35
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 14:56:23
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "control_flows.empty",
    "has_inputs": true,
    "template": {
      "input": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "input",
        "display_name": "input",
        "type": "str",
        "list": false,
        "field_type": "input"
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