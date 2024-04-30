/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 02:48:07
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 02:48:24
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "output.mindmap",
    "has_inputs": true,
    "template": {
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
      "show_mind_map": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": true,
        "name": "show_mind_map",
        "display_name": "show_mind_map",
        "type": "bool",
        "clear_after_run": false,
        "list": false,
        "field_type": "checkbox"
      },
    }
  }
}