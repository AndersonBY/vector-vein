/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 14:07:30
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 14:07:56
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "file_processing.file_upload",
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
        "field_type": "file",
        "support_file_types": "*/*",
        "accept_multiple": true,
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