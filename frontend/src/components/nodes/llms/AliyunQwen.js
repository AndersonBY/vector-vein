/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 12:20:07
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-08 13:11:17
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "llms.aliyun_qwen",
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
        "value": "qwen2.5-72b-instruct",
        "options": [
          {
            "value": "qwen2.5-72b-instruct",
            "label": "qwen2.5-72b-instruct"
          },
          {
            "value": "qwen2.5-32b-instruct",
            "label": "qwen2.5-32b-instruct"
          },
          {
            "value": "qwen2.5-coder-32b-instruct",
            "label": "qwen2.5-coder-32b-instruct"
          },
          {
            "value": "qwq-32b-preview",
            "label": "qwq-32b-preview"
          },
          {
            "value": "qwen2.5-14b-instruct",
            "label": "qwen2.5-14b-instruct"
          },
          {
            "value": "qwen2.5-7b-instruct",
            "label": "qwen2.5-7b-instruct"
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