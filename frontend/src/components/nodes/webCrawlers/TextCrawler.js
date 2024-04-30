/**
 * @Author: Bi Ying
 * @Date:   2024-04-14 19:13:38
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-29 18:42:50
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "web_crawlers.text_crawler",
    "has_inputs": true,
    "template": {
      "url": {
        "required": true,
        "placeholder": "https://example.com",
        "show": true,
        "value": "",
        "name": "url",
        "display_name": "url",
        "type": "str",
        "list": false,
        "field_type": "input"
      },
      "output_type": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "text",
        "options": [
          {
            "value": "text",
            "label": "Text"
          },
          // {
          //   "value": "json",
          //   "label": "JSON"
          // },
        ],
        "name": "output_type",
        "display_name": "output_type",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select",
      },
      "output_text": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output_text",
        "display_name": "output_text",
        "type": "str|dict",
        "list": false,
        "field_type": "textarea",
        "is_output": true,
      },
      "output_title": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output_title",
        "display_name": "output_title",
        "type": "str|dict",
        "list": false,
        "field_type": "textarea",
        "is_output": true,
      },
    }
  }
}