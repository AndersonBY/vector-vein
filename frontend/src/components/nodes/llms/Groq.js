export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "llms.groq",
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
        "value": "groq-mixtral-8x7b-32768",
        "options": [
          {
            "label": "mixtral-8x7b-32768",
            "value": "mixtral-8x7b-32768",
          },
          {
            "label": "llama3-70b-8192",
            "value": "llama3-70b-8192",
          },
          {
            "label": "llama3-8b-8192",
            "value": "llama3-8b-8192",
          },
          {
            "label": "gemma-7b-it",
            "value": "gemma-7b-it",
          },
          {
            "label": "gemma2-9b-it",
            "value": "gemma2-9b-it",
          },
          {
            "label": "llama3-groq-70b-8192-tool-use-preview",
            "value": "llama3-groq-70b-8192-tool-use-preview",
          },
          {
            "label": "llama3-groq-8b-8192-tool-use-preview",
            "value": "llama3-groq-8b-8192-tool-use-preview",
          },
          {
            "label": "llama-3.1-70b-versatile",
            "value": "llama-3.1-70b-versatile",
          },
          {
            "label": "llama-3.1-8b-versatile",
            "value": "llama-3.1-8b-versatile",
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