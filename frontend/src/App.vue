<template>
  <a-config-provider :locale="locale" :theme="theme">
    <a-spin :spinning="loading">
      <router-view />
    </a-spin>
  </a-config-provider>
</template>

<script setup>
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import enUS from 'ant-design-vue/es/locale/en_US'
import { ref, computed, onBeforeMount } from 'vue'
import { useUserSettingsStore } from '@/stores/userSettings'

const loading = ref(true)
onBeforeMount(async () => {
  // Only wait when in production mode
  if (import.meta.env.PROD) {    
    while (!window.pywebview) {
      await new Promise((resolve) => setTimeout(resolve, 100))
    }
  }
  loading.value = false
})

const userSettings = useUserSettingsStore()

const antDesignLocale = computed(() => {
  const languageMap = {
    'zh-CN': zhCN,
    'en-US': enUS,
  }
  return languageMap[userSettings.language]
})

const locale = antDesignLocale
const theme = {
  token: {
    colorPrimary: '#28c5e5',
    colorLink: '#28c5e5',
  }
}
</script>

<style>
#app .shadow-card {
  box-shadow: 0 2px 10px 0 rgb(0 0 0 / 8%);
  border-radius: 12px;
}

.text-primary {
  color: #28c5e5;
}

.shadow-card {
  box-shadow: 0 2px 10px 0 rgba(0, 0, 0, 0.08);
  border-radius: 12px;
}

.shadow-card .ant-card-head {
  border-bottom: none;
  padding: 0 24px;
}

.shadow-card .ant-card-head+.ant-card-body {
  padding-top: 5px;
}

.ant-modal-header .ant-modal-title {
  font-weight: 600;
  font-size: 18px;
}

#app .ant-statistic-content-value {
  font-weight: 700;
}

#app .ant-btn,
.ant-input,
.ant-input-password,
.ant-input-number,
.ant-select-selector,
.ant-select:not(.ant-select-customize-input),
.ant-select-selector {
  border-radius: 4px;
}

.ant-popover-inner-content p:last-child {
  margin-bottom: 0px;
}

.markdown {
  line-height: 2;
  font-size: 1.015rem;
}

.custom-scrollbar::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.custom-scrollbar::-webkit-scrollbar-thumb {
  background: #CCCCCC;
  border-radius: 6px;
}

.custom-scrollbar::-webkit-scrollbar-track {
  background: transparent;
}

.custom-hljs pre code.hljs {
  display: block;
  overflow-x: auto;
  padding: 1em;
}

.custom-hljs code.hljs {
  padding: 3px 5px;
}

.custom-hljs .hljs {
  background: #23241f;
  color: #f8f8f2;
}

.markdown-body .highlight pre,
.markdown-body pre {
  padding: 0 !important;
}

body {
  margin: 0;
}
</style>