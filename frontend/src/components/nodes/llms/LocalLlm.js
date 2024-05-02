/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 13:23:42
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-05-02 17:22:14
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "llms.local_llm",
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
      "model_family": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "",
        "options": [],
        "name": "model_family",
        "display_name": "model_family",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "llm_model": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "",
        "options": [],
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