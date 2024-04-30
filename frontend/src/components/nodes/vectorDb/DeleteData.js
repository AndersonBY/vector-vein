/**
 * @Author: Bi Ying
 * @Date:   2024-04-14 22:50:49
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-14 22:53:01
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "vector_db.delete_data",
    "has_inputs": true,
    "template": {
      "object_id": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "object_id",
        "display_name": "object_id",
        "type": "list|str",
        "list": false,
        "field_type": ""
      },
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
      "delete_success": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "delete_success",
        "display_name": "delete_success",
        "type": "list|bool",
        "list": false,
        "field_type": "",
        "is_output": true
      }
    }
  }
}