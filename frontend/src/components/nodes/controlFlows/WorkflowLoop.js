/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 00:41:55
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 00:42:14
 */
import { getChatModelOptions } from '@/utils/common'

export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "control_flows.workflow_loop",
    "has_inputs": true,
    "seleted_workflow_title": "",
    "is_template": false,
    "template": {
      "workflow_id": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "workflow_id",
        "display_name": "workflow_id",
        "type": "str",
        "list": false,
        "field_type": "input"
      },
      "loop_count": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "loop_count",
        "display_name": "loop_count",
        "type": "int",
        "list": false,
        "field_type": "number"
      },
      "max_loop_count": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": 10,
        "name": "max_loop_count",
        "display_name": "max_loop_count",
        "type": "int",
        "list": false,
        "field_type": "number"
      },
      "initial_values": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "initial_values",
        "display_name": "initial_values",
        "type": "str",
        "list": false,
        "field_type": "input",
        "group": "initial_values",
      },
      "assignment_in_loop": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": {},
        "name": "assignment_in_loop",
        "display_name": "assignment_in_loop",
        "type": "dict",
        "list": false,
        "field_type": "input",
        "group": "assignment_in_loop",
      },
      "loop_end_condition": {
        "required": true,
        "placeholder": "",
        "show": false,
        "value": "loop_count",
        "options": [
          {
            "label": "loop_count",
            "value": "loop_count",
          },
          {
            "label": "output_field_condition",
            "value": "output_field_condition",
          },
          // {
          //   "label": "extra_workflow_judgement",
          //   "value": "extra_workflow_judgement",
          // },
          {
            "label": "ai_model_judgement",
            "value": "ai_model_judgement"
          },
        ],
        "name": "loop_end_condition",
        "display_name": "loop_end_condition",
        "type": "str",
        "list": false,
        "field_type": "select",
        "group": "loop_end_condition",
      },
      "output_field_condition_field": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "",
        "options": [],
        "name": "output_field_condition_field",
        "display_name": "output_field_condition_field",
        "type": "str",
        "list": false,
        "field_type": "select",
        "group": "loop_end_condition",
      },
      "output_field_condition_operator": {
        "required": false,
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
        "name": "output_field_condition_operator",
        "display_name": "output_field_condition_operator",
        "type": "str",
        "list": false,
        "field_type": "select",
        "group": "loop_end_condition",
      },
      "output_field_condition_value": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "output_field_condition_value",
        "display_name": "output_field_condition_value",
        "type": "str",
        "list": false,
        "field_type": "input"
      },
      "judgement_model": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "OpenAI⋄gpt-4o-mini",
        "options": getChatModelOptions(true),
        "name": "judgement_model",
        "display_name": "judgement_model",
        "type": "str",
        "list": false,
        "field_type": "select"
      },
      "judgement_prompt": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "judgement_prompt",
        "display_name": "judgement_prompt",
        "type": "str",
        "list": false,
        "field_type": "textarea"
      },
      "judgement_end_output": {
        "required": false,
        "placeholder": "",
        "show": false,
        "value": "",
        "name": "judgement_end_output",
        "display_name": "judgement_end_output",
        "type": "str",
        "list": false,
        "field_type": "input"
      },
    }
  }
}