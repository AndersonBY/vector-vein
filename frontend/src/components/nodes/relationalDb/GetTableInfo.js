/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 01:52:28
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 16:06:20
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "relational_db.get_table_info",
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
      "tables": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": [],
        "options": [],
        "name": "table",
        "display_name": "table",
        "type": "str",
        "list": false,
        "field_type": "select"
      },
      "output_sql": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output_sql",
        "display_name": "output_sql",
        "type": "list|str",
        "list": false,
        "field_type": "",
        "is_output": true,
        "has_tooltip": true
      },
      "output_json": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": [],
        "name": "output_json",
        "display_name": "output_json",
        "type": "list|str",
        "list": false,
        "field_type": "",
        "is_output": true
      }
    }
  }
}