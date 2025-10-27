/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 10:53:54
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-24 22:48:58
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "media_processing.claude_vision",
    "has_inputs": true,
    "template": {
      "text_prompt": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "text_prompt",
        "display_name": "text_prompt",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "llm_model": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "claude-sonnet-4-5-20250929",
        "options": [
          {
            "value": "claude-sonnet-4-5-20250929-thinking",
            "label": "claude-sonnet-4-5-20250929-thinking"
          },
          {
            "value": "claude-sonnet-4-5-20250929",
            "label": "claude-sonnet-4-5-20250929"
          },
          {
            "value": "claude-haiku-4-5-20251001",
            "label": "claude-haiku-4-5-20251001",
          },
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
        ],
        "name": "llm_model",
        "display_name": "llm_model",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "multiple_input": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": false,
        "name": "multiple_input",
        "display_name": "multiple_input",
        "type": "bool",
        "list": false,
        "field_type": "checkbox",
        "has_tooltip": true,
      },
      "images_or_urls": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "images",
        "options": [
          {
            "value": "images",
            "label": "images"
          },
          {
            "value": "urls",
            "label": "urls"
          },
        ],
        "name": "images_or_urls",
        "display_name": "images_or_urls",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "radio"
      },
      "images": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": [],
        "name": "images",
        "display_name": "images",
        "type": "str",
        "list": false,
        "field_type": "file",
        "support_file_types": ".jpg, .jpeg, .png, .webp",
        "condition": (fieldsData) => {
          return fieldsData.images_or_urls.value == 'images'
        }
      },
      "urls": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "urls",
        "display_name": "urls",
        "type": "str",
        "list": false,
        "field_type": "input",
        "condition": (fieldsData) => {
          return fieldsData.images_or_urls.value == 'urls'
        },
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
        "field_type": "input",
        "is_output": true
      },
    }
  }
}