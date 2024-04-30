/**
 * @Author: Bi Ying
 * @Date:   2024-04-14 22:53:34
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-14 22:54:16
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "vector_db.search_data",
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
        "field_type": "textarea"
      },
      "data_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "text",
        "options": [
          {
            "value": "text",
            "label": "Text"
          },
          // {
          //   "value": "image",
          //   "label": "Image"
          // },
        ],
        "name": "data_type",
        "display_name": "data_type",
        "type": "str",
        "list": false,
        "field_type": "select"
      },
      "database": {
        "required": true,
        "placeholder": "",
        "show": true,
        "value": "",
        "options": [],
        "name": "database",
        "display_name": "database",
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
        "value": "text",
        "options": [
          {
            "value": "text",
            "label": "Text"
          },
          {
            "value": "list",
            "label": "List"
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