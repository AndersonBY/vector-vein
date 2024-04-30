/**
 * @Author: Bi Ying
 * @Date:   2024-04-14 19:37:11
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-30 21:33:17
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "web_crawlers.bilibili_crawler",
    "has_inputs": true,
    "template": {
      "url_or_bvid": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": "",
        "name": "url_or_bvid",
        "display_name": "url_or_bvid",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
      "output_type": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "str",
        "options": [
          {
            "value": "str",
            "label": "str"
          },
          {
            "value": "list",
            "label": "list"
          },
        ],
        "name": "output_type",
        "display_name": "output_type",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "output_subtitle": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output_subtitle",
        "display_name": "output_subtitle",
        "type": "str|dict",
        "clear_after_run": true,
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
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea",
        "is_output": true,
      },
    }
  }
}