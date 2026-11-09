<script setup>
import { Refresh } from '@/icons'
import IconButton from '@/components/IconButton.vue'
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { settingAPI } from '@/api/user'

const { t } = useI18n()
const tr = key => t(`settings.desktop_window.${key}`)
const loading = ref(true), saving = ref(false), failed = ref(false), minimizing = ref(false)
const closeAction = ref('ask'), trayAvailable = ref(false)
let alive = true, generation = 0

const load = async () => {
  if (saving.value) return
  const request = ++generation
  loading.value = true; failed.value = false
  try {
    const response = await settingAPI('get_window_setting', {})
    if (!alive || request !== generation) return
    if (response.status !== 200) throw new Error()
    closeAction.value = response.data.close_action
    trayAvailable.value = response.data.tray_available === true
  } catch { if (alive && request === generation) failed.value = true }
  finally { if (alive && request === generation) loading.value = false }
}
const save = async value => {
  if (saving.value || loading.value || !['ask', 'tray', 'exit'].includes(value)) return
  const request = ++generation
  saving.value = true
  try {
    const response = await settingAPI('update_window_setting', { close_action: value })
    if (!alive || request !== generation) return
    if (response.status !== 200) throw new Error()
    closeAction.value = response.data.close_action
    trayAvailable.value = response.data.tray_available === true
    message.success(tr('saved'))
  } catch { if (alive && request === generation) message.error(tr('save_failed')) }
  finally { if (alive && request === generation) saving.value = false }
}
const minimize = async () => {
  if (!trayAvailable.value || minimizing.value) return
  minimizing.value = true
  try {
    const response = await settingAPI('minimize_to_tray', {})
    if (response.status !== 200) throw new Error()
  } catch { if (alive) message.error(tr('minimize_failed')) }
  finally { if (alive) minimizing.value = false }
}
const refreshOnFocus = () => { if (!loading.value) load() }
onMounted(() => { load(); window.addEventListener?.('focus', refreshOnFocus) })
onBeforeUnmount(() => { alive = false; generation++; window.removeEventListener?.('focus', refreshOnFocus) })
</script>

<template>
  <div class="desktop-window-settings">
    <a-alert v-if="failed" type="warning" show-icon :message="tr('load_failed')"><template #action><IconButton :text="t('workspace.taskAgentSpace.retry')" @click="load"><template #icon><Refresh /></template></IconButton></template></a-alert>
    <a-spin :spinning="loading">
      <a-form layout="vertical">
        <a-form-item :label="tr('close_label')" :extra="tr('immediate')">
          <a-radio-group :value="closeAction" :disabled="loading || saving || failed" class="close-action-options" :aria-label="tr('close_label')" @change="save($event.target.value)">
            <a-radio value="ask">{{ tr('ask') }}</a-radio>
            <a-radio value="tray" :disabled="!trayAvailable">{{ tr('tray') }}</a-radio>
            <a-radio value="exit">{{ tr('exit') }}</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
      <p>{{ tr('background_hint') }}</p>
      <p>{{ tr('restore_hint') }}</p>
      <a-alert v-if="!loading && !failed && !trayAvailable" type="warning" show-icon :message="tr('unavailable')" />
      <a-button :loading="minimizing" :disabled="loading || saving || !trayAvailable" @click="minimize">{{ tr('minimize_now') }}</a-button>
    </a-spin>
  </div>
</template>

<style scoped>
.desktop-window-settings { max-width: 720px; }
.close-action-options { display: flex; flex-direction: column; gap: 16px; padding: 4px 0; }
.desktop-window-settings p { color: var(--site-secondary-text-color); line-height: 1.7; }
.desktop-window-settings :deep(.ant-alert) { margin-bottom: 16px; }
</style>
