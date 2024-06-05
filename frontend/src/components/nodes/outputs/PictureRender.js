/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 02:51:01
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-06 00:24:03
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "output.picture_render",
    "has_inputs": true,
    "template": {
      "render_type": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "pdf",
        "options": [
          {
            "value": "pdf",
            "label": "PDF"
          },
        ],
        "name": "render_type",
        "display_name": "render_type",
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
      "output_type": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "markdown",
        "options": [
          {
            "value": "only_link",
            "label": "only_link"
          },
          {
            "value": "markdown",
            "label": "markdown"
          },
          {
            "value": "html",
            "label": "html"
          },
        ],
        "name": "output_type",
        "display_name": "output_type",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
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
        "field_type": "input",
        "is_output": true
      },
    }
  }
}