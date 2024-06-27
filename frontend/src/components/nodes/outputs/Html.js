/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 02:44:57
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 02:45:29
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "output.html",
    "has_inputs": true,
    "template": {
      "html_code": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "html_code",
        "display_name": "html_code",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "output": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output",
        "display_name": "output",
        "type": "str",
        "clear_after_run": false,
        "list": false,
        "field_type": "input",
        "is_output": true
      },
    }
  }
}