<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import SimpleFormItem from '@/components/SimpleFormItem.vue'
import { settingAPI } from "@/api/user"

const { t } = useI18n()

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  },
  settings: {
    type: Object,
    default: () => ({})
  }
})

const open = ref(props.open)
const settings = ref(props.settings)
const saving = ref(false)

const saveSettings = async () => {
  saving.value = true
  settings.value.data.initial_setup = true
  await settingAPI('update', settings.value)
  message.success(t('settings.save_success'))
  saving.value = false
  open.value = false
}
</script>

<template>
  <a-modal v-model:open="open" :title="t('layouts.workspaceLayout.initial_setup')" @ok="saveSettings" :closable="false"
    :maskClosable="false" :cancelButtonProps="{ style: { display: 'none' } }">
    <a-flex vertical gap="large">
      <SimpleFormItem type="select" v-model="settings.data.website_domain" :title="t('settings.website_domain')"
        :description="t('layouts.workspaceLayout.domain_tip')" :options="[
          { label: 'vectorvein.ai', value: 'vectorvein.ai' },
          { label: 'vectorvein.com', value: 'vectorvein.com' },
        ]" />
      <a-alert :message="t('layouts.workspaceLayout.setting_tip1')"
        :description="t('layouts.workspaceLayout.setting_tip2')" type="info" show-icon />
    </a-flex>
  </a-modal>
</template>