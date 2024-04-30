/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 02:43:17
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 02:43:33
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "output.email",
    "has_inputs": true,
    "template": {
      "to_email": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": "",
        "name": "to_email",
        "display_name": "to_email",
        "type": "str",
        "list": false,
        "field_type": "input"
      },
      "subject": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": "",
        "name": "subject",
        "display_name": "subject",
        "type": "str",
        "list": false,
        "field_type": "input"
      },
      "content_html": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "content_html",
        "display_name": "content_html",
        "type": "str",
        "list": false,
        "field_type": "input"
      },
      "attachments": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "attachments",
        "display_name": "attachments",
        "type": "str",
        "list": false,
        "field_type": "input"
      },
    }
  }
}