/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 01:05:40
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 01:06:14
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "text_processing.markdown_to_html",
    "has_inputs": true,
    "template": {
      "markdown": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "markdown",
        "display_name": "markdown",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "html": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "html",
        "display_name": "html",
        "type": "str",
        "list": false,
        "field_type": "textarea",
        "is_output": true
      }
    }
  }
}