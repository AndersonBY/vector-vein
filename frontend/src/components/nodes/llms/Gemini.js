/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 13:20:33
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-04 15:03:14
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "llms.gemini",
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
        "value": "gemini-1.5-flash",
        "options": [
          {
            "value": "gemini-2.0-flash-exp",
            "label": "gemini-2.0-flash-exp"
          },
          {
            "value": "gemini-2.0-flash-thinking-exp-1219",
            "label": "gemini-2.0-flash-thinking-exp-1219"
          },
          {
            "value": "gemini-exp-1206",
            "label": "gemini-exp-1206"
          },
          {
            "value": "gemini-1.5-flash",
            "label": "gemini-1.5-flash"
          },
          {
            "value": "gemini-1.0-pro",
            "label": "gemini-1.0-pro"
          },
          {
            "value": "gemini-1.5-pro",
            "label": "gemini-1.5-pro"
          }
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