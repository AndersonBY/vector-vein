/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 00:48:33
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 00:49:52
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "text_processing.list_render",
    "has_inputs": true,
    "template": {
      "list": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": [],
        "name": "list",
        "display_name": "list",
        "type": "str",
        "list": true,
        "field_type": "list"
      },
      "separator": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "\\n\\n",
        "name": "separator",
        "display_name": "separator",
        "type": "str",
        "list": true,
        "field_type": "input"
      },
      "output_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "text",
        "options": [
          {
            "value": "text",
            "label": "Text"
          },
          {
            "value": "list",
            "label": "List"
          },
        ],
        "name": "output_type",
        "display_name": "output_type",
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
        "field_type": "textarea",
        "is_output": true
      }
    }
  }
}