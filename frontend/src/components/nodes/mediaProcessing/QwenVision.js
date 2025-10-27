/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 12:06:23
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 12:07:05
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "media_processing.qwen_vision",
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
        "value": "qwen3-vl-30b-a3b-instruct",
        "options": [
          {
            "value": "qwen3-vl-30b-a3b-thinking",
            "label": "qwen3-vl-30b-a3b-thinking",
          },
          {
            "value": "qwen3-vl-30b-a3b-instruct",
            "label": "qwen3-vl-30b-a3b-instruct",
          },
          {
            "value": "qwen3-vl-8b-thinking",
            "label": "qwen3-vl-8b-thinking",
          },
          {
            "value": "qwen3-vl-8b-instruct",
            "label": "qwen3-vl-8b-instruct",
          },
          {
            "value": "qwen3-vl-flash",
            "label": "qwen3-vl-flash",
          },
          {
            "value": "qwen3-vl-plus",
            "label": "qwen3-vl-plus",
          },
          {
            "value": "qwen3-vl-235b-a22b-thinking",
            "label": "qwen3-vl-235b-a22b-thinking",
          },
          {
            "value": "qwen3-vl-235b-a22b-instruct",
            "label": "qwen3-vl-235b-a22b-instruct",
          },
          {
            "value": "qvq-72b-preview",
            "label": "qvq-72b-preview",
          },
          {
            "value": "qwen2.5-vl-72b-instruct",
            "label": "qwen2.5-vl-72b-instruct",
          },
          {
            "value": "qwen2.5-vl-7b-instruct",
            "label": "qwen2.5-vl-7b-instruct",
          },
          {
            "value": "qwen2.5-vl-3b-instruct",
            "label": "qwen2.5-vl-3b-instruct",
          },
          {
            "value": "qwen2-vl-72b-instruct",
            "label": "qwen2-vl-72b-instruct",
          },
          {
            "value": "qwen2-vl-7b-instruct",
            "label": "qwen2-vl-7b-instruct",
          },
          {
            "value": "qwen-vl-max",
            "label": "qwen-vl-max",
          },
          {
            "value": "qwen-vl-plus",
            "label": "qwen-vl-plus",
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