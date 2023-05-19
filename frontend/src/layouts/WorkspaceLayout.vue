<script setup>
import { defineComponent, onBeforeMount, onMounted, ref, computed } from 'vue'
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import { getRandomBasicLayoutBackgroundImg } from '@/utils/util'
import { getWorkflows } from "@/utils/workflow"
import BasicHeader from '@/components/layouts/BasicHeader.vue'

defineComponent({
  name: 'WorkspaceLayout',
})

const userWorkflowsStore = useUserWorkflowsStore()
const headerClass = ref(['scroll-top', 'basic-header'])

onBeforeMount(async () => {
  await getWorkflows(userWorkflowsStore, true)
})

onMounted(() => {
  window.addEventListener('scroll', scrollChange, true)
})

const scrollChange = () => {
  let scrollTop = document.documentElement.scrollTop || document.body.scrollTop
  if (scrollTop == 0) {
    headerClass.value = ['scroll-top', 'basic-header']
  } else {
    headerClass.value = ['scroll-down', 'basic-header']
  }
}

const backgroundImgUrl = computed(() => getRandomBasicLayoutBackgroundImg())
</script>
<template>
  <a-layout style="min-height: 100vh">
    <BasicHeader />
    <a-layout-content class="basic-layout-content-container" :style="{ marginTop: '64px' }">
      <router-view class="content-view-container"></router-view>
      <img class="basic-layout-background-img" :src="backgroundImgUrl" />
    </a-layout-content>
  </a-layout>
</template>
<style>
.basic-header {
  position: fixed;
  z-index: 1;
  width: 100%;
}

.basic-header .ant-menu {
  background: transparent;
}

.logo {
  float: left;
}

.logo img {
  height: 30px;
}

.basic-layout-content-container {
  z-index: 0;
}

.basic-layout-content-container .content-view-container {
  z-index: 1;
  position: relative;
}

.basic-layout-content-container .basic-layout-background-img {
  position: absolute;
  z-index: 0;
  width: 50%;
  height: 50%;
  bottom: 150px;
  right: 0;
}


.scroll-top {
  background: transparent;
}

.scroll-down {
  background: #fff;
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