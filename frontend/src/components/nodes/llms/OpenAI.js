/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 13:25:09
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 16:11:46
 */
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
        "value": "gpt-3.5",
        "options": [
          {
            "value": "gpt-3.5",
            "label": "gpt-3.5-turbo"
          },
          {
            "value": "gpt-4",
            "label": "gpt-4-turbo"
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
        "clear_after_run": false,
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
        "clear_after_run": false,
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