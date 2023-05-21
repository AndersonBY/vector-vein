<script setup>
import { defineComponent, onBeforeMount, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import { useUserSettingsStore } from "@/stores/userSettings"
import { getRandomBackgroundImg } from '@/utils/util'
import { currentTourVersion } from '@/utils/common'
import { getWorkflows } from "@/utils/workflow"
import BasicHeader from '@/components/layouts/BasicHeader.vue'

defineComponent({
  name: 'WorkspaceLayout',
})

const userWorkflowsStore = useUserWorkflowsStore()
const userSettingsStore = useUserSettingsStore()
const { tourVersion } = storeToRefs(userSettingsStore)

onBeforeMount(async () => {
  console.log(tourVersion.value < currentTourVersion)
  await getWorkflows(userWorkflowsStore, true)
})

const backgroundImgUrl = computed(() => getRandomBackgroundImg())
</script>
<template>
  <a-layout style="min-height: 100vh">
    <BasicHeader />
    <a-layout-content class="layout-content-container" :style="{ marginTop: '64px' }">
      <router-view class="content-view-container"></router-view>
      <img class="layout-background-img" :src="backgroundImgUrl" />
    </a-layout-content>
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