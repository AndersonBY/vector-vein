<script setup>
defineProps({
  title: { type: String, required: true },
  description: { type: String, default: '' },
})
</script>

<template>
  <header class="workspace-page-header">
    <div class="page-heading">
      <a-typography-title :level="2" class="page-title">{{ title }}</a-typography-title>
      <a-typography-paragraph v-if="description" type="secondary" class="page-description">
        {{ description }}
      </a-typography-paragraph>
    </div>
    <a-flex v-if="$slots.actions" wrap gap="small" class="page-actions">
      <slot name="actions" />
    </a-flex>
  </header>
</template>

<style scoped>
.workspace-page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px 24px;
  padding: 8px 0 16px;
}
.page-heading { min-width: 0; }
.page-title { margin: 0; font-size: 24px; }
.page-description { margin: 4px 0 0; }
.page-actions { align-items: center; }
</style>
