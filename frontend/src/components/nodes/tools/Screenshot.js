/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 00:30:04
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-08 23:43:14
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "tools.screenshot",
    "has_inputs": true,
    "template": {
      "monitor_number": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 0,
        "name": "monitor_number",
        "display_name": "monitor_number",
        "type": "str",
        "list": false,
        "field_type": "number"
      },
      "output_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "base64",
        "options": [
          {
            "value": "base64",
            "label": "base64"
          },
          {
            "value": "file_path",
            "label": "file_path"
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
        "value": [],
        "name": "output",
        "display_name": "output",
        "type": "list|str",
        "list": false,
        "field_type": "",
        "is_output": true
      }
    }
  }
}