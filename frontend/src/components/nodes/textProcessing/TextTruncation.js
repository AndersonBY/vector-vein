/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 01:49:59
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 01:51:44
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "text_processing.text_truncation",
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
      "truncate_method": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "general",
        "options": [
          {
            "value": "general",
            "label": "general"
          },
          {
            "value": "markdown",
            "label": "markdown"
          }
        ],
        "name": "truncate_method",
        "display_name": "truncate_method",
        "type": "str",
        "list": false,
        "field_type": "select"
      },
      "truncate_length": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 2000,
        "name": "truncate_length",
        "display_name": "truncate_length",
        "type": "str",
        "list": false,
        "field_type": "number"
      },
      "floating_range": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 100,
        "name": "floating_range",
        "display_name": "floating_range",
        "type": "str",
        "list": false,
        "field_type": "number"
      },
      "output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output",
        "display_name": "output",
        "type": "list",
        "list": true,
        "field_type": "textarea",
        "is_output": true
      },
    }
  }
}