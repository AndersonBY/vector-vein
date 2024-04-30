/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 15:19:55
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 15:21:35
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "control_flows.json_process",
    "has_inputs": true,
    "template": {
      "input": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "input",
        "display_name": "input",
        "type": "str|dict",
        "list": false,
        "field_type": "input"
      },
      "process_mode": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "get_value",
        "options": [
          {
            "value": "get_value",
            "label": "get_value"
          },
          {
            "value": "get_multiple_values",
            "label": "get_multiple_values"
          },
          {
            "value": "list_values",
            "label": "list_values"
          },
          {
            "value": "list_keys",
            "label": "list_keys"
          },
        ],
        "name": "process_mode",
        "display_name": "process_mode",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "key": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "key",
        "display_name": "key",
        "type": "str",
        "list": false,
        "field_type": "input",
        "condition": (fieldsData) => {
          return fieldsData.process_mode.value == 'get_value'
        }
      },
      "keys": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": [],
        "name": "keys",
        "display_name": "keys",
        "type": "list",
        "list": false,
        "field_type": "input"
      },
      "default_value": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "default_value",
        "display_name": "default_value",
        "type": "str",
        "list": false,
        "field_type": "input",
        "condition": (fieldsData) => {
          return fieldsData.process_mode.value == 'get_value'
        }
      },
      "output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output",
        "display_name": "output",
        "type": "str",
        "list": false,
        "field_type": "",
        "is_output": true
      }
    }
  }
}