/**
 * @Author: Bi Ying
 * @Date:   2024-04-14 19:51:40
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-14 22:45:35
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "web_crawlers.youtube_crawler",
    "has_inputs": true,
    "template": {
      "url_or_video_id": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": "",
        "name": "url_or_video_id",
        "display_name": "url_or_video_id",
        "type": "str",
        "list": false,
        "field_type": "input"
      },
      "get_comments": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": false,
        "name": "get_comments",
        "display_name": "get_comments",
        "type": "bool",
        "list": false,
        "field_type": "checkbox"
      },
      "comments_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "text_only",
        "options": [
          {
            "value": "text_only",
            "label": "text_only"
          },
          {
            "value": "detailed",
            "label": "detailed"
          },
        ],
        "name": "comments_type",
        "display_name": "comments_type",
        "type": "bool",
        "list": false,
        "field_type": "radio"
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
      "output_comments": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output_comments",
        "display_name": "output_comments",
        "type": "str|dict",
        "list": false,
        "field_type": "textarea",
        "is_output": true,
      },
    }
  }
}