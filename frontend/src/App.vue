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
.text-primary {
  color: #28c5e5;
}

.vue-flow .add-field-button {
  display: flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
}

.ant-drawer-body::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.ant-drawer-body::-webkit-scrollbar-thumb {
  background: #CCCCCC;
  border-radius: 6px;
}

.ant-drawer-body::-webkit-scrollbar-track {
  background: transparent;
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