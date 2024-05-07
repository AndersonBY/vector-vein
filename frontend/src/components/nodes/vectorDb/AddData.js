/**
 * @Author: Bi Ying
 * @Date:   2024-04-14 20:01:07
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-05-06 13:56:06
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "vector_db.add_data",
    "has_inputs": true,
    "template": {
      "text": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "text",
        "display_name": "text",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "content_title": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "content_title",
        "display_name": "content_title",
        "type": "str",
        "list": false,
        "field_type": "input"
      },
      "source_url": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "source_url",
        "display_name": "source_url",
        "type": "str",
        "list": false,
        "field_type": "input"
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
      "data_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "text",
        "options": [
          {
            "value": "TEXT",
            "label": "Text"
          },
          // {
          //   "value": "IMAGE",
          //   "label": "Image"
          // },
        ],
        "name": "data_type",
        "display_name": "data_type",
        "type": "str",
        "list": false,
        "field_type": "select",
        "group": "default",
      },
      "split_method": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "general",
        "options": [
          {
            "value": "general",
            "label": "general"
          },
          {
            "value": "delimiter",
            "label": "delimiter"
          },
          {
            "value": "markdown",
            "label": "markdown"
          },
          {
            "value": "table",
            "label": "table"
          },
        ],
        "name": "split_method",
        "display_name": "split_method",
        "type": "str",
        "list": false,
        "field_type": "select",
        "group": "default",
        "condition": (fieldsData) => {
          return fieldsData.data_type.value == 'text'
        }
      },
      "chunk_length": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 500,
        "name": "chunk_length",
        "display_name": "chunk_length",
        "type": "str",
        "list": false,
        "field_type": "number",
        "group": "default",
        "condition": (fieldsData) => {
          return ['general', 'markdown'].includes(fieldsData.split_method.value)
        }
      },
      "chunk_overlap": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 30,
        "name": "chunk_overlap",
        "display_name": "chunk_overlap",
        "type": "str",
        "list": false,
        "field_type": "number",
        "group": "default",
        "condition": (fieldsData) => {
          return ['general', 'markdown'].includes(fieldsData.split_method.value)
        }
      },
      "delimiter": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "\\n",
        "name": "delimiter",
        "display_name": "delimiter",
        "type": "str",
        "list": false,
        "field_type": "input",
        "group": "default",
        "condition": (fieldsData) => {
          return fieldsData.split_method.value == 'delimiter'
        }
      },
      "remove_url_and_email": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": true,
        "name": "remove_url_and_email",
        "display_name": "remove_url_and_email",
        "type": "bool",
        "list": false,
        "field_type": "checkbox",
        "group": "default",
      },
      "object_id": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "object_id",
        "display_name": "object_id",
        "type": "list|str",
        "list": false,
        "field_type": "",
        "is_output": true,
      }
    }
  }
}