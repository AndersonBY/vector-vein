/**
 * @Author: Bi Ying
 * @Date:   2024-04-15 00:41:55
 * @Last Modified by:   Bi Ying
 * @Last Modified time: 2024-04-15 00:42:14
 */
export function createTemplateData() {
  return {
    "description": "description",
    "task_name": "tools.workflow_invoke",
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
    }
  }
}