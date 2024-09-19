/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 13:17:37
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-24 22:49:13
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "llms.claude",
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
        "value": "claude-3-haiku-20240307",
        "options": [
          {
            "value": "claude-3-5-sonnet-20240620",
            "label": "claude-3-5-sonnet-20240620"
          },
          {
            "value": "claude-3-opus-20240229",
            "label": "claude-3-opus-20240229"
          },
          {
            "value": "claude-3-sonnet-20240229",
            "label": "claude-3-sonnet-20240229"
          },
          {
            "value": "claude-3-haiku-20240307",
            "label": "claude-3-haiku-20240307"
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