export function createTemplateData() {
  return {
    description: "Collect human confirmation or notes before continuing.",
    task_name: "control_flows.human_feedback",
    has_inputs: true,
    template: {
      hint_message: {
        required: true,
        placeholder: "",
        show: true,
        value: "",
        name: "hint_message",
        display_name: "hint_message",
        type: "str",
        list: false,
        field_type: "textarea",
      },
      human_input: {
        required: true,
        placeholder: "",
        show: true,
        value: "",
        name: "human_input",
        display_name: "human_input",
        type: "str",
        list: false,
        field_type: "textarea",
      },
      output: {
        required: true,
        placeholder: "",
        show: false,
        value: "",
        name: "output",
        display_name: "output",
        type: "str",
        list: false,
        field_type: "",
        is_output: true,
      },
    },
  }
}
