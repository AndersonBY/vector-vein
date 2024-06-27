<script setup>

const props = defineProps({
  text: {
    type: String,
    required: false,
    default: '',
  },
  block: {
    type: Boolean,
    default: false,
  },
  danger: {
    type: Boolean,
    default: false,
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  ghost: {
    type: Boolean,
    default: false,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  shape: {
    type: String,
    default: 'default',
  },
  size: {
    type: String,
    default: 'middle',
  },
  type: {
    type: String,
    default: 'default',
  },
})
</script>

<template>
  <a-button class="icon-button" :block="block" :danger="danger" :disabled="disabled" :ghost="ghost" :loading="loading"
    :shape="shape" :size="size" :type="type">
    <template #icon>
      <slot name="icon"></slot>
    </template>
    <span v-if="text.length > 0" class="icon-button-text">
      {{ text }}
    </span>
  </a-button>
</template>

<style>
.icon-button {
  display: flex;
  align-items: center;
  overflow: hidden;
}

.icon-button:hover {
  gap: 2px;
}

.icon-button .icon-button-text {
  max-width: 0;
  white-space: nowrap;
  overflow: hidden;
  transition: max-width 0.2s ease, opacity 0.2s ease;
  opacity: 0;
  transition-delay: 0s;
  margin-inline-start: 0 !important;
}

.icon-button:hover .icon-button-text {
  max-width: 2000px;
  opacity: 1;
  transition-delay: 0.2s;
  margin-inline-start: 8px;
}
</style>