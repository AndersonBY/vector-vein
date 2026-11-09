<script setup>
import { computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { theme } from 'ant-design-vue'
import { CheckOne, Down } from '@/icons'
const props = defineProps({ modelValue: { type: String, default: 'auto' }, disabled: Boolean })
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const { token } = theme.useToken()
const open = ref(false)
const options = computed(() => ['ask', 'auto', 'full'].map(value => ({ value, label: t('workspace.taskAgentSpace.permission_' + value), description: t('workspace.taskAgentSpace.permission_' + value + '_hint') })))
const selectMode = ({ key }) => {
  if (props.disabled || !options.value.some(option => option.value === key)) return
  emit('update:modelValue', key)
  open.value = false
}
</script>
<template>
  <div class="permission-picker" :class="{ 'full-access': props.modelValue === 'full' }" :style="{ '--permission-text': token.colorText, '--permission-hover': token.colorFillTertiary, '--color-primary': token.colorPrimary }">
    <a-dropdown v-model:open="open" :trigger="['click']" placement="topLeft" :disabled="disabled">
      <button type="button" class="permission-trigger" :disabled="disabled" :aria-label="t('workspace.taskAgentSpace.permissions')" :aria-expanded="open" aria-haspopup="menu">
        <span>{{ t('workspace.taskAgentSpace.permission_' + props.modelValue) }}</span>
        <Down :size="12" aria-hidden="true" />
      </button>
      <template #overlay>
        <a-menu class="permission-menu" :style="{ '--permission-secondary': token.colorTextSecondary }" :selected-keys="[props.modelValue]" @click="selectMode">
          <a-menu-item v-for="option in options" :key="option.value" :disabled="disabled">
            <div class="permission-option"><div><strong>{{ option.label }}</strong><small>{{ option.description }}</small></div><CheckOne v-if="props.modelValue === option.value" :size="16" aria-hidden="true" /></div>
          </a-menu-item>
        </a-menu>
      </template>
    </a-dropdown>
  </div>
</template>
<style scoped>
.permission-picker { flex-shrink: 0; }
.permission-trigger { display: inline-flex; align-items: center; gap: 6px; height: 30px; padding: 0 10px; border: 0; border-radius: 999px; background: transparent; color: var(--permission-text); font: inherit; font-size: 12px; cursor: pointer; }
.permission-trigger:hover:not(:disabled) { background: var(--permission-hover); }
.permission-trigger:disabled { cursor: default; opacity: .5; }
.permission-trigger:focus-visible { outline: 2px solid var(--color-primary); outline-offset: 2px; }
.permission-menu { width: 380px; max-width: calc(100vw - 24px); }
.permission-option { display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 5px 0; white-space: normal; }
.permission-option > div { min-width: 0; }
.permission-option > svg { flex-shrink: 0; }
.permission-option strong { display: block; font-weight: 500; }
.permission-option small { display: block; margin-top: 4px; color: var(--permission-secondary); line-height: 1.5; }
.full-access .permission-trigger { color: #c86524; }
</style>
