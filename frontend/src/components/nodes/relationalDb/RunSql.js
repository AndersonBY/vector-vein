/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 01:56:28
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 02:00:58
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "relational_db.run_sql",
    "has_inputs": true,
    "template": {
      "database": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "options": [],
        "name": "database",
        "display_name": "database",
        "type": "str",
        "list": false,
        "field_type": "select"
      },
      "sql": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "sql",
        "display_name": "sql",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "read_only": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": false,
        "name": "read_only",
        "display_name": "read_only",
        "type": "bool",
        "list": false,
        "field_type": "checkbox",
        "has_tooltip": true
      },
      "include_column_names": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": true,
        "name": "include_column_names",
        "display_name": "include_column_names",
        "type": "bool",
        "list": false,
        "field_type": "checkbox",
        "condition": (fieldsData) => {
          return fieldsData.output_type.value == 'list'
        },
        "has_tooltip": true
      },
      "max_count": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 100,
        "name": "max_count",
        "display_name": "max_count",
        "type": "str",
        "list": false,
        "field_type": "number"
      },
      "output_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "csv",
        "options": [
          {
            "value": "list",
            "label": "list"
          },
          {
            "value": "markdown",
            "label": "markdown"
          },
          {
            "value": "csv",
            "label": "csv"
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