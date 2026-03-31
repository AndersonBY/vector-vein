<script setup>
const value = defineModel()

const presets = [
  { label: "Every 5 min", value: "*/5 * * * *" },
  { label: "Hourly", value: "0 * * * *" },
  { label: "Daily 09:00", value: "0 9 * * *" },
  { label: "Weekdays 09:00", value: "0 9 * * 1-5" },
]

const applyPreset = (cronExpression) => {
  value.value = cronExpression
}
</script>

<template>
  <a-flex vertical gap="small">
    <a-input v-model:value="value" placeholder="* * * * *" />
    <a-flex wrap="wrap" gap="small">
      <a-tag v-for="preset in presets" :key="preset.value" class="cron-preset" @click="applyPreset(preset.value)">
        {{ preset.label }}
      </a-tag>
    </a-flex>
  </a-flex>
</template>

<style scoped>
.cron-preset {
  cursor: pointer;
}
</style>
