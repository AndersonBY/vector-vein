<script setup>
import { defineComponent, onBeforeMount, computed, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import { useUserSettingsStore } from "@/stores/userSettings"
import { getRandomBackgroundImg } from '@/utils/util'
import { currentTourVersion } from '@/utils/common'
import { getWorkflows } from "@/utils/workflow"
import { settingAPI } from "@/api/user"
import BasicHeader from '@/components/layouts/BasicHeader.vue'

defineComponent({
  name: 'WorkspaceLayout',
})

const { t } = useI18n()
const userWorkflowsStore = useUserWorkflowsStore()
const userSettingsStore = useUserSettingsStore()
const { setting } = storeToRefs(userSettingsStore)
const openTour = ref(false)

onBeforeMount(async () => {
  const [workflowsResponse, settingsResponse] = await Promise.all([getWorkflows(userWorkflowsStore, true), settingAPI('get', {})])
  userSettingsStore.setSetting(settingsResponse.data)
  if (typeof setting.value.data.tour_version === "undefined" ? 0 : setting.value.data.tour_version < currentTourVersion) {
    setting.value.data.tour_version = currentTourVersion
    userSettingsStore.setSetting(setting.value)
    await settingAPI('update', setting.value)
    setTimeout(() => {
      openTour.value = true
    }, 1000)
  }
})

const backgroundImgUrl = computed(() => getRandomBackgroundImg())

const tourCurrentStep = ref(0)
const tourSteps = [{
  title: t('layouts.workspaceLayout.tour.workflow_button_title'),
  description: t('layouts.workspaceLayout.tour.workflow_button_description'),
  target: () => document.getElementById('header-workflow-button'),
}, {
  title: t('layouts.workspaceLayout.tour.database_button_title'),
  description: t('layouts.workspaceLayout.tour.database_button_description'),
  target: () => document.getElementById('header-data-button'),
}]
const onTourClose = () => {
  userSettingsStore.setTourVersion(currentTourVersion)
  openTour.value = false
}
</script>
<template>
  <a-layout style="min-height: 100vh">
    <BasicHeader />
    <a-layout-content class="layout-content-container" :style="{ marginTop: '64px' }">
      <router-view class="content-view-container"></router-view>
      <img class="layout-background-img" :src="backgroundImgUrl" />
    </a-layout-content>

    <a-tour v-model:current="tourCurrentStep" :open="openTour" :steps="tourSteps" @close="onTourClose" />
  </a-layout>
</template>
<style>
.logo {
  float: left;
}

.logo img {
  height: 30px;
}

.layout-content-container {
  z-index: 0;
}

.layout-content-container .content-view-container {
  z-index: 1;
  position: relative;
}

.layout-content-container .layout-background-img {
  position: absolute;
  z-index: 0;
  width: 50%;
  height: 50%;
  bottom: 150px;
  right: 0;
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