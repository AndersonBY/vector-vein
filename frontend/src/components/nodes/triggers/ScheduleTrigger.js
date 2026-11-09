export function createTemplateData() {
  return {
    description: "Desktop schedule trigger",
    task_name: "triggers.schedule_trigger",
    has_inputs: false,
    template: {
      recurrence: { name: 'recurrence', value: null, type: 'dict', show: false, required: false, field_type: 'json' },
      timezone: { name: 'timezone', value: Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai', type: 'str', show: false, required: false, field_type: 'str' },
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
