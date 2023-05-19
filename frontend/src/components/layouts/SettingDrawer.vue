<script setup>
import { defineComponent, ref, reactive, toRaw, onBeforeMount } from "vue"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { useUserSettingsStore } from '@/stores/userSettings'
import { settingAPI } from "@/api/user"

defineComponent({
  name: 'SettingDrawer',
})

const { t } = useI18n()
const loading = ref(true)
const userSettings = useUserSettingsStore()
onBeforeMount(async () => {
  const res = await settingAPI('get', {})
  userSettings.setSetting(res.data)
  settingForm.id = res.data.id
  settingForm.data.openai_api_type = res.data.data.openai_api_type || 'open_ai'
  settingForm.data.openai_api_key = res.data.data.openai_api_key || ''
  settingForm.data.openai_api_base = res.data.data.openai_api_base || ''
  settingForm.data.openai_chat_engine = res.data.data.openai_chat_engine || ''
  settingForm.data.openai_embedding_engine = res.data.data.openai_embedding_engine || ''
  settingForm.data.output_folder = res.data.data.output_folder || './'
  settingForm.data.email_user = res.data.data.email_user || ''
  settingForm.data.email_password = res.data.data.email_password || ''
  settingForm.data.email_smtp_host = res.data.data.email_smtp_host || ''
  settingForm.data.email_smtp_port = res.data.data.email_smtp_port || ''
  settingForm.data.email_smtp_ssl = res.data.data.email_smtp_ssl || true
  loading.value = false
  open.value = false
})
const settingForm = reactive({
  id: 1,
  data: {
    openai_api_type: 'openai',
    openai_api_key: '',
    openai_api_base: '',
    openai_chat_engine: '',
    openai_embedding_engine: '',
    output_folder: './',
    email_user: '',
    email_password: '',
    email_smtp_host: '',
    email_smtp_port: '',
    email_smtp_ssl: true,
  }
})
const open = ref(false)

const showDrawer = async () => {
  open.value = true
  loading.value = false
}

const onClose = () => {
  open.value = false
}

const selectFolder = async () => {
  try {
    const selectedFolder = await window.pywebview.api.open_folder_dialog(settingForm.output_folder)
    if (!selectedFolder) {
      return
    }
    settingForm.data.output_folder = selectedFolder[0]
  } catch (error) {
    console.log(error)
  }
}

const saveSetting = async () => {
  loading.value = true
  await userSettings.setSetting(toRaw(settingForm))
  await settingAPI('update', settingForm)
  message.success(t('components.layout.settingDrawer.save_success'))
  loading.value = false
  open.value = false
}
</script>

<template>
  <a-button type="primary" @click="showDrawer">
    {{ t('components.layout.settingDrawer.open') }}
  </a-button>
  <a-drawer :title="t('components.layout.settingDrawer.my_setting')" size="large" :open="open" @close="onClose">
    <template #extra>
      <a-button type="primary" @click="saveSetting">
        {{ t('components.layout.settingDrawer.save') }}
      </a-button>
    </template>
    <a-spin :spinning="loading">
      <a-row justify="space-between" align="middle">
        <a-col :span="24">
          <a-form>
            <a-form-item :label="t('components.layout.settingDrawer.openai_api_type')">
              <a-radio-group v-model:value="settingForm.data.openai_api_type">
                <a-radio-button value="open_ai">
                  {{ t('components.layout.settingDrawer.openai') }}
                </a-radio-button>
                <a-radio-button value="azure">
                  {{ t('components.layout.settingDrawer.azure') }}
                </a-radio-button>
              </a-radio-group>
            </a-form-item>

            <a-form-item :label="t('components.layout.settingDrawer.openai_api_key')">
              <a-input-password v-model:value="settingForm.data.openai_api_key" />
            </a-form-item>

            <a-form-item :label="t('components.layout.settingDrawer.openai_api_base')"
              v-if="settingForm.data.openai_api_type == 'azure'">
              <a-input v-model:value="settingForm.data.openai_api_base" />
            </a-form-item>

            <a-form-item :label="t('components.layout.settingDrawer.openai_chat_engine')"
              v-if="settingForm.data.openai_api_type == 'azure'">
              <a-input v-model:value="settingForm.data.openai_chat_engine" />
            </a-form-item>

            <a-form-item :label="t('components.layout.settingDrawer.openai_embedding_engine')"
              v-if="settingForm.data.openai_api_type == 'azure'">
              <a-input v-model:value="settingForm.data.openai_embedding_engine" />
            </a-form-item>

            <a-divider />

            <a-row :gutter="[12, 12]">
              <a-col :span="24">
                <a-space>
                  <a-typography-text>
                    {{ t('components.layout.settingDrawer.output_folder') }}:
                  </a-typography-text>
                  <a-typography-text>
                    {{ settingForm.data.output_folder }}
                  </a-typography-text>
                </a-space>
              </a-col>
              <a-col :span="24">
                <a-button type="primary" block @click="selectFolder">
                  {{ t('components.layout.settingDrawer.select_folder') }}
                </a-button>
              </a-col>
            </a-row>

            <a-divider>
              {{ t('components.layout.settingDrawer.email_settings') }}
            </a-divider>

            <a-form-item :label="t('components.layout.settingDrawer.email_user')">
              <a-input v-model:value="settingForm.data.email_user" />
            </a-form-item>

            <a-form-item :label="t('components.layout.settingDrawer.email_password')">
              <a-input-password v-model:value="settingForm.data.email_password" />
            </a-form-item>

            <a-form-item :label="t('components.layout.settingDrawer.email_smtp_host')">
              <a-input v-model:value="settingForm.data.email_smtp_host" />
            </a-form-item>

            <a-form-item :label="t('components.layout.settingDrawer.email_smtp_port')">
              <a-input-number v-model:value="settingForm.data.email_smtp_port" />
            </a-form-item>

            <a-form-item :label="t('components.layout.settingDrawer.email_smtp_ssl')">
              <a-switch v-model:checked="settingForm.data.email_smtp_ssl" />
            </a-form-item>

          </a-form>
        </a-col>
      </a-row>
    </a-spin>
  </a-drawer>
</template>