<script setup>
import { computed, onBeforeMount, h } from 'vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import enUS from 'ant-design-vue/es/locale/en_US'
import { theme, Spin } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from "vue-router"
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import { initTheme } from '@/utils/theme'
import LoadingElement from "@/components/LoadingElement.vue"

const { locale } = useI18n({ useScope: "global" })
const router = useRouter()

const userSettings = useUserSettingsStore()
const { theme: userTheme } = storeToRefs(userSettings)

onBeforeMount(async () => {
  // Only wait when in production mode
  if (import.meta.env.PROD) {
    while (!window.pywebview) {
      await new Promise((resolve) => setTimeout(resolve, 100))
    }
  }
  await userSettings.init()
  locale.value = userSettings.language
  initTheme(userSettings.theme)

  // Expose router to window for python usage
  window.router = router
})

const antDesignLocale = computed(() => {
  const languageMap = {
    'zh-CN': zhCN,
    'en-US': enUS,
  }
  return languageMap[userSettings.language]
})

const themeMap = {
  default: theme.defaultAlgorithm,
  dark: theme.darkAlgorithm,
  compact: theme.compactAlgorithm,
}

const customTheme = computed(() => {
  return {
    token: {
      colorPrimary: '#28c5e5',
      colorLink: '#28c5e5',
      colorTextBase: userTheme.value == 'default' ? '#1d1d1f' : '#fff',
      borderRadius: 8,
    },
    algorithm: themeMap[userTheme.value],
  }
})

Spin.setDefaultIndicator({
  indicator: h(LoadingElement),
})
</script>

<template>
  <a-config-provider :locale="antDesignLocale" :theme="customTheme">
    <router-view :class="`theme-${userTheme}`" />
  </a-config-provider>
</template>

<style>
:root .theme-default {
  --color-primary: #28c5e5;
  --component-background: #fff;
  --gray-background: #f5f5f5;
  --border-color: 1px solid #33333322;
  --light-border: 1px solid #f0f0f0;
  --site-text-color: rgba(0, 0, 0, 0.88);
  --site-secondary-text-color: rgba(0, 0, 0, 0.45);
  --site-light-text-color: #6d6d6d;
  --card-background: #fff;
  --card-box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  --card-hover-box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  --more-hover-background: #f5f5f5;
  --conversation-list-background: #d5eef9;
  --conversation-hover-background-image: linear-gradient(to left, rgb(200 224 234) 60%, rgba(0, 0, 0, 0));
  --chat-button-selected-background-color: rgba(0, 0, 0, 0.06);
  --chat-box-shadow: 50px 50px 100px 10px rgba(0, 0, 0, .1);
}

:root .theme-dark {
  --color-primary: #28c5e5;
  --component-background: #141414;
  --gray-background: #1a1a1a;
  --border-color: 1px solid #ffffff22;
  --light-border: 1px solid #1a1a1a;
  --site-text-color: rgba(255, 255, 255, 0.85);
  --site-secondary-text-color: rgba(255, 255, 255, 0.61);
  --site-light-text-color: #c7c7c7;
  --card-background: #141414;
  --card-box-shadow: 0 2px 8px rgba(128, 127, 127, 0.274);
  --card-hover-box-shadow: 0 4px 12px rgba(128, 127, 127, 0.274);
  --more-hover-background: #252525;
  --conversation-list-background: #002130;
  --conversation-hover-background-image: linear-gradient(to left, rgb(0 33 48) 60%, rgba(0, 0, 0, 0));
  --chat-button-selected-background-color: rgba(255, 255, 255, 0.06);
  --chat-box-shadow: 50px 50px 100px 10px rgba(128, 127, 127, 0.274);
}

.theme-dark .ant-menu.ant-menu-dark,
.theme-dark .ant-layout .ant-layout-sider {
  background-color: var(--component-background);
}

.ant-tour.ant-tour-primary .ant-tour-inner {
  background-color: #007de4;
}

.ant-tour.ant-tour-primary .ant-tour-arrow::before {
  background: #007de4;
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

textarea::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

textarea::-webkit-scrollbar-thumb {
  background: #CCCCCC;
  border-radius: 6px;
}

textarea::-webkit-scrollbar-track {
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

.markdown {
  line-height: 2;
  font-size: 1.015rem;
}

.markdown-body {
  user-select: text;
}

.markdown-body .code-block .header {
  background-color: #343541;
  display: flex;
  justify-content: space-between;
  color: #d9d9e3;
  padding: 8px 16px;
}

.markdown-body .code-block .header .copy-container .ant-typography {
  margin-bottom: 0;
}

.markdown-body .code-block code {
  border-radius: 0;
}

.markdown-body .code-block .ant-typography-copy {
  color: #fff;
}

:deep(.slick-dots) {
  position: relative;
  height: auto;
}

:deep(.slick-slide img) {
  border: 5px solid #fff;
  display: block;
  margin: auto;
  max-width: 80%;
  max-height: 60vh;
}

:deep(.slick-arrow) {
  display: none !important;
}

:deep(.slick-thumb) {
  bottom: 0px;
}

:deep(.slick-thumb li) {
  width: 60px;
  height: 45px;
}

:deep(.slick-thumb li img) {
  width: 100%;
  height: 100%;
  filter: grayscale(100%);
  display: block;
}

:deep .slick-thumb li.slick-active img {
  filter: grayscale(0%);
}

body {
  margin: 0;
}

.no-header-bottom-line.ant-card>.ant-card-head {
  border-bottom: none;
}

.no-header-bottom-line.ant-card>.ant-card-body {
  padding-top: 0;
}

.ant-btn>.i-icon+span,
.ant-btn>span+.i-icon {
  margin-inline-start: 8px;
}

html::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

html::-webkit-scrollbar-thumb {
  background: #CCCCCC;
  border-radius: 6px;
}

html::-webkit-scrollbar-track {
  background: transparent;
}
</style>