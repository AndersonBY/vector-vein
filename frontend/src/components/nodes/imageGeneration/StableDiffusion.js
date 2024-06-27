/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 13:38:33
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-25 16:57:09
 */
export function createTemplateData() {
  const specialWidthHeightModels = [
    'stable-diffusion-xl-1024-v0-9',
    'stable-diffusion-xl-1024-v1-0',
  ]
  const sd3Models = [
    "sd-ultra",
    "sd3-large",
    "sd3-large-turbo",
    "sd3-medium",
    "sd-core",
  ]
  return {
    "description": "description",
    "task_name": "image_generation.stable_diffusion",
    "has_inputs": true,
    "template": {
      "provider": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "stable-diffusion-official",
        "options": [
          {
            "value": "self-host",
            "label": "self-host"
          },
          {
            "value": "stable-diffusion-official",
            "label": "stable-diffusion-official"
          },
        ],
        "name": "provider",
        "display_name": "provider",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
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
      "negative_prompt": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "negative_prompt",
        "display_name": "negative_prompt",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "model": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "sd3-medium",
        "options": [
          {
            "value": "sd-ultra",
            "label": "Ultra"
          },
          {
            "value": "sd3-large",
            "label": "Stable Diffusion 3 Large"
          },
          {
            "value": "sd3-large-turbo",
            "label": "Stable Diffusion 3 Large Turbo"
          },
          {
            "value": "sd3-medium",
            "label": "Stable Diffusion 3 Medium"
          },
          {
            "value": "sd-core",
            "label": "Core"
          },
          {
            "value": "stable-diffusion-xl-1024-v1-0",
            "label": "SDXL 1.0"
          },
          {
            "value": "stable-diffusion-xl-1024-v0-9",
            "label": "SDXL 0.9"
          },
        ],
        "name": "model",
        "display_name": "model",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "cfg_scale": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 7,
        "name": "cfg_scale",
        "display_name": "cfg_scale",
        "type": "float",
        "list": false,
        "field_type": "number",
        "group": "default",
        "condition": (fieldsData) => {
          return !sd3Models.includes(fieldsData.model.value)
        },
      },
      "sampler": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "k_dpmpp_2m",
        "options": [
          {
            "value": "ddim",
            "label": "ddim",
          },
          {
            "value": "plms",
            "label": "plms",
          },
          {
            "value": "k_euler",
            "label": "k_euler",
          },
          {
            "value": "k_euler_ancestral",
            "label": "k_euler_ancestral",
          },
          {
            "value": "k_heun",
            "label": "k_heun",
          },
          {
            "value": "k_dpm_2",
            "label": "k_dpm_2",
          },
          {
            "value": "k_dpm_2_ancestral",
            "label": "k_dpm_2_ancestral",
          },
          {
            "value": "k_dpmpp_2s_ancestral",
            "label": "k_dpmpp_2s_ancestral",
          },
          {
            "value": "k_dpmpp_2m",
            "label": "k_dpmpp_2m",
          },
          {
            "value": "k_dpmpp_sde",
            "label": "k_dpmpp_sde",
          },
        ],
        "name": "sampler",
        "display_name": "sampler",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select",
        "group": "default",
        "condition": (fieldsData) => {
          return !sd3Models.includes(fieldsData.model.value)
        },
      },
      "size": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "1024 x 1024",
        "options": [
          {
            "value": "1024 x 1024",
            "label": "1024 x 1024",
          },
          {
            "value": "1152 x 896",
            "label": "1152 x 896",
          },
          {
            "value": "896 x 1152",
            "label": "896 x 1152",
          },
          {
            "value": "1216 x 832",
            "label": "1216 x 832",
          },
          {
            "value": "832 x 1216",
            "label": "832 x 1216",
          },
          {
            "value": "1344 x 768",
            "label": "1344 x 768",
          },
          {
            "value": "768 x 1344",
            "label": "768 x 1344",
          },
          {
            "value": "1536 x 640",
            "label": "1536 x 640",
          },
          {
            "value": "640 x 1536",
            "label": "640 x 1536",
          },
        ],
        "name": "size",
        "display_name": "size",
        "type": "int",
        "list": false,
        "field_type": "select",
        "condition": (fieldsData) => {
          return specialWidthHeightModels.includes(fieldsData.model.value) && !sd3Models.includes(fieldsData.model.value)
        }
      },
      "aspect_ratio": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "1:1",
        "options": [
          {
            "value": "1:1",
            "label": "1:1",
          },
          {
            "value": "16:9",
            "label": "16:9",
          },
          {
            "value": "21:9",
            "label": "21:9",
          },
          {
            "value": "2:3",
            "label": "2:3",
          },
          {
            "value": "3:2",
            "label": "3:2",
          },
          {
            "value": "4:5",
            "label": "4:5",
          },
          {
            "value": "5:4",
            "label": "5:4",
          },
          {
            "value": "9:16",
            "label": "9:16",
          },
          {
            "value": "9:21",
            "label": "9:21",
          },
        ],
        "name": "aspect_ratio",
        "display_name": "aspect_ratio",
        "type": "int",
        "list": false,
        "field_type": "select",
        "condition": (fieldsData) => {
          return sd3Models.includes(fieldsData.model.value)
        },
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