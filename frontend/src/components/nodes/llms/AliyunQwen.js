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
          {
            "value": "qwen2.5-coder-7b-instruct",
            "label": "qwen2.5-coder-7b-instruct"
          },
        ],
        "name": "llm_model",
        "display_name": "llm_model",
        "type": "str",
        "list": true,
        "field_type": "select"
      },
      "top_p": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 0.95,
        "name": "top_p",
        "display_name": "top_p",
        "type": "float",
        "list": false,
        "field_type": "top_p",
        "group": "default",
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
        "field_type": "temperature",
        "group": "default",
      },
      "stream": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": false,
        "name": "stream",
        "display_name": "stream",
        "type": "bool",
        "list": false,
        "field_type": "checkbox"
      },
      "system_prompt": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "system_prompt",
        "display_name": "system_prompt",
        "type": "str",
        "list": false,
        "field_type": "textarea",
        "group": "default",
      },
      "response_format": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "text",
        "options": [
          {
            "value": "text",
            "label": "Text"
          },
          {
            "value": "json_object",
            "label": "JSON"
          },
        ],
        "name": "response_format",
        "display_name": "response_format",
        "type": "str",
        "list": true,
        "field_type": "select",
        "group": "default",
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