/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 13:22:49
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-05-02 12:38:43
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "llms.mini_max",
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
        "value": "abab6.5s-chat",
        "options": [
          {
            "value": "abab5.5-chat",
            "label": "abab5.5-chat"
          },
          {
            "value": "abab6-chat",
            "label": "abab6-chat"
          },
          {
            "value": "abab6.5s-chat",
            "label": "abab6.5s-chat"
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