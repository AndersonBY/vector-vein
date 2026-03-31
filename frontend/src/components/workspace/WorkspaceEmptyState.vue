<script setup>
const props = defineProps({
  title: {
    type: String,
    required: true,
  },
  description: {
    type: String,
    default: '',
  },
})
</script>

<template>
  <div class="workspace-empty-state">
    <a-empty>
      <template #description>
        <a-flex vertical align="center" gap="small">
          <a-typography-text strong>
            {{ title }}
          </a-typography-text>
          <a-typography-text type="secondary">
            {{ description }}
          </a-typography-text>
          <slot />
        </a-flex>
      </template>
    </a-empty>
  </div>
</template>

<style scoped>
.workspace-empty-state {
  padding: 24px 8px;
}
</style>
