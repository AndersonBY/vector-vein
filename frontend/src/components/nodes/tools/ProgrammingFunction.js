/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 00:33:34
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-29 18:39:55
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "tools.programming_function",
    "has_inputs": true,
    "template": {
      "language": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "python",
        "options": [
          {
            "value": "python",
            "label": "Python"
          },
        ],
        "name": "language",
        "display_name": "language",
        "type": "str",
        "list": false,
        "field_type": "select"
      },
      "code": {
        "required": true,
        "placeholder": "some code...",
        "show": false,
        "value": "",
        "name": "code",
        "display_name": "code",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "list_input": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": false,
        "name": "list_input",
        "display_name": "list_input",
        "type": "bool",
        "list": false,
        "field_type": "checkbox"
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
        "is_output": true,
      },
      "console_msg": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "console_msg",
        "display_name": "console_msg",
        "type": "str",
        "list": false,
        "field_type": "textarea",
        "is_output": true,
      },
      "error_msg": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "error_msg",
        "display_name": "error_msg",
        "type": "str",
        "list": false,
        "field_type": "textarea",
        "is_output": true,
      },
      "files": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "files",
        "display_name": "files",
        "type": "str",
        "list": false,
        "field_type": "textarea",
        "is_output": true,
      }
    }
  }
}