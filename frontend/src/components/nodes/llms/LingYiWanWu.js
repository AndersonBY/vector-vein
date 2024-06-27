/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 13:21:37
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-05-24 11:47:47
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "llms.ling_yi_wan_wu",
    "has_inputs": true,
    "template": {
      "prompt": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "prompt",
        "display_name": "prompt",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "llm_model": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "yi-large",
        "options": [
          {
            "value": "yi-large",
            "label": "yi-large",
          },
          {
            "value": "yi-large-turbo",
            "label": "yi-large-turbo",
          },
          {
            "value": "yi-medium",
            "label": "yi-medium",
          },
          {
            "value": "yi-medium-200k",
            "label": "yi-medium-200k",
          },
          {
            "value": "yi-spark",
            "label": "yi-spark",
          },
        ],
        "name": "llm_model",
        "display_name": "llm_model",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "temperature": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 0.7,
        "name": "temperature",
        "display_name": "temperature",
        "type": "float",
        "list": false,
        "field_type": "temperature"
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