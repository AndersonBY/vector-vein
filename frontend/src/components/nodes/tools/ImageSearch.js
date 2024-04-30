/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 00:30:04
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 00:32:27
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "tools.image_search",
    "has_inputs": true,
    "template": {
      "search_text": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "search_text",
        "display_name": "search_text",
        "type": "str",
        "list": false,
        "field_type": "input"
      },
      "search_engine": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "bing",
        "options": [
          {
            "value": "bing",
            "label": "bing"
          },
          {
            "value": "pexels",
            "label": "pexels"
          },
          {
            "value": "unsplash",
            "label": "unsplash"
          },
        ],
        "name": "search_engine",
        "display_name": "search_engine",
        "type": "str",
        "list": false,
        "field_type": "select"
      },
      "count": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 5,
        "name": "count",
        "display_name": "count",
        "type": "str",
        "list": false,
        "field_type": "number"
      },
      "output_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "markdown",
        "options": [
          {
            "value": "text",
            "label": "text"
          },
          {
            "value": "markdown",
            "label": "markdown"
          },
        ],
        "name": "output_type",
        "display_name": "output_type",
        "type": "str",
        "list": false,
        "field_type": "select"
      },
      "output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": [],
        "name": "output",
        "display_name": "output",
        "type": "list|str",
        "list": false,
        "field_type": "",
        "is_output": true
      }
    }
  }
}