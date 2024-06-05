/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 02:41:18
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-05 19:30:31
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "output.table",
    "has_inputs": true,
    "template": {
      "content_type": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "csv",
        "options": [
          {
            "value": "file",
            "label": "file"
          },
          {
            "value": "csv",
            "label": "csv"
          },
          {
            "value": "json",
            "label": "json"
          },
        ],
        "name": "content_type",
        "display_name": "content_type",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
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
      "show_table": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": true,
        "name": "show_table",
        "display_name": "show_table",
        "type": "bool",
        "clear_after_run": false,
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
        "type": "str|dict",
        "list": false,
        "field_type": "textarea",
        "is_output": true
      },
    }
  }
}