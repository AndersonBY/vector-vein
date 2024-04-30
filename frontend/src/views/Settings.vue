<script setup>
import { ref, reactive, toRaw, onBeforeMount } from "vue"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { MenuFoldOne, MenuUnfoldOne, More, Robot, Mail } from '@icon-park/vue-next'
import { useUserSettingsStore } from '@/stores/userSettings'
import { settingAPI } from "@/api/user"

const { t } = useI18n()
const loading = ref(false)

const userSettings = useUserSettingsStore()

onBeforeMount(async () => {
  const res = await settingAPI('get', {})
  userSettings.setSetting(res.data)
  settingForm.id = res.data.id
  // LLMs settings
  settingForm.data.openai_api_type = res.data.data.openai_api_type || 'open_ai'
  settingForm.data.openai_api_key = res.data.data.openai_api_key || ''
  settingForm.data.openai_api_base = res.data.data.openai_api_base || 'https://api.openai.com/v1'
  settingForm.data.azure_api_key = res.data.data.azure_api_key || ''
  settingForm.data.azure_endpoint = res.data.data.azure_endpoint || ''
  settingForm.data.azure_gpt_35_deployment_id = res.data.data.azure_gpt_35_deployment_id || ''
  settingForm.data.azure_gpt_4_deployment_id = res.data.data.azure_gpt_4_deployment_id || ''
  settingForm.data.azure_gpt_4v_deployment_id = res.data.data.azure_gpt_4v_deployment_id || ''
  settingForm.data.openai_embedding_engine = res.data.data.openai_embedding_engine || ''
  settingForm.data.moonshot_api_base = res.data.data.moonshot_api_base || 'https://api.moonshot.cn/v1'
  settingForm.data.moonshot_api_key = res.data.data.moonshot_api_key || ''
  settingForm.data.zhipuai_api_base = res.data.data.zhipuai_api_base || 'https://open.bigmodel.cn/api/paas/v4/'
  settingForm.data.zhipuai_api_key = res.data.data.zhipuai_api_key || ''
  settingForm.data.anthropic_api_base = res.data.data.anthropic_api_base || 'https://api.anthropic.com/v1'
  settingForm.data.anthropic_api_key = res.data.data.anthropic_api_key || ''
  //
  settingForm.data.output_folder = res.data.data.output_folder || './'
  // Email settings
  settingForm.data.email_user = res.data.data.email_user || ''
  settingForm.data.email_password = res.data.data.email_password || ''
  settingForm.data.email_smtp_host = res.data.data.email_smtp_host || ''
  settingForm.data.email_smtp_port = res.data.data.email_smtp_port || ''
  settingForm.data.email_smtp_ssl = res.data.data.email_smtp_ssl || true
  settingForm.data.pexels_api_key = res.data.data.pexels_api_key || ''
  settingForm.data.stable_diffusion_base_url = res.data.data.stable_diffusion_base_url || 'http://127.0.0.1:7860'
  settingForm.data.use_system_proxy = res.data.data.use_system_proxy || true
  loading.value = false
})
const settingForm = reactive({
  id: 1,
  data: {
    openai_api_type: 'openai',
    openai_api_key: '',
    openai_api_base: 'https://api.openai.com/v1',
    azure_api_key: '',
    azure_endpoint: '',
    azure_gpt_35_deployment_id: '',
    azure_gpt_4_deployment_id: '',
    azure_gpt_4v_deployment_id: '',
    openai_embedding_engine: '',
    moonshot_api_base: 'https://api.moonshot.cn/v1',
    moonshot_api_key: '',
    zhipuai_api_base: 'https://open.bigmodel.cn/api/paas/v4/',
    zhipuai_api_key: '',
    anthropic_api_base: 'https://api.anthropic.com/v1',
    anthropic_api_key: '',
    output_folder: './',
    email_user: '',
    email_password: '',
    email_smtp_host: '',
    email_smtp_port: '',
    email_smtp_ssl: true,
    pexels_api_key: '',
    stable_diffusion_base_url: 'http://127.0.0.1:7860',
    use_system_proxy: true,
  }
})

const selectFolder = async () => {
  try {
    const selectedFolder = await window.pywebview.api.open_folder_dialog(
      settingForm.data.output_folder
    )
    if (!selectedFolder) {
      return
    }
    settingForm.data.output_folder = selectedFolder[0]
  } catch (error) {
    console.log(error)
  }
}

const saving = ref(false)
const saveSetting = async () => {
  saving.value = true
  await userSettings.setSetting(toRaw(settingForm))
  await settingAPI('update', settingForm)
  message.success(t('settings.save_success'))
  saving.value = false
}

const selectedKeys = ref(['llms'])
const collapsed = ref(false)
const sidebarHover = ref(false)
const onCollapse = (switchToCollapsed) => {
  collapsed.value = switchToCollapsed
}
const menuClick = async ({ key }) => {
  selectedKeys.value = [key]
}
</script>

