export function createTemplateData() {
  return {
    description: "Desktop schedule trigger",
    task_name: "triggers.schedule_trigger",
    has_inputs: false,
    template: {
      schedule: {
        required: true,
        placeholder: "",
        show: false,
        value: "0 9 * * *",
        name: "schedule",
        display_name: "schedule",
        type: "str",
        list: false,
        field_type: "cron",
      },
    },
  }
}
