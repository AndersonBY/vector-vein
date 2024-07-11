<script setup>
import { useI18n } from 'vue-i18n'
import SelectOptionsEditor from '@/components/SelectOptionsEditor.vue'

const { t } = useI18n()

const ttsSettings = defineModel()
</script>

<template>
  <a-tabs tab-position="left">
    <a-tab-pane key="piper" tab="piper">
      <a-flex vertical justify="center" gap="middle">
        <a-alert message="piper-tts deployment" type="info">
          <template #description>
            <a-typography-link style="text-align: center;" target="_blank"
              href="https://github.com/rhasspy/piper/blob/master/src/python_run/README_http.md">
              https://github.com/rhasspy/piper/blob/master/src/python_run/README_http.md
            </a-typography-link>
          </template>
        </a-alert>
        <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
          <a-form-item label="API Base">
            <a-input v-model:value="ttsSettings.piper.api_base" />
          </a-form-item>
        </a-form>
      </a-flex>
    </a-tab-pane>

    <a-tab-pane key="reecho" tab="Reecho.ai">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <a-form-item label="API Key">
          <a-input-password v-model:value="ttsSettings.reecho.api_key" />
        </a-form-item>
        <a-form-item :label="t('settings.voices')">
          <SelectOptionsEditor v-model="ttsSettings.reecho.voices" :labelName="t('settings.voice_label')"
            :valueName="t('settings.voice_id')" labelKey="voice_label" valueKey="voice_id" />
        </a-form-item>
      </a-form>
    </a-tab-pane>

    <a-tab-pane key="azure" tab="Azure">
      <a-flex vertical justify="center" gap="middle">
        <a-alert message="Azure Text-to-Speech" type="info">
          <template #description>
            <a-typography-link style="text-align: center;" target="_blank"
              href="https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/text-to-speech">
              https://docs.microsoft.com/en-us/azure/cognitive-services/speech-service/text-to-speech
            </a-typography-link>
          </template>
        </a-alert>
        <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
          <a-form-item label="API Key">
            <a-input-password v-model:value="ttsSettings.azure.api_key" />
          </a-form-item>
          <a-form-item label="Service Region">
            <a-input v-model:value="ttsSettings.azure.service_region" />
          </a-form-item>
          <a-form-item :label="t('settings.voices')">
            <SelectOptionsEditor v-model="ttsSettings.azure.voices" :labelName="t('settings.voice_label')"
              :valueName="t('settings.voice_id')" labelKey="voice_label" valueKey="voice_id" />
          </a-form-item>
        </a-form>
      </a-flex>
    </a-tab-pane>
  </a-tabs>
</template>