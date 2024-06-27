/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 00:38:53
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-06-16 23:42:16
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "tools.text_search",
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
        "value": "jina.ai",
        "options": [
          {
            "value": "bing",
            "label": "bing"
          },
          {
            "value": "jina.ai",
            "label": "jina.ai"
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
        "value": 10,
        "name": "count",
        "display_name": "count",
        "type": "str",
        "list": false,
        "field_type": "number",
        "group": "default",
      },
      "combine_result_in_text": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": true,
        "name": "combine_result_in_text",
        "display_name": "combine_result_in_text",
        "type": "bool",
        "clear_after_run": false,
        "list": false,
        "field_type": "checkbox",
        "group": "default",
      },
      "max_snippet_length": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 300,
        "name": "max_snippet_length",
        "display_name": "Max Snippet Length",
        "type": "number",
        "list": false,
        "field_type": "number",
        "group": "default"
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
        "field_type": "select",
        "group": "default",
      },
      "output_page_title": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": [],
        "name": "output_page_title",
        "display_name": "output_page_title",
        "type": "list|str",
        "list": false,
        "field_type": "",
        "is_output": true
      },
      "output_page_url": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": [],
        "name": "output_page_url",
        "display_name": "output_page_url",
        "type": "list|str",
        "list": false,
        "field_type": "",
        "is_output": true
      },
      "output_page_snippet": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": [],
        "name": "output_page_snippet",
        "display_name": "output_page_snippet",
        "type": "list|str",
        "list": false,
        "field_type": "",
        "is_output": true
      },
    }
  }
}