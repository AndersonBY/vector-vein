# Visual schedule editor

`frontend/src/components/scheduling/ScheduleEditor.vue` provides a shared schedule form. Workflow schedule management and the ScheduleTrigger node use the same component.

## Component interface

```vue
<ScheduleEditor
  v-model="cronExpression"
  v-model:recurrence="recurrence"
  v-model:timezone="timezone"
  :disabled="saving"
  @validity-change="scheduleValid = $event"
/>
```

`modelValue` contains a five-field Cron expression; the form never requires users to type it. `recurrence` is `null` or an object with exactly `unit`, `interval`, and `anchor_date`. `timezone` is an IANA time zone. Parents must block submission while `validity-change` reports `false`.

The component emits data changes only after user edits. Mounting or refreshing external props does not rewrite stored values. Valid expressions that cannot be represented by the visual controls remain unchanged until the user explicitly selects a new repeat mode. Localized summaries are available through `formatSchedule(expression, recurrence, t)` in `frontend/src/utils/schedule.js`.

## Repeat rules

- Daily, weekdays, and weekly schedules select a local time; weekly schedules support multiple weekdays.
- Custom minutes and hours use intervals that divide the hour or day evenly. They align to clock boundaries rather than the moment the schedule is saved.
- Custom days, weeks, and months accept an interval. Intervals greater than one require a start date. Supported ranges are 1–365 days, 1–52 weeks, and 1–12 months.
- Daily intervals count calendar dates from the start date. Weekly intervals count weeks beginning Monday, including the week containing the start date. Monthly intervals count calendar months from the start month. No run occurs before the start date.
- Monthly schedules skip months without the selected date; they do not move day 31 to the last day of a shorter month.
- Existing interval-one rules retain their start date when editing other fields. Selecting a different repeat mode clears that rule.
- All dates and times are interpreted in the selected time zone. Nonexistent local times during a daylight-saving transition are skipped. The next-run search iterates actual UTC minutes.

## Storage and execution

`WorkflowRunSchedule.cron_expression` stores the Cron candidate times. `WorkflowRunSchedule.data.timezone` and `.recurrence` store the time zone and calendar filter. No schema migration is required. The scheduler applies both the Cron expression and the recurrence filter. The API validates all three fields before saving.

Older schedules without a time zone use `Asia/Shanghai`, matching the scheduler's existing default. New schedules use the local browser time zone. Older API callers that omit `recurrence` retain it when the expression is unchanged; changing the expression clears the old rule. Explicit `recurrence: null` also clears it.

The Agent schedule form uses the same component. Its persistence and execution are described in [Agent scheduling](task-agent-scheduling.md).
