/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 14:05:21
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-24 19:17:09
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "file_processing.file_loader",
    "has_inputs": true,
    "template": {
      "files": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": [],
        "name": "files",
        "display_name": "files",
        "type": "str",
        "list": false,
        "field_type": "file"
      },
      "remove_image": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": true,
        "name": "remove_image",
        "display_name": "remove_image",
        "type": "bool",
        "list": false,
        "field_type": "checkbox"
      },
      "remove_url_and_email": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": true,
        "name": "remove_url_and_email",
        "display_name": "remove_url_and_email",
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
        "field_type": "",
        "is_output": true
      },
    }
  }
}