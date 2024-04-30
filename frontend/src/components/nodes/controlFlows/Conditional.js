/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 14:08:56
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 14:30:56
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "control_flows.conditional",
    "has_inputs": true,
    "template": {
      "field_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "string",
        "options": [
          {
            "value": "string",
            "label": "Str"
          },
          {
            "value": "number",
            "label": "Number"
          },
        ],
        "name": "field_type",
        "display_name": "field_type",
        "type": "str",
        "list": true,
        "field_type": "select"
      },
      "left_field": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "left_field",
        "display_name": "left_field",
        "type": "str|float|int",
        "list": false,
        "field_type": "input"
      },
      "operator": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "equal",
        "options": [
          {
            "value": "equal",
            "label": "equal",
            "field_type": ["string", "number"]
          },
          {
            "value": "not_equal",
            "label": "not_equal",
            "field_type": ["string", "number"]
          },
          {
            "value": "greater_than",
            "label": "greater_than",
            "field_type": ["number"]
          },
          {
            "value": "less_than",
            "label": "less_than",
            "field_type": ["number"]
          },
          {
            "value": "greater_than_or_equal",
            "label": "greater_than_or_equal",
            "field_type": ["number"]
          },
          {
            "value": "less_than_or_equal",
            "label": "less_than_or_equal",
            "field_type": ["number"]
          },
          {
            "value": "include",
            "label": "include",
            "field_type": ["string"]
          },
          {
            "value": "not_include",
            "label": "not_include",
            "field_type": ["string"]
          },
          {
            "value": "is_empty",
            "label": "is_empty",
            "field_type": ["string"]
          },
          {
            "value": "is_not_empty",
            "label": "is_not_empty",
            "field_type": ["string"]
          },
          {
            "value": "starts_with",
            "label": "starts_with",
            "field_type": ["string"]
          },
          {
            "value": "ends_with",
            "label": "ends_with",
            "field_type": ["string"]
          },
        ],
        "name": "operator",
        "display_name": "operator",
        "type": "str",
        "list": false,
        "field_type": "select"
      },
      "right_field": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "right_field",
        "display_name": "right_field",
        "type": "str|float|int",
        "list": false,
        "field_type": "input"
      },
      "true_output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "true_output",
        "display_name": "true_output",
        "type": "str",
        "list": false,
        "field_type": ""
      },
      "false_output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "false_output",
        "display_name": "false_output",
        "type": "str",
        "list": false,
        "field_type": ""
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
      },
    }
  }
}