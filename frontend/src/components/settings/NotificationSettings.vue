<script setup>
import { Remind } from '@/icons'
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { settingAPI } from '@/api/user'

const model = defineModel({ type: Object, default: () => ({ enabled: false, language: 'zh-CN' }) })
const { t, locale } = useI18n()
const testing = ref(false)
const setEnabled = enabled => { model.value = { enabled, language: locale.value === 'en-US' ? 'en-US' : 'zh-CN' } }
const testNotification = async () => {
  if (testing.value) return
  testing.value = true
  try {
    const response = await settingAPI('test_notification', { language: locale.value === 'en-US' ? 'en-US' : 'zh-CN' })
    if (response.status !== 200) throw new Error()
    message.success(t('settings.notifications_test_submitted'))
  } catch { message.error(t('settings.notifications_test_failed')) }
  finally { testing.value = false }
}
</script>

<template>
  <a-flex vertical gap="middle" class="notification-settings">
    <a-flex align="center" justify="space-between" gap="middle" wrap="wrap" class="notification-row">
      <div class="notification-copy"><strong>{{ t('settings.notifications_enable') }}</strong><p>{{ t('settings.notifications_description') }}</p></div>
      <a-flex align="center" gap="small" wrap="wrap" class="notification-actions">
        <a-switch :checked="model.enabled" :aria-label="t('settings.notifications_enable')" @update:checked="setEnabled" />
        <a-button :loading="testing" @click="testNotification">
          <template #icon><Remind /></template>
          {{ t('settings.notifications_test') }}
        </a-button>
      </a-flex>
    </a-flex>
    <p>{{ t('settings.notifications_help') }}</p>
  </a-flex>
</template>

<style scoped>
.notification-settings { max-width: 720px; }
.notification-copy { flex: 1 1 260px; min-width: 0; }
.notification-actions { flex: 0 1 auto; }
p { margin: 6px 0 0; color: var(--site-secondary-text-color); line-height: 1.6; }
</style>
