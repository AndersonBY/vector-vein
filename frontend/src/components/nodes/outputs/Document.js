/**
 * @Author: Bi Ying
 * @Date:   2024-04-29 02:53:06
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-29 02:55:08
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "output.document",
    "has_inputs": true,
    "template": {
      "file_name": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": "",
        "name": "file_name",
        "display_name": "file_name",
        "type": "str",
        "list": false,
        "field_type": "input"
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
      "export_type": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": ".docx",
        "options": [
          {
            "value": ".docx",
            "label": ".docx"
          },
          {
            "value": ".xlsx",
            "label": ".xlsx"
          },
          {
            "value": ".txt",
            "label": ".txt"
          },
          {
            "value": ".md",
            "label": ".md"
          },
          {
            "value": ".json",
            "label": ".json"
          },
          {
            "value": ".csv",
            "label": ".csv"
          },
          {
            "value": ".html",
            "label": ".html"
          },
          {
            "value": ".srt",
            "label": ".srt"
          },
        ],
        "name": "export_type",
        "display_name": "export_type",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "show_local_file": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": true,
        "name": "show_local_file",
        "display_name": "show_local_file",
        "type": "bool",
        "clear_after_run": false,
        "list": false,
        "field_type": "checkbox"
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
        "field_type": "local_file",
        "is_output": true
      },
    }
  }
}