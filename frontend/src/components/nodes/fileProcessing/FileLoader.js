/**
 * @Author: Bi Ying
 * @Date:   2024-04-29 02:46:49
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-05 19:36:05
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
        "multiline": true,
        "value": [],
        "password": false,
        "name": "files",
        "display_name": "files",
        "type": "str",
        "clear_after_run": true,
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
        "multiline": true,
        "value": "",
        "password": false,
        "name": "output",
        "display_name": "output",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "",
        "is_output": true
      },
    }
  }
}