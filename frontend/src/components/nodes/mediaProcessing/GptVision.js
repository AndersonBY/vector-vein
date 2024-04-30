/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 12:08:53
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 12:11:42
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
    }
  }
}