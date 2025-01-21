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
            "value": "Baichuan2-53B",
            "label": "Baichuan2-53B"
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
        "field_type": "temperature",
        "group": "default",
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
        "field_type": "select",
        "group": "default",
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
        "field_type": "checkbox",
        "group": "default",
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
        "field_type": "select",
        "group": "default",
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