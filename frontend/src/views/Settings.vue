<script setup>
import { ref, reactive, toRaw, onBeforeMount, computed } from "vue"
import { onBeforeRouteLeave } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  More,
  Mail,
  Robot,
  Search,
  Refresh,
  CubeFive,
  Acoustic,
  Microphone,
  MenuFoldOne,
  KeyboardOne,
  MenuUnfoldOne,
  Communication,
  DatabaseNetworkPoint,
  Api,
} from '@/icons'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import { useModelCatalogStore } from '@/stores/modelCatalog'
import EndpointSettings from "@/components/settings/EndpointSettings.vue"
import ShortcutSettings from '@/components/settings/ShortcutSettings.vue'
import LLMTabsSettings from "@/components/settings/LLMTabsSettings.vue"
import EmbeddingTabsSettings from "@/components/settings/EmbeddingTabsSettings.vue"
import TTSSettings from "@/components/settings/TTSSettings.vue"
import { getChatModelOptions } from '@/utils/common'
import { CHAT_PROVIDER_LABEL_MAP } from '@/utils/modelProviders'
import { hashObject } from "@/utils/util"
import { settingAPI, hardwareAPI } from "@/api/user"
import QuestionPopover from "@/components/QuestionPopover.vue"
import ModelPreferenceSettings from '@/components/settings/ModelPreferenceSettings.vue'
import { MODEL_PREFERENCES, validModelPair } from '@/utils/modelPreferences'
import { deepCopy } from '@/utils/util'
import CustomLLMSettings from "@/components/settings/CustomLLMSettings.vue"

const { t } = useI18n()
const loading = ref(true)

const userSettings = useUserSettingsStore()
const modelCatalogStore = useModelCatalogStore()
const { theme } = storeToRefs(userSettings)
const componentTheme = computed(() => theme.value == 'default' ? 'light' : 'dark')

const microphoneDeviceOptions = ref([])
const chatModelOptions = ref(getChatModelOptions())

const settingForm = reactive({
  id: 1,
  data: {}
})

const refreshingMics = ref(false)
const refreshMics = async () => {
  refreshingMics.value = true
  const devices = await hardwareAPI('list_microphones', {})
  microphoneDeviceOptions.value = devices.data.map((device) => ({
    label: device.name,
    value: device.index,
  }))
  refreshingMics.value = false
}

const savedSettingsHash = ref('')
const savedShortcutsHash = ref('')
const endpointEditor = ref(null)
const endpointDraftDirty = ref(false)
const unsavedChanges = computed(() => !loading.value &&
  (endpointDraftDirty.value || hashObject(settingForm.data) !== savedSettingsHash.value))
onBeforeRouteLeave(() => !unsavedChanges.value || window.confirm(t('settings.leave_unsaved_confirm')))

onBeforeMount(async () => {
  const defaultSettingsResp = await settingAPI('get_default_settings')
  const res = await settingAPI('get', {})

  userSettings.setSetting(res.data)

  const userData = res.data.data || {}
  settingForm.id = res.data.id
  settingForm.data = deepCopy({ ...defaultSettingsResp.data, ...userData })
  settingForm.data.model_preferences ||= {}

  // Merge API settings from response
  if (res.data.api) {
    settingForm.data.api = {
      ...settingForm.data.api,
      ...res.data.api
    }
  }

  // Set default API settings if not present
  if (!settingForm.data.api) {
    settingForm.data.api = {
      enabled: true,
      host: '127.0.0.1',
      port: 8787,
      current_url: ''
    }
  }

  await refreshMics()

  savedSettingsHash.value = hashObject(settingForm.data)
  savedShortcutsHash.value = hashObject(settingForm.data.shortcuts || {})

  loading.value = false
})

const selectFolder = async (settingsKey) => {
  try {
    const selectedFolder = await window.pywebview.api.open_folder_dialog(
      settingForm.data[settingsKey]
    )
    if (!selectedFolder) {
      return
    }
    settingForm.data[settingsKey] = selectedFolder
  } catch (error) {
    console.error(error)
  }
}

