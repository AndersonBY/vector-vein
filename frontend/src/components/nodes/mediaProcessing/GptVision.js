/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 12:08:53
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-08-02 19:54:04
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "media_processing.gpt_vision",
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
        "value": "gpt-5",
        "options": [
          {
            "value": "gpt-5",
            "label": "gpt-5"
          },
          {
            "value": "gpt-5-codex",
            "label": "gpt-5-codex"
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
            "value": "gpt-4o",
            "label": "gpt-4o"
          },
          {
            "value": "gpt-4o-mini",
            "label": "gpt-4o-mini"
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
        ],
        "name": "llm_model",
        "display_name": "llm_model",
        "type": "str",
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
      "detail_type": {
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
            "value": "low",
            "label": "low"
          },
          {
            "value": "high",
            "label": "high"
          },
        ],
        "name": "detail_type",
        "display_name": "detail_type",
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
    }
  }
}