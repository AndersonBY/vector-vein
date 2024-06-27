/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 13:36:19
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-05-06 13:57:28
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "image_generation.dall_e",
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
      "model": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "dall-e-3",
        "options": [
          {
            "value": "dall-e-3",
            "label": "DALL·E 3"
          },
        ],
        "name": "model",
        "display_name": "model",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "size": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "1024x1024",
        "options": [
          {
            "value": "1024x1024",
            "label": "1024x1024"
          },
          {
            "value": "1792x1024",
            "label": "1792x1024"
          },
          {
            "value": "1024x1792",
            "label": "1024x1792"
          },
        ],
        "name": "size",
        "display_name": "size",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "quality": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "standard",
        "options": [
          {
            "value": "standard",
            "label": "standard"
          },
          {
            "value": "hd",
            "label": "hd"
          },
        ],
        "name": "quality",
        "display_name": "quality",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select",
        "group": "default",
      },
      "style": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "vivid",
        "options": [
          {
            "value": "vivid",
            "label": "vivid"
          },
          {
            "value": "natural",
            "label": "natural"
          },
        ],
        "name": "style",
        "display_name": "style",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select",
        "group": "default",
      },
      "output_type": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "markdown",
        "options": [
          {
            "value": "only_link",
            "label": "only_link"
          },
          {
            "value": "markdown",
            "label": "markdown"
          },
          {
            "value": "html",
            "label": "html"
          },
        ],
        "name": "output_type",
        "display_name": "output_type",
        "type": "str",
        "clear_after_run": false,
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