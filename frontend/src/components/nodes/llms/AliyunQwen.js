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
        "value": "qwen3-32b",
        "options": [
          {
            "value": "qwen3-max-preview",
            "label": "qwen3-max-preview",
          },
          {
            "value": "qwen3-235b-a22b-instruct-2507",
            "label": "qwen3-235b-a22b-instruct-2507",
          },
          {
            "value": "qwen3-coder-480b-a35b-instruct",
            "label": "qwen3-coder-480b-a35b-instruct",
          },
          {
            "value": "qwen3-235b-a22b",
            "label": "qwen3-235b-a22b",
          },
          {
            "value": "qwen3-235b-a22b-thinking",
            "label": "qwen3-235b-a22b-thinking",
          },
          {
            "value": "qwen3-next-80b-a3b-thinking",
            "label": "qwen3-next-80b-a3b-thinking",
          },
          {
            "value": "qwen3-next-80b-a3b-instruct",
            "label": "qwen3-next-80b-a3b-instruct",
          },
          {
            "value": "qwen3-32b",
            "label": "qwen3-32b",
          },
          {
            "value": "qwen3-32b-thinking",
            "label": "qwen3-32b-thinking",
          },
          {
            "value": "qwen3-30b-a3b",
            "label": "qwen3-30b-a3b",
          },
          {
            "value": "qwen3-30b-a3b-thinking",
            "label": "qwen3-30b-a3b-thinking",
          },
          {
            "value": "qwen3-14b",
            "label": "qwen3-14b",
          },
          {
            "value": "qwen3-14b-thinking",
            "label": "qwen3-14b-thinking",
          },
          {
            "value": "qwen3-8b",
            "label": "qwen3-8b",
          },
          {
            "value": "qwen3-8b-thinking",
            "label": "qwen3-8b-thinking",
          },
          {
            "value": "qwen3-4b",
            "label": "qwen3-4b",
          },
          {
            "value": "qwen3-4b-thinking",
            "label": "qwen3-4b-thinking",
          },
          {
            "value": "qwen3-1.7b",
            "label": "qwen3-1.7b",
          },
          {
            "value": "qwen3-1.7b-thinking",
            "label": "qwen3-1.7b-thinking",
          },
          {
            "value": "qwen3-0.6b",
            "label": "qwen3-0.6b",
          },
          {
            "value": "qwen3-0.6b-thinking",
            "label": "qwen3-0.6b-thinking",
          },
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
            "value": "qwq-32b",
            "label": "qwq-32b"
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