/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 01:27:17
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 01:29:48
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "text_processing.text_splitters",
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
          }
        ],
        "name": "split_method",
        "display_name": "split_method",
        "type": "str",
        "list": false,
        "field_type": "select"
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
        "condition": (fieldsData) => {
          return ['general', 'markdown'].includes(fieldsData.split_method.value)
        },
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
        "condition": (fieldsData) => {
          return ['general', 'markdown'].includes(fieldsData.split_method.value)
        },
      },
      "delimiter": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "\\n",
        "name": "delimiter",
        "display_name": "delimiter",
        "type": "str",
        "list": true,
        "field_type": "input",
        "condition": (fieldsData) => {
          return fieldsData.split_method.value == 'delimiter'
        },
      },
      "output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output",
        "display_name": "output",
        "type": "list",
        "list": true,
        "field_type": "textarea",
        "is_output": true
      },
    }
  }
}