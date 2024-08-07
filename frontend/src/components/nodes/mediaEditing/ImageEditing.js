/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 13:38:33
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-08-05 22:17:58
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "media_editing.image_editing",
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
      "crop": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": false,
        "name": "crop",
        "display_name": "crop",
        "type": "bool",
        "clear_after_run": false,
        "list": false,
        "field_type": "checkbox",
        "group": "crop",
      },
      "crop_method": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": 'proportional',
        "options": [
          {
            "label": "proportional",
            "value": "proportional",
          },
          {
            "label": "fixed",
            "value": "fixed",
          },
        ],
        "name": "crop_method",
        "display_name": "crop_method",
        "type": "str",
        "clear_after_run": false,
        "list": false,
        "field_type": "select",
        "group": "crop",
        "condition": (fieldsData) => {
          return fieldsData.crop.value
        },
      },
      "crop_position": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": 'center',
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
          {
            "label": "absolute",
            "value": "absolute",
          },
        ],
        "name": "crop_position",
        "display_name": "crop_position",
        "type": "str",
        "clear_after_run": false,
        "list": false,
        "field_type": "select",
        "group": "crop",
        "condition": (fieldsData) => {
          return fieldsData.crop.value
        },
      },
      "crop_x": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 1,
        "name": "crop_x",
        "display_name": "crop_x",
        "type": "int",
        "list": false,
        "field_type": "number",
        "group": "crop",
        "condition": (fieldsData) => {
          return fieldsData.crop_position.value == 'absolute' && fieldsData.crop.value
        },
      },
      "crop_y": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 1,
        "name": "crop_y",
        "display_name": "crop_y",
        "type": "int",
        "list": false,
        "field_type": "number",
        "group": "crop",
        "condition": (fieldsData) => {
          return fieldsData.crop_position.value == 'absolute' && fieldsData.crop.value
        },
      },
      "crop_width": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 300,
        "name": "crop_width",
        "display_name": "crop_width",
        "type": "int",
        "list": false,
        "field_type": "number",
        "group": "crop",
        "has_tooltip": true,
        "condition": (fieldsData) => {
          return fieldsData.crop.value && fieldsData.crop_method.value == 'fixed'
        },
      },
      "crop_height": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 300,
        "name": "crop_height",
        "display_name": "crop_height",
        "type": "int",
        "list": false,
        "field_type": "number",
        "group": "crop",
        "has_tooltip": true,
        "condition": (fieldsData) => {
          return fieldsData.crop.value && fieldsData.crop_method.value == 'fixed'
        },
      },
      "crop_width_ratio": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 1,
        "name": "crop_width_ratio",
        "display_name": "crop_width_ratio",
        "type": "int",
        "list": false,
        "field_type": "number",
        "group": "crop",
        "condition": (fieldsData) => {
          return fieldsData.crop.value && fieldsData.crop_method.value == 'proportional'
        },
      },
      "crop_height_ratio": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 1,
        "name": "crop_height_ratio",
        "display_name": "crop_height_ratio",
        "type": "int",
        "list": false,
        "field_type": "number",
        "group": "crop",
        "condition": (fieldsData) => {
          return fieldsData.crop.value && fieldsData.crop_method.value == 'proportional'
        },
      },
      "scale": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": false,
        "name": "scale",
        "display_name": "scale",
        "type": "bool",
        "clear_after_run": false,
        "list": false,
        "field_type": "checkbox",
        "group": "scale",
      },
      "scale_method": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": 'proportional_scale',
        "options": [
          {
            "label": "proportional_scale",
            "value": "proportional_scale",
          },
          {
            "label": "fixed_width_height",
            "value": "fixed_width_height",
          },
        ],
        "name": "scale_method",
        "display_name": "scale_method",
        "type": "str",
        "clear_after_run": false,
        "list": false,
        "field_type": "select",
        "group": "scale",
        "condition": (fieldsData) => {
          return fieldsData.scale.value
        },
      },
      "scale_ratio": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": 1,
        "name": "scale_ratio",
        "display_name": "scale_ratio",
        "type": "float",
        "clear_after_run": false,
        "list": false,
        "field_type": "number",
        "group": "scale",
        "condition": (fieldsData) => {
          return fieldsData.scale.value && fieldsData.scale_method.value == 'proportional_scale'
        },
      },
      "scale_width": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 0,
        "name": "scale_width",
        "display_name": "scale_width",
        "type": "int",
        "list": false,
        "field_type": "number",
        "has_tooltip": true,
        "group": "scale",
        "condition": (fieldsData) => {
          return fieldsData.scale.value && fieldsData.scale_method.value == 'fixed_width_height'
        },
      },
      "scale_height": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 0,
        "name": "scale_height",
        "display_name": "scale_height",
        "type": "int",
        "list": false,
        "field_type": "number",
        "has_tooltip": true,
        "group": "scale",
        "condition": (fieldsData) => {
          return fieldsData.scale.value && fieldsData.scale_method.value == 'fixed_width_height'
        },
      },
      "compress": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": 100,
        "name": "compress",
        "display_name": "compress",
        "type": "float",
        "clear_after_run": false,
        "list": false,
        "field_type": "number",
        "group": "default",
        "has_tooltip": true,
      },
      "rotate": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 0,
        "name": "rotate",
        "display_name": "rotate",
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
