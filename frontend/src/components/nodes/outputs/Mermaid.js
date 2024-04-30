/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 02:46:33
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 02:46:52
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "output.mermaid",
    "has_inputs": true,
    "template": {
      "content": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "content",
        "display_name": "content",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "show_mermaid": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": true,
        "name": "show_mermaid",
        "display_name": "show_mermaid",
        "type": "bool",
        "clear_after_run": false,
        "list": false,
        "field_type": "checkbox"
      },
    }
  }
}