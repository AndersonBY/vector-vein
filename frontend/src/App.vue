<script setup>
import { computed, onBeforeMount, h } from 'vue'
import zhCN from 'ant-design-vue/es/locale/zh_CN'
import enUS from 'ant-design-vue/es/locale/en_US'
import { theme, Spin } from 'ant-design-vue'
import { useUserSettingsStore } from '@/stores/userSettings'
import LoadingElement from "@/components/LoadingElement.vue"

onBeforeMount(async () => {
  // Only wait when in production mode
  if (import.meta.env.PROD) {
    while (!window.pywebview) {
      await new Promise((resolve) => setTimeout(resolve, 100))
    }
  }
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
const customTheme = {
  token: {
    colorPrimary: '#28c5e5',
    colorLink: '#28c5e5',
    colorTextBase: '#1d1d1f',
    borderRadius: 8,
  },
  algorithm: theme.defaultAlgorithm,
}

Spin.setDefaultIndicator({
  indicator: h(LoadingElement),
})
</script>

<template>
  <a-config-provider :locale="locale" :theme="customTheme">
    <router-view />
  </a-config-provider>
</template>

<style>
.primary-color-text {
  color: #179ebf !important;
}

.primary-color-active-text {
  color: #28c5e5 !important;
}

.dark-color-text {
  color: #6d6d6d !important;
}

.primary-black {
  color: #333;
}

.vue-flow .add-field-button {
  display: flex;
  gap: 6px;
  align-items: center;
  justify-content: center;
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

.ant-typography.black-text {
  color: #303030;
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