<template>
  <a-layout class="main-container">
    <a-layout-sider class="sider-menu" :defaultCollapsed="collapsed" v-model:collapsed="collapsed" :trigger="null"
      collapsible :collapsedWidth="48" @collapse="onCollapse" breakpoint="lg" theme="light"
      :style="{ overflowY: sidebarHover ? 'auto' : 'hidden' }" @mouseover="sidebarHover = true"
      @mouseleave="sidebarHover = false">
      <a-menu v-model:selectedKeys="selectedKeys" @click="menuClick" theme="light" mode="inline" style="height: 100%">
        <a-menu-item key="llms">
          <template #icon>
            <Robot />
          </template>
          {{ t('settings.llms') }}
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
      <a-card v-show="selectedKeys == 'llms'" :title="t('settings.llms')" :loading="loading">
        <template #extra>
          <a-button type="primary" @click="saveSetting" :loading="saving">
            {{ t('settings.save') }}
          </a-button>
        </template>
        <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
          <a-form-item :label="t('settings.openai_api_type')">
            <a-radio-group v-model:value="settingForm.data.openai_api_type">
              <a-radio-button value="open_ai">
                {{ t('settings.openai') }}
              </a-radio-button>
              <a-radio-button value="azure">
                {{ t('settings.azure') }}
              </a-radio-button>
            </a-radio-group>
          </a-form-item>

          <template v-if="settingForm.data.openai_api_type == 'azure'">
            <a-form-item :label="t('settings.azure_api_key')">
              <a-input-password v-model:value="settingForm.data.azure_api_key" />
            </a-form-item>

            <a-form-item :label="t('settings.azure_endpoint')">
              <a-input v-model:value="settingForm.data.azure_endpoint" />
            </a-form-item>

            <a-form-item :label="t('settings.azure_gpt_35_deployment_id')">
              <a-input v-model:value="settingForm.data.azure_gpt_35_deployment_id" />
            </a-form-item>

            <a-form-item :label="t('settings.azure_gpt_4_deployment_id')">
              <a-input v-model:value="settingForm.data.azure_gpt_4_deployment_id" />
            </a-form-item>

            <a-form-item :label="t('settings.azure_gpt_4v_deployment_id')">
              <a-input v-model:value="settingForm.data.azure_gpt_4v_deployment_id" />
            </a-form-item>

            <a-form-item :label="t('settings.openai_embedding_engine')">
              <a-input v-model:value="settingForm.data.openai_embedding_engine" />
            </a-form-item>
          </template>
          <template v-else>
            <a-form-item :label="t('settings.openai_api_key')">
              <a-input-password v-model:value="settingForm.data.openai_api_key" />
            </a-form-item>
            <a-form-item :label="t('settings.openai_api_base')">
              <a-input v-model:value="settingForm.data.openai_api_base" />
            </a-form-item>
          </template>

          <a-divider />

          <a-form-item :label="t('settings.moonshot_api_base')">
            <a-input v-model:value="settingForm.data.moonshot_api_base" />
          </a-form-item>
          <a-form-item :label="t('settings.moonshot_api_key')">
            <a-input-password v-model:value="settingForm.data.moonshot_api_key" />
          </a-form-item>

          <a-divider />

          <a-form-item :label="t('settings.zhipuai_api_base')">
            <a-input v-model:value="settingForm.data.zhipuai_api_base" />
          </a-form-item>
          <a-form-item :label="t('settings.zhipuai_api_key')">
            <a-input-password v-model:value="settingForm.data.zhipuai_api_key" />
          </a-form-item>

          <a-divider />

          <a-form-item :label="t('settings.anthropic_api_base')">
            <a-input v-model:value="settingForm.data.anthropic_api_base" />
          </a-form-item>
          <a-form-item :label="t('settings.anthropic_api_key')">
            <a-input-password v-model:value="settingForm.data.anthropic_api_key" />
          </a-form-item>
        </a-form>
      </a-card>

      <a-card v-show="selectedKeys == 'email'" :title="t('settings.email_settings')" :loading="loading">
        <template #extra>
          <a-button type="primary" @click="saveSetting">
            {{ t('settings.save') }}
          </a-button>
        </template>
        <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
          <a-form-item :label="t('settings.email_user')">
            <a-input v-model:value="settingForm.data.email_user" />
          </a-form-item>

          <a-form-item :label="t('settings.email_password')">
            <a-input-password v-model:value="settingForm.data.email_password" />
          </a-form-item>

          <a-form-item :label="t('settings.email_smtp_host')">
            <a-input v-model:value="settingForm.data.email_smtp_host" />
          </a-form-item>

          <a-form-item :label="t('settings.email_smtp_port')">
            <a-input-number v-model:value="settingForm.data.email_smtp_port" />
          </a-form-item>

          <a-form-item :label="t('settings.email_smtp_ssl')">
            <a-switch v-model:checked="settingForm.data.email_smtp_ssl" />
          </a-form-item>
        </a-form>
      </a-card>

      <a-card v-show="selectedKeys == 'other'" :title="t('settings.other')" :loading="loading">
        <template #extra>
          <a-button type="primary" @click="saveSetting">
            {{ t('settings.save') }}
          </a-button>
        </template>
        <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
          <a-form-item :label="t('settings.pexels_api_key')">
            <a-input-password v-model:value="settingForm.data.pexels_api_key" />
          </a-form-item>

          <a-form-item :label="t('settings.stable_diffusion_base_url')">
            <a-input v-model:value="settingForm.data.stable_diffusion_base_url" />
          </a-form-item>

          <a-form-item :label="t('settings.output_folder')">
            <a-flex vertical gap="small">
              <a-typography-text>
                {{ settingForm.data.output_folder }}
              </a-typography-text>
              <a-button @click="selectFolder">
                {{ t('settings.select_folder') }}
              </a-button>
            </a-flex>
          </a-form-item>

          <a-form-item :label="t('settings.use_system_proxy')">
            <a-checkbox v-model:checked="settingForm.data.use_system_proxy" />
          </a-form-item>
        </a-form>
      </a-card>
    </a-layout-content>
  </a-layout>
</template>

<style scoped>
.main-container {
  padding: 0 40px 60px;
  margin: 0 auto;
  margin-top: 64px;
  max-width: 72rem;
  gap: 0.75rem;
}

.field-label {
  float: right;
}

.sider-menu {
  background: '#fff';
  overflow-x: 'hidden';
  padding-top: '64px';
  border: 1px solid #f0f0f0;
  border-radius: 10px;
}

.sider-menu .collapse-button {
  position: absolute;
  bottom: 0;
}
</style>