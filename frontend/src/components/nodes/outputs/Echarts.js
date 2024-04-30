/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 02:41:18
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 02:41:37
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "output.echarts",
    "has_inputs": true,
    "template": {
      "option": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "option",
        "display_name": "option",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "show_echarts": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": true,
        "name": "show_echarts",
        "display_name": "show_echarts",
        "type": "bool",
        "clear_after_run": false,
        "list": false,
        "field_type": "checkbox"
      },
    }
  }
}