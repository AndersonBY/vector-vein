/**
 * @Author: Claude Assistant
 * @Date:   2024-02-22 06:56:00
 * @Last Modified by:   Claude Assistant
 * @Last Modified time: 2024-02-22 06:56:00
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "text_processing.regex_extract",
    "has_inputs": true,
    "template": {
      "text": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "text",
        "display_name": "text",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "pattern": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "```.*?\\n(.*?)\\n```",
        "name": "pattern",
        "display_name": "pattern",
        "type": "str",
        "list": false,
        "field_type": "input",
        "has_tooltip": true,
      },
      "output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": [],
        "name": "output",
        "display_name": "output",
        "type": "list",
        "list": true,
        "field_type": "textarea",
        "is_output": true
      }
    }
  }
}