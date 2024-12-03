/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 00:48:33
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-05-17 16:28:50
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "text_processing.text_replace",
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
      "replace_items": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": [],
        "name": "replace_items",
        "display_name": "replace_items",
        "type": "str",
        "list": true,
        "field_type": "custom"
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