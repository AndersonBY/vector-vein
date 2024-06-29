/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 13:34:20
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-29 16:25:59
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "llms.groq",
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
        "value": "groq-mixtral-8x7b-32768",
        "options": [
          {
            "label": "mixtral-8x7b-32768",
            "value": "groq-mixtral-8x7b-32768",
          },
          {
            "label": "llama3-70b-8192",
            "value": "groq-llama3-70b-8192",
          },
          {
            "label": "llama3-8b-8192",
            "value": "groq-llama3-8b-8192",
          },
          {
            "label": "gemma-7b-it",
            "value": "groq-gemma-7b-it",
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