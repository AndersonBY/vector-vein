<script setup>
import { useAttrs } from 'vue'

defineOptions({ inheritAttrs: false })
const attrs = useAttrs()
defineProps({
  text: { type: String, required: true },
  block: Boolean,
  danger: Boolean,
  disabled: Boolean,
  ghost: Boolean,
  loading: Boolean,
  shape: { type: String, default: 'default' },
  size: { type: String, default: 'middle' },
  type: { type: String, default: 'text' },
})
</script>

<template>
  <span class="icon-button-root">
  <a-tooltip :title="text" :trigger="['hover', 'focus']">
    <span class="icon-button-trigger" :tabindex="disabled ? 0 : undefined" :aria-label="disabled ? text : undefined">
      <a-button v-bind="attrs" class="icon-button" :block="block" :danger="danger" :disabled="disabled"
        :ghost="ghost" :loading="loading" :shape="shape" :size="size" :type="type"
        :aria-label="attrs['aria-label'] || text">
        <template #icon><span class="icon-button-symbol" aria-hidden="true"><slot name="icon" /></span></template>
      </a-button>
    </span>
  </a-tooltip>
  </span>
</template>

<style scoped>
.icon-button-root, .icon-button-trigger { display: inline-flex; flex: 0 0 auto; vertical-align: middle; border-radius: 6px; }
.icon-button.ant-btn { display: inline-flex; align-items: center; justify-content: center; padding: 0; font-size: 16px; }
.icon-button.ant-btn:not(.ant-btn-block) { width: 32px; min-width: 32px; height: 32px; }
.icon-button.ant-btn-sm:not(.ant-btn-block) { width: 28px; min-width: 28px; height: 28px; }
.icon-button.ant-btn-lg:not(.ant-btn-block) { width: 40px; min-width: 40px; height: 40px; font-size: 18px; }
.icon-button-symbol { display: inline-flex; align-items: center; justify-content: center; pointer-events: none; }
.icon-button:focus-visible, .icon-button-trigger:focus-visible { outline: 2px solid var(--color-primary, #28c5e5); outline-offset: 2px; }
</style>
