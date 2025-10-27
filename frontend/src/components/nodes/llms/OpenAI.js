export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "llms.open_ai",
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
        "value": "gpt-5",
        "options": [
          {
            "value": "gpt-5",
            "label": "gpt-5"
          },
          {
            "value": "gpt-5-pro",
            "label": "gpt-5-pro"
          },
          {
            "value": "gpt-5-mini",
            "label": "gpt-5-mini"
          },
          {
            "value": "gpt-5-nano",
            "label": "gpt-5-nano"
          },
          {
            "value": "gpt-5-chat-latest",
            "label": "gpt-5-chat-latest"
          },
          {
            "value": "gpt-5-codex",
            "label": "gpt-5-codex"
          },
          {
            "value": "o4-mini",
            "label": "o4-mini"
          },
          {
            "value": "o4-mini-high",
            "label": "o4-mini-high"
          },
          {
            "value": "gpt-4.1",
            "label": "gpt-4.1"
          },
          {
            "value": "o3-mini",
            "label": "o3-mini"
          },
          {
            "value": "o3-mini-high",
            "label": "o3-mini-high"
          },
          {
            "value": "o1-mini",
            "label": "o1-mini"
          },
          {
            "value": "o1-preview",
            "label": "o1-preview"
          },
          {
            "value": "gpt-4o",
            "label": "gpt-4o"
          },
          {
            "value": "gpt-4",
            "label": "gpt-4-turbo"
          },
          {
            "value": "gpt-4o-mini",
            "label": "gpt-4o-mini"
          },
          {
            "value": "gpt-3.5",
            "label": "gpt-3.5-turbo"
          },
        ],
        "name": "llm_model",
        "display_name": "llm_model",
        "type": "str",
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
        "field_type": "select"
      },
      "use_function_call": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": false,
        "name": "use_function_call",
        "display_name": "use_function_call",
        "type": "bool",
        "list": false,
        "field_type": "checkbox"
      },
      "functions": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": [],
        "name": "functions",
        "display_name": "functions",
        "type": "list",
        "list": false,
        "field_type": "select"
      },
      "function_call_mode": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "auto",
        "options": [
          {
            "value": "auto",
            "label": "auto"
          },
          {
            "value": "none",
            "label": "none"
          },
        ],
        "name": "function_call_mode",
        "display_name": "function_call_mode",
        "type": "str",
        "list": true,
        "field_type": "select"
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
      "function_call_output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "function_call_output",
        "display_name": "function_call_output",
        "type": "str",
        "list": false,
        "field_type": "",
        "is_output": true,
        "condition": (fieldsData) => {
          return fieldsData.use_function_call.value
        }
      },
      "function_call_arguments": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "function_call_arguments",
        "display_name": "function_call_arguments",
        "type": "dict",
        "list": false,
        "field_type": "",
        "is_output": true,
        "condition": (fieldsData) => {
          return fieldsData.use_function_call.value
        }
      },
    }
  }
}