/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 02:52:54
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 17:34:31
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "output.text",
    "has_inputs": false,
    "template": {
      "text": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": "",
        "name": "text",
        "display_name": "text",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "output_title": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output_title",
        "display_name": "output_title",
        "type": "str",
        "list": false,
        "field_type": "input",
        "has_tooltip": true
      },
      "render_markdown": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": true,
        "name": "render_markdown",
        "display_name": "render_markdown",
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
        "type": "str|dict",
        "list": false,
        "field_type": "textarea",
        "is_output": true
      },
    }
  }
}