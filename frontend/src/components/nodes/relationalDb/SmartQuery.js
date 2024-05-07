/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 02:28:08
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-05-07 11:47:58
 */
import { flattenedChatModelOptions } from '@/utils/common'

export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "relational_db.smart_query",
    "has_inputs": true,
    "template": {
      "query": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "query",
        "display_name": "query",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "model": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "OpenAI/gpt-35-turbo",
        "options": flattenedChatModelOptions,
        "name": "model",
        "display_name": "model",
        "type": "str",
        "list": false,
        "field_type": "select"
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
      "use_sample_data": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": true,
        "name": "use_sample_data",
        "display_name": "use_sample_data",
        "type": "bool",
        "list": false,
        "field_type": "checkbox",
        "group": "default",
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
        "group": "default",
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
        "field_type": "number",
        "group": "default",
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
        "type": "list|str",
        "list": false,
        "field_type": "",
        "is_output": true
      },
      "output_query_sql": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output_query_sql",
        "display_name": "output_query_sql",
        "type": "list|str",
        "list": false,
        "field_type": "",
        "is_output": true
      }
    }
  }
}