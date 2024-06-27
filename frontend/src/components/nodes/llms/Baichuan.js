/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 12:27:06
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-24 22:20:51
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "llms.baichuan",
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
        "value": "Baichuan3-Turbo",
        "options": [
          {
            "value": "Baichuan4",
            "label": "Baichuan4"
          },
          {
            "value": "Baichuan3-Turbo",
            "label": "Baichuan3-Turbo"
          },
          {
            "value": "Baichuan3-Turbo-128k",
            "label": "Baichuan3-Turbo-128k"
          },
          {
            "value": "Baichuan2-Turbo",
            "label": "Baichuan2-Turbo"
          },
          {
            "value": "Baichuan2-Turbo-192k",
            "label": "Baichuan2-Turbo-192k"
          },
          {
            "value": "Baichuan2-53B",
            "label": "Baichuan2-53B"
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