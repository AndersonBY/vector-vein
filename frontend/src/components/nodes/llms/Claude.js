export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "llms.claude",
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
        "value": "claude-sonnet-4-20250514",
        "options": [
          {
            "value": "claude-opus-4-20250514-thinking",
            "label": "claude-opus-4-20250514-thinking"
          },
          {
            "value": "claude-opus-4-20250514",
            "label": "claude-opus-4-20250514"
          },
          {
            "value": "claude-sonnet-4-20250514-thinking",
            "label": "claude-sonnet-4-20250514-thinking"
          },
          {
            "value": "claude-sonnet-4-20250514",
            "label": "claude-sonnet-4-20250514"
          },
          {
            "value": "claude-3-7-sonnet-thinking",
            "label": "claude-3-7-sonnet-thinking"
          },
          {
            "value": "claude-3-7-sonnet",
            "label": "claude-3-7-sonnet"
          },
          {
            "value": "claude-3-5-sonnet",
            "label": "claude-3-5-sonnet"
          },
          {
            "value": "claude-3-5-haiku",
            "label": "claude-3-5-haiku"
          },
          {
            "value": "claude-3-opus",
            "label": "claude-3-opus"
          },
          {
            "value": "claude-3-sonnet",
            "label": "claude-3-sonnet"
          },
          {
            "value": "claude-3-haiku",
            "label": "claude-3-haiku"
          },
        ],
        "name": "llm_model",
        "display_name": "llm_model",
        "type": "str",
        "list": true,
        "field_type": "select"
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
      "reasoning_content": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "reasoning_content",
        "display_name": "reasoning_content",
        "type": "str",
        "list": false,
        "field_type": "textarea",
        "is_output": true,
        "condition": (fieldsData) => {
          return fieldsData.llm_model.value === "claude-3-7-sonnet-thinking"
        }
      },
    }
  }
}