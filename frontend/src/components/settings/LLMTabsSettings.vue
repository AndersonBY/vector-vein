<script setup>
import { useI18n } from 'vue-i18n'
import { ref } from 'vue'
import LLMStandardSettings from "@/components/settings/LLMStandardSettings.vue"

const props = defineProps({
  endpoints: {
    type: Array,
    required: true
  },
})

const backends = defineModel()
const activeBackend = ref('deepseek')

const { t } = useI18n()
</script>

<template>
  <a-tabs tab-position="left" v-model:activeKey="activeBackend">
    <a-tab-pane key="deepseek" tab="DeepSeek">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.deepseek" :endpoints="endpoints" backend="deepseek" :active="activeBackend === 'deepseek'" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="openai" tab="OpenAI">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.openai" :endpoints="endpoints" backend="openai" :active="activeBackend === 'openai'" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="anthropic" tab="Anthropic">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.anthropic" :endpoints="endpoints" backend="anthropic" :active="activeBackend === 'anthropic'" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="qwen" :tab="t('settings.qwen')">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.qwen" :endpoints="endpoints" backend="qwen" :active="activeBackend === 'qwen'" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="gemini" tab="Gemini">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.gemini" :endpoints="endpoints" backend="gemini" :active="activeBackend === 'gemini'" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="moonshot" :tab="t('settings.moonshot')">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.moonshot" :endpoints="endpoints" backend="moonshot" :active="activeBackend === 'moonshot'" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="zhipuai" :tab="t('settings.zhipuai')">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.zhipuai" :endpoints="endpoints" backend="zhipuai" :active="activeBackend === 'zhipuai'" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="minimax" tab="MiniMax">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.minimax" :endpoints="endpoints" backend="minimax" :active="activeBackend === 'minimax'" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="mistral" tab="Mistral">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.mistral" :endpoints="endpoints" backend="mistral" :active="activeBackend === 'mistral'" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="lingyiwanwu" :tab="t('settings.lingyiwanwu')">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.yi" :endpoints="endpoints" backend="yi" :active="activeBackend === 'lingyiwanwu'" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="baichuan" :tab="t('settings.baichuan')">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.baichuan" :endpoints="endpoints" backend="baichuan" :active="activeBackend === 'baichuan'" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="groq" tab="Groq">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.groq" :endpoints="endpoints" backend="groq" :active="activeBackend === 'groq'" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="ernie" tab="Ernie">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.ernie" :endpoints="endpoints" backend="ernie" :active="activeBackend === 'ernie'" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="stepfun" tab="StepFun">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.stepfun" :endpoints="endpoints" backend="stepfun" :active="activeBackend === 'stepfun'" />
      </a-form>
    </a-tab-pane>
    <a-tab-pane key="xai" tab="xAI">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <LLMStandardSettings v-model="backends.xai" :endpoints="endpoints" backend="xai" :active="activeBackend === 'xai'" />
      </a-form>
    </a-tab-pane>
  </a-tabs>
</template>
