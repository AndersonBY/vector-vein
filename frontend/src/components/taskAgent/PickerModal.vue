<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { theme } from 'ant-design-vue'
import './picker.css'

defineProps({ open: Boolean, title: String, confirmDisabled: Boolean })
defineEmits(['confirm', 'cancel'])
const { t } = useI18n()
const { token } = theme.useToken()
// The modal is teleported outside the page's theme container.
const colors = computed(() => ({
  '--component-background': token.value.colorBgContainer,
  '--gray-background': token.value.colorFillQuaternary,
  '--more-hover-background': token.value.colorFillTertiary,
  '--light-border': `1px solid ${token.value.colorBorderSecondary}`,
  '--site-text-color': token.value.colorText,
  '--site-secondary-text-color': token.value.colorTextSecondary,
  '--color-primary': token.value.colorPrimary,
}))
</script>

<template>
  <a-modal
    :open="open"
    :title="title"
    :width="1100"
    centered
    class="task-agent-picker-modal"
    :style="colors"
    :ok-text="t('workspace.taskAgentSpace.picker.confirm')"
    :cancel-text="t('common.cancel')"
    :ok-button-props="{ disabled: confirmDisabled }"
    @ok="$emit('confirm')"
    @cancel="$emit('cancel')"
  >
    <div class="task-agent-picker-body">
      <div class="picker-toolbar"><slot name="toolbar" /></div>
      <div class="picker-content">
        <section class="picker-list-panel"><slot name="list" /></section>
        <section class="picker-detail-panel"><slot name="detail" /></section>
      </div>
    </div>
  </a-modal>
</template>
