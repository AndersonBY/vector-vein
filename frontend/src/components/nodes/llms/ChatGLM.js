/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 12:30:13
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-12 20:26:40
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "llms.chat_glm",
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
        "value": "glm-4-air",
        "options": [
          {
            "value": "glm-4-plus",
            "label": "glm-4-plus",
          },
          {
            "value": "glm-4",
            "label": "glm-4"
          },
          {
            "value": "glm-4-0520",
            "label": "glm-4-0520",
          },
          {
            "value": "glm-4-air",
            "label": "glm-4-air",
          },
          {
            "value": "glm-4-airx",
            "label": "glm-4-airx",
          },
          {
            "value": "glm-4-flash",
            "label": "glm-4-flash",
          },
          {
            "value": "glm-4-long",
            "label": "glm-4-long",
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