/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 13:38:33
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-08-07 19:17:15
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "media_editing.image_watermark",
    "has_inputs": true,
    "template": {
      "input_image": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": [],
        "name": "input_image",
        "display_name": "input_image",
        "type": "str",
        "list": false,
        "field_type": "file",
        "support_file_types": ".jpg, .jpeg, .png, .webp",
      },
      "image_or_text": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "text",
        "options": [
          {
            "value": "text",
            "label": "text"
          },
          {
            "value": "image",
            "label": "image"
          },
        ],
        "name": "image_or_text",
        "display_name": "image_or_text",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "radio"
      },
      "watermark_image": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": [],
        "name": "watermark_image",
        "display_name": "watermark_image",
        "type": "str",
        "list": false,
        "field_type": "file",
        "support_file_types": ".jpg, .jpeg, .png, .webp",
        "condition": (fieldsData) => {
          return fieldsData.image_or_text.value == "image"
        },
      },
      "watermark_image_width_ratio": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": 0.3,
        "name": "watermark_image_width_ratio",
        "display_name": "watermark_image_width_ratio",
        "type": "float",
        "clear_after_run": false,
        "list": false,
        "field_type": "number",
        "has_tooltip": true,
        "condition": (fieldsData) => {
          return fieldsData.image_or_text.value == "image"
        },
      },
      "watermark_image_height_ratio": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": 0,
        "name": "watermark_image_height_ratio",
        "display_name": "watermark_image_height_ratio",
        "type": "float",
        "clear_after_run": false,
        "list": false,
        "field_type": "number",
        "has_tooltip": true,
        "condition": (fieldsData) => {
          return fieldsData.image_or_text.value == "image"
        },
      },
      "watermark_text": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "watermark_text",
        "display_name": "watermark_text",
        "type": "str",
        "list": false,
        "field_type": "textarea",
        "condition": (fieldsData) => {
          return fieldsData.image_or_text.value == "text"
        },
      },
      "watermark_text_font": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": [],
        "name": "watermark_text_font",
        "display_name": "watermark_text_font",
        "type": "str",
        "list": false,
        "field_type": "file",
        "support_file_types": ".otf, .ttf, .ttc, .otc",
        "condition": (fieldsData) => {
          return fieldsData.image_or_text.value == "text"
        },
      },
      "watermark_text_font_size": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": 20,
        "name": "watermark_text_font_size",
        "display_name": "watermark_text_font_size",
        "type": "float",
        "clear_after_run": false,
        "list": false,
        "field_type": "number",
        "condition": (fieldsData) => {
          return fieldsData.image_or_text.value == "text"
        },
      },
      "watermark_text_font_color": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "#ffffff",
        "name": "watermark_text_font_color",
        "display_name": "watermark_text_font_color",
        "type": "str",
        "list": false,
        "field_type": "input",
        "condition": (fieldsData) => {
          return fieldsData.image_or_text.value == "text"
        },
      },
      "opacity": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": 0.8,
        "name": "opacity",
        "display_name": "opacity",
        "type": "float",
        "clear_after_run": false,
        "list": false,
        "field_type": "number",
        "group": "default",
      },
      "position": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": 'bottom_right',
        "options": [
          {
            "label": "center",
            "value": "center",
          },
          {
            "label": "top_left",
            "value": "top_left",
          },
          {
            "label": "top",
            "value": "top",
          },
          {
            "label": "top_right",
            "value": "top_right",
          },
          {
            "label": "right",
            "value": "right",
          },
          {
            "label": "bottom_right",
            "value": "bottom_right",
          },
          {
            "label": "bottom",
            "value": "bottom",
          },
          {
            "label": "bottom_left",
            "value": "bottom_left",
          },
          {
            "label": "left",
            "value": "left",
          },
        ],
        "name": "position",
        "display_name": "position",
        "type": "str",
        "clear_after_run": false,
        "list": false,
        "field_type": "select",
        "group": "default",
      },
      "vertical_gap": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 10,
        "name": "vertical_gap",
        "display_name": "vertical_gap",
        "type": "int",
        "list": false,
        "field_type": "number",
        "group": "default",
      },
      "horizontal_gap": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 10,
        "name": "horizontal_gap",
        "display_name": "horizontal_gap",
        "type": "int",
        "list": false,
        "field_type": "number",
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
