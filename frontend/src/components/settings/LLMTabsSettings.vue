<script setup>
import { useI18n } from 'vue-i18n'
import LLMStandardSettings from "@/components/settings/LLMStandardSettings.vue"

const props = defineProps({
  endpoints: {
    type: Array,
    required: true
  },
})

const backends = defineModel()

const { t } = useI18n()
</script>

<template>
  <a-tabs tab-position="left">
    <a-tab-pane key="deepseek" tab="DeepSeek">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.deepseek" :endpoints="endpoints" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="openai" tab="OpenAI">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.openai" :endpoints="endpoints" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="anthropic" tab="Anthropic">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.anthropic" :endpoints="endpoints" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="qwen" :tab="t('settings.qwen')">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.qwen" :endpoints="endpoints" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="gemini" tab="Gemini">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.gemini" :endpoints="endpoints" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="moonshot" :tab="t('settings.moonshot')">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.moonshot" :endpoints="endpoints" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="zhipuai" :tab="t('settings.zhipuai')">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.zhipuai" :endpoints="endpoints" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="minimax" tab="MiniMax">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.minimax" :endpoints="endpoints" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="mistral" tab="Mistral">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.mistral" :endpoints="endpoints" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="lingyiwanwu" :tab="t('settings.lingyiwanwu')">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.yi" :endpoints="endpoints" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="baichuan" :tab="t('settings.baichuan')">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.baichuan" :endpoints="endpoints" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="ernie" tab="Groq">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.groq" :endpoints="endpoints" />
      </a-form>
    </a-tab-pane>
  </a-tabs>
</template>