const saving = ref(false)
const saveSetting = async (updateShortcuts = false) => {
  if (saving.value) return false
  if (!validPreferences.value) {
    selectedKeys.value = ['model_preferences']
    message.error(t('components.model_picker.invalid_preferences'))
    return false
  }
  const pendingEndpoints = endpointEditor.value?.prepareSave()
  if (pendingEndpoints === false) {
    selectedKeys.value = ['endpoints']
    return false
  }
  saving.value = true
  try {
    const submitted = deepCopy(toRaw(settingForm))
    if (pendingEndpoints) submitted.data.llm_settings.endpoints = pendingEndpoints
    const response = await settingAPI('update', { ...submitted, update_shortcuts: updateShortcuts === true ||
      hashObject(submitted.data.shortcuts || {}) !== savedShortcutsHash.value })
    if (response.status !== 200) throw new Error('Settings update failed')
    const saved = response.data || submitted
    userSettings.setSetting(saved)
    modelCatalogStore.setPayloadFromSettings(saved)
    message.success(t('settings.save_success'))
    chatModelOptions.value = getChatModelOptions()
    savedSettingsHash.value = hashObject(submitted.data)
    savedShortcutsHash.value = hashObject(submitted.data.shortcuts || {})
    if (pendingEndpoints) settingForm.data.llm_settings.endpoints = submitted.data.llm_settings.endpoints
    endpointEditor.value?.markSaved()
    endpointDraftDirty.value = false
    return true
  } catch {
    message.error(t('components.model_picker.settings_save_failed'))
    return false
  } finally {
    saving.value = false
  }
}

const preferenceOptions = computed(() => {
  // Use the settings draft so newly enabled models can be assigned before saving.
  const backends = settingForm.data.llm_settings?.backends || {}
  const options = Object.entries(backends).filter(([key]) => key !== 'local').map(([key, backend]) => ({
    value: key, label: CHAT_PROVIDER_LABEL_MAP[key] || key, children: Object.entries(backend.models || {}).filter(([, model]) => model.enabled !== false).map(([value, model]) => ({value, label: model.id || value})),
  })).filter(provider => provider.children.length)
  for (const [family, models] of Object.entries(settingForm.data.custom_llms || {})) {
    const children = models.filter(model => backends.local?.models?.[model]?.enabled !== false).map(value => ({ value, label: value }))
    if (children.length) options.push({ value: '_local__' + family, label: family, children })
  }
  return options.map(provider => ({...provider, value: provider.value.startsWith('_local__') ? provider.value : CHAT_PROVIDER_LABEL_MAP[provider.value] || provider.value}))
})
const validPreferences = computed(() => MODEL_PREFERENCES.every(key => {
  const value = settingForm.data.model_preferences?.[key]
  return !value || (!value.model && !value.model_provider) || validModelPair(preferenceOptions.value, value.model_provider, value.model)
}))
const selectedKeys = ref(['endpoints'])
const collapsed = ref(false)
const sidebarHover = ref(false)
const onCollapse = (switchToCollapsed) => {
  collapsed.value = switchToCollapsed
}
const menuClick = async ({ key }) => {
  selectedKeys.value = [key]
}

const websiteDomainOptions = [
  { label: 'vectorvein.ai', value: 'vectorvein.ai' },
  { label: 'vectorvein.com', value: 'vectorvein.com' },
]

</script>

<template>
  <div class="main-container">
    <a-layout class="main-layout">
      <a-layout-sider class="sider-menu" :defaultCollapsed="collapsed" v-model:collapsed="collapsed" :trigger="null"
        collapsible :collapsedWidth="48" @collapse="onCollapse" breakpoint="lg" :theme="componentTheme"
        :style="{ overflowY: sidebarHover ? 'auto' : 'hidden' }" @mouseover="sidebarHover = true"
        @mouseleave="sidebarHover = false">
        <a-menu v-model:selectedKeys="selectedKeys" @click="menuClick" :theme="componentTheme" mode="inline"
          style="height: 100%; padding-bottom: 40px;">
          <a-menu-item key="endpoints">
            <template #icon>
              <DatabaseNetworkPoint />
            </template>
            {{ t('settings.endpoints') }}
          </a-menu-item>
          <a-menu-item key="llms">
            <template #icon>
              <Robot />
            </template>
            {{ t('settings.llms') }}
          </a-menu-item>
          <a-menu-item key="model_preferences">
            <template #icon><Robot /></template>
            {{ t('components.model_picker.preferences_title') }}
          </a-menu-item>
          <a-menu-item key="custom_llms">
            <template #icon>
              <Robot />
            </template>
            {{ t('settings.custom_llms') }}
          </a-menu-item>
          <a-menu-item key="asr">
            <template #icon>
              <Microphone />
            </template>
            {{ t('settings.asr') }}
          </a-menu-item>
          <a-menu-item key="tts">
            <template #icon>
              <Acoustic />
            </template>
            {{ t('settings.tts') }}
          </a-menu-item>
          <a-menu-item key="embedding_models">
            <template #icon>
              <CubeFive />
            </template>
            {{ t('settings.embedding_models') }}
          </a-menu-item>
          <a-menu-item key="agent">
            <template #icon>
              <Communication />
            </template>
            {{ t('settings.agent_settings') }}
          </a-menu-item>
          <a-menu-item key="web_search">
            <template #icon>
              <Search />
            </template>
            {{ t('settings.web_search') }}
          </a-menu-item>
          <a-menu-item key="api">
            <template #icon>
              <Api />
            </template>
            {{ t('settings.api_settings') }}
          </a-menu-item>
          <a-menu-item key="shortcut">
            <template #icon>
              <KeyboardOne />
            </template>
            {{ t('settings.shortcut_settings') }}
          </a-menu-item>
          <a-menu-item key="email">
            <template #icon>
              <Mail />
            </template>
            {{ t('settings.email_settings') }}
          </a-menu-item>
          <a-menu-item key="other">
            <template #icon>
              <More />
            </template>
            {{ t('settings.other') }}
          </a-menu-item>
          <div class="collapse-button">
            <a-button type="text" @click="onCollapse(!collapsed)">
              <MenuFoldOne v-if="collapsed" class="trigger" />
              <MenuUnfoldOne v-else class="trigger" />
            </a-button>
          </div>
        </a-menu>
      </a-layout-sider>

      <a-layout-content>
        <div class="settings-toolbar">
          <a-typography-text v-if="unsavedChanges" type="secondary" role="status">{{ t('settings.unsaved_notice') }}</a-typography-text>
          <a-button type="primary" :loading="saving" :disabled="loading || !unsavedChanges" @click="saveSetting()">
            {{ t('settings.save') }}
          </a-button>
        </div>
        <a-card v-show="selectedKeys == 'endpoints'" :title="t('settings.endpoints')" :loading="loading">
          <EndpointSettings
            ref="endpointEditor" :saving="saving" :save-settings="saveSetting" @dirty="endpointDraftDirty = $event"
            v-if="settingForm.data?.llm_settings?.endpoints && settingForm.data.llm_settings?.backends.local"
            v-model:endpoints="settingForm.data.llm_settings.endpoints"
            v-model:localModels="settingForm.data.llm_settings.backends.local"
            v-model:modelFamilyMap="settingForm.data.custom_llms" />
        </a-card>

        <a-card v-show="selectedKeys == 'llms'" :title="t('settings.llms')" :loading="loading">
          <LLMTabsSettings v-if="settingForm.data.llm_settings?.backends && settingForm.data.llm_settings?.endpoints"
            v-model="settingForm.data.llm_settings.backends" :endpoints="settingForm.data.llm_settings.endpoints" />
        </a-card>

        <a-card v-show="selectedKeys == 'model_preferences'" :title="t('components.model_picker.preferences_title')" :loading="loading">
          <ModelPreferenceSettings v-if="!loading" v-model="settingForm.data.model_preferences" :options="preferenceOptions" />
        </a-card>

        <a-card v-show="selectedKeys == 'custom_llms'" :title="t('settings.custom_llms')" :loading="loading">
          <a-skeleton v-if="loading" active />
          <CustomLLMSettings v-else v-model:localModels="settingForm.data.llm_settings.backends.local"
            v-model:modelFamilyMap="settingForm.data.custom_llms"
            :endpoints="settingForm.data.llm_settings.endpoints" />
        </a-card>

        <a-card v-show="selectedKeys == 'embedding_models'" :title="t('settings.embedding_models')" :loading="loading">
          <a-flex vertical gap="middle">
            <a-alert :message="t('settings.embedding_models')" type="info">
              <template #description>
                <a-typography-paragraph style="margin-bottom: 8px;">
                  {{ t('settings.embedding_settings_tip') }}
                </a-typography-paragraph>
                <a-typography-link target="_blank" href="https://github.com/huggingface/text-embeddings-inference">
                  text-embeddings-inference
                </a-typography-link>
              </template>
            </a-alert>
            <EmbeddingTabsSettings
              v-if="settingForm.data.llm_settings?.embedding_backends && settingForm.data.llm_settings?.endpoints"
              v-model="settingForm.data.llm_settings.embedding_backends"
              :endpoints="settingForm.data.llm_settings.endpoints" />
          </a-flex>
        </a-card>

        <a-card v-show="selectedKeys == 'asr'" :title="t('settings.asr')" :loading="loading">
          <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
            <a-form-item :label="t('settings.microphone_device')">
              <a-flex gap="small" align="center">
                <a-select v-model:value="settingForm.data.microphone_device" :options="microphoneDeviceOptions"
                  style="width: 100%;" />
                <a-tooltip :title="t('common.refresh')">
                  <a-button type=text size="small" :loading="refreshingMics" @click="refreshMics">
                    <Refresh />
                  </a-button>
                </a-tooltip>
              </a-flex>
            </a-form-item>
            <a-form-item :label="t('settings.provider_for_asr')">
              <a-select v-model:value="settingForm.data.asr.provider"
                :options="[{ label: 'OpenAI', value: 'openai' }]" />
            </a-form-item>
          </a-form>
          <a-tabs tab-position="left">
            <a-tab-pane key="openai" tab="OpenAI">
              <a-flex vertical justify="center" gap="middle">
                <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
                  <a-form-item>
                    <template #label>
                      <a-typography-text style="text-wrap: wrap;">
                        {{ t('settings.asr_openai_setting_same_as_llm') }}
                      </a-typography-text>
                    </template>
                    <a-checkbox v-model:checked="settingForm.data.asr.openai.same_as_llm" />
                  </a-form-item>
                  <a-form-item v-if="!settingForm.data.asr.openai.same_as_llm" :label="t('settings.openai_api_base')">
                    <a-input v-model:value="settingForm.data.asr.openai.api_base" />
                  </a-form-item>
                  <a-form-item v-if="!settingForm.data.asr.openai.same_as_llm" :label="t('settings.openai_api_key')">
                    <a-input-password v-model:value="settingForm.data.asr.openai.api_key" />
                  </a-form-item>
                  <a-form-item v-if="!settingForm.data.asr.openai.same_as_llm" :label="t('common.model')">
                    <a-input v-model:value="settingForm.data.asr.openai.model" />
                  </a-form-item>
                </a-form>
              </a-flex>
            </a-tab-pane>
          </a-tabs>
        </a-card>

        <a-card v-show="selectedKeys == 'tts'" :title="t('settings.tts')" :loading="loading">
          <TTSSettings v-model="settingForm.data.tts" />
        </a-card>

        <a-card v-show="selectedKeys == 'web_search'" :title="t('settings.web_search')" :loading="loading">
          <a-tabs tab-position="left">
            <a-tab-pane key="jina.ai" tab="jina.ai">
              <a-flex vertical justify="center" gap="middle">
                <a-alert message="jina.ai" type="info">
                  <template #description>
                    <a-typography-link style="text-align: center;" target="_blank" href="https://jina.ai/reader/">
                      https://jina.ai/reader/
                    </a-typography-link>
                  </template>
                </a-alert>
                <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
                  <a-form-item label="jina.ai API Key">
                    <a-input-password v-model:value="settingForm.data.web_search.jinaai.api_key" />
                  </a-form-item>
                </a-form>
              </a-flex>
            </a-tab-pane>
            <a-tab-pane key="bing" tab="bing">
              <a-flex vertical justify="center" gap="middle">
                <a-alert message="Bing search API" type="info">
                  <template #description>
                    <a-typography-link style="text-align: center;" target="_blank"
                      href="https://www.microsoft.com/en-us/bing/apis/bing-web-search-api">
                      https://www.microsoft.com/en-us/bing/apis/bing-web-search-api
                    </a-typography-link>
                  </template>
                </a-alert>
                <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
                  <a-form-item label="Endpoint">
                    <a-input v-model:value="settingForm.data.web_search.bing.endpoint" />
                  </a-form-item>
                  <a-form-item label="OCP_APIM_SUBSCRIPTION_KEY">
                    <a-input-password v-model:value="settingForm.data.web_search.bing.ocp_apim_subscription_key" />
                  </a-form-item>
                </a-form>
              </a-flex>
            </a-tab-pane>
          </a-tabs>
        </a-card>

        <a-card v-show="selectedKeys == 'api'" :title="t('settings.api_settings')" :loading="loading">
          <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
            <a-form-item :label="t('settings.api_enabled')">
              <a-switch v-model:checked="settingForm.data.api.enabled" />
            </a-form-item>

            <a-form-item :label="t('settings.api_host')">
              <a-input v-model:value="settingForm.data.api.host" :disabled="!settingForm.data.api.enabled" />
            </a-form-item>

            <a-form-item :label="t('settings.api_port')">
              <a-input-number v-model:value="settingForm.data.api.port" :min="1024" :max="65535"
                :disabled="!settingForm.data.api.enabled" style="width: 100%;" />
            </a-form-item>

            <a-form-item :label="t('settings.api_current_url')" v-if="settingForm.data.api.current_url">
              <a-typography-text copyable>
                {{ settingForm.data.api.current_url }}
              </a-typography-text>
            </a-form-item>

            <a-alert :message="t('settings.api_restart_notice')" type="info" show-icon style="margin-top: 16px;" />
          </a-form>
        </a-card>

        <a-card v-show="selectedKeys == 'email'" :title="t('settings.email_settings')" :loading="loading">
          <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
            <a-form-item :label="t('settings.email_user')">
              <a-input v-model:value="settingForm.data.email.user" />
            </a-form-item>

            <a-form-item :label="t('settings.email_password')">
              <a-input-password v-model:value="settingForm.data.email.password" />
            </a-form-item>

            <a-form-item :label="t('settings.email_smtp_host')">
              <a-input v-model:value="settingForm.data.email.smtp_host" />
            </a-form-item>

            <a-form-item :label="t('settings.email_smtp_port')">
              <a-input-number v-model:value="settingForm.data.email.smtp_port" />
            </a-form-item>

            <a-form-item :label="t('settings.email_smtp_ssl')">
              <a-switch v-model:checked="settingForm.data.email.smtp_ssl" />
            </a-form-item>
          </a-form>
        </a-card>

        <a-card v-if="selectedKeys == 'shortcut'" :title="t('settings.shortcut_settings')" :loading="loading">
          <ShortcutSettings v-model="settingForm.data.shortcuts" />
        </a-card>

        <a-card v-show="selectedKeys == 'other'" :title="t('settings.other')" :loading="loading">
          <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
            <a-form-item :label="t('settings.website_domain')">
              <a-select v-model:value="settingForm.data.website_domain" :options="websiteDomainOptions"
                style="width: 100%;" />
            </a-form-item>

            <a-form-item :label="t('settings.pexels_api_key')">
              <a-input-password v-model:value="settingForm.data.pexels_api_key" />
            </a-form-item>

            <a-form-item :label="t('settings.stable_diffusion_base_url')">
              <a-input v-model:value="settingForm.data.stable_diffusion_base_url" />
            </a-form-item>

            <a-form-item :label="t('settings.stability_key')">
              <a-input-password v-model:value="settingForm.data.stability_key" />
            </a-form-item>

            <a-form-item :label="t('settings.use_system_proxy')">
              <a-checkbox v-model:checked="settingForm.data.use_system_proxy" />
            </a-form-item>

            <a-form-item :label="t('settings.skip_ssl_verification')">
              <a-checkbox v-model:checked="settingForm.data.skip_ssl_verification" />
            </a-form-item>

            <a-form-item :label="t('settings.output_folder')">
              <a-flex vertical gap="small">
                <a-typography-text>
                  {{ settingForm.data.output_folder }}
                </a-typography-text>
                <a-button @click="selectFolder('output_folder')">
                  {{ t('settings.select_folder') }}
                </a-button>
              </a-flex>
            </a-form-item>

            <a-form-item :label="t('settings.log_path')">
              <a-flex vertical gap="small">
                <a-typography-text>
                  {{ settingForm.data.log_path }}
                </a-typography-text>
                <a-button @click="selectFolder('log_path')">
                  {{ t('settings.select_folder') }}
                </a-button>
              </a-flex>
            </a-form-item>

            <a-form-item :label="t('settings.data_path')">
              <a-flex vertical gap="small">
                <a-typography-text>
                  {{ settingForm.data.data_path }}
                </a-typography-text>
                <a-button @click="selectFolder('data_path')">
                  {{ t('settings.select_folder') }}
                </a-button>
              </a-flex>
            </a-form-item>
          </a-form>
        </a-card>

        <a-card v-show="selectedKeys == 'agent'" :title="t('settings.agent_settings')" :loading="loading">
          <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
            <a-form-item :label="t('settings.agent_auto_title')">
              <a-checkbox v-model:checked="settingForm.data.agent.auto_title" />
            </a-form-item>
            <a-form-item v-show="settingForm.data.agent.auto_title" :label="t('settings.agent_auto_title_model')">
              <a-cascader style="width: 100%;" v-model:value="settingForm.data.agent.auto_title_model"
                :options="chatModelOptions" />
            </a-form-item>
            <a-form-item>
              <template #label>
                {{ t('settings.agent_screenshot_monitor_device') }}
                <QuestionPopover :contents="[t('settings.agent_screenshot_monitor_device_question_popover')]" />
              </template>
              <a-input-number v-model:value="settingForm.data.agent.screenshot_monitor_device" />
            </a-form-item>
            <a-form-item :label="t('settings.agent_tool_call_data_generate_model')">
              <a-cascader style="width: 100%;" v-model:value="settingForm.data.agent.tool_call_data_generate_model"
                :options="chatModelOptions" />
            </a-form-item>
          </a-form>
        </a-card>
      </a-layout-content>
    </a-layout>
  </div>
</template>

<style scoped>
.main-container {
  background-color: var(--gray-background);
  padding-top: 64px;
  display: flex;
  justify-content: center;
  min-height: calc(100vh - 64px);
}

.main-layout {
  padding: 0 40px 60px;
  max-width: 72rem;
  gap: 0.75rem;
  background-color: var(--gray-background);
}

.sider-menu {
  background: var(--component-background);
  overflow-x: hidden;
  border: var(--light-border);
  border-radius: 10px;
}

.sider-menu .collapse-button {
  position: absolute;
  bottom: 0;
}
.settings-toolbar {
  position: sticky;
  top: 64px;
  z-index: 5;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 16px;
  padding: 12px 0;
  background: var(--gray-background);
}
</style>
