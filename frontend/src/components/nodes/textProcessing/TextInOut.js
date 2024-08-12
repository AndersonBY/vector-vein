/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 01:22:11
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-08-12 12:44:02
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
      "input_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "text",
        "options": [
          {
            "value": "text",
            "label": "text"
          },
          {
            "value": "number",
            "label": "number"
          },
        ],
        "name": "input_type",
        "display_name": "input_type",
        "type": "str",
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
      },
    }
  }
}