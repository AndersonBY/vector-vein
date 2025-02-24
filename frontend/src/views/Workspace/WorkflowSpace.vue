<script setup>
import { ref, nextTick, watch, onBeforeMount, computed } from "vue"
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import { Home, Star, More, Delete, ExpandLeft, ExpandRight } from '@icon-park/vue-next'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import { formatTime } from '@/utils/util'
import { workflowAPI } from "@/api/workflow"

const { t } = useI18n()
const loading = ref(false)
const userSettingsStore = useUserSettingsStore()
const { language, theme } = storeToRefs(userSettingsStore)
const userWorkflowsStore = useUserWorkflowsStore()
const { userFastAccessWorkflows } = storeToRefs(userWorkflowsStore)
const route = useRoute()
const router = useRouter()
const workflowId = ref(route.params.workflowId)
const selectedKeys = ref([workflowId.value])
const openKeys = ref(['user-workflows'])
const collapsed = ref(false)

const setSelectedKeys = (route) => {
  if (route.name == 'WorkflowSpaceMain') {
    selectedKeys.value = ['my_index']
  } else if (route.name == 'WorkflowUse') {
    workflowId.value = route.params.workflowId
    selectedKeys.value = [route.params.workflowId]
  }
}

onBeforeMount(async () => {
  setSelectedKeys(route)
  await userWorkflowsStore.refreshWorkflows()
})

watch(route, (route) => {
  setSelectedKeys(route)
})

const newWorkflowIndex = ref(1)

const add = async (template) => {
  const response = await workflowAPI('create', {
    title: t('workspace.workflowSpace.new_workflow') + newWorkflowIndex.value,
    language: language.value,
  })
  if (response.status != 200) {
    message.error(response.msg)
    return
  }
  const workflow = response.data
  workflow.update_time = formatTime(workflow.update_time)
  workflow.create_time = formatTime(workflow.create_time)
  userWorkflowsStore.addUserWorkflow(workflow)

  nextTick(async () => {
    selectedKeys.value = [workflow.wid]
    await router.push({ name: 'WorkflowEditor', params: { workflowId: workflow.wid } })
  })
}

const deleteWorkflowFromFastAccess = async (wid) => {
  const response = await workflowAPI('delete_from_fast_access', { wid: wid })
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.delete_from_fast_access_success'))
    await userWorkflowsStore.refreshWorkflows()
  } else {
    message.error(t('workspace.workflowSpace.delete_from_fast_access_failed'))
  }
}

const componentTheme = computed(() => theme.value == 'default' ? 'light' : 'dark')
</script>

<template>
  <div class="space-container">
    <a-layout class="layout">
      <a-layout-sider width="200" v-model:collapsed="collapsed" :style="{ padding: collapsed ? '0' : '8px' }"
        breakpoint="lg" collapsed-width="0" :zeroWidthTriggerStyle="{ background: 'unset', top: 0 }"
        :theme="componentTheme">
        <template #trigger>
          <a-button type="text" @click="collapsed = !collapsed">
            <template #icon>
              <ExpandLeft v-if="collapsed" />
              <ExpandRight v-else />
            </template>
          </a-button>
        </template>
        <a-skeleton v-if="loading" active />
        <a-menu v-else v-model:selectedKeys="selectedKeys" v-model:openKeys="openKeys" mode="inline"
          :theme="componentTheme" style="height: 100%">
          <a-menu-item key="my_index" id="my_index">
            <router-link :to="{ name: 'WorkflowSpaceMain' }">
              <Home theme="filled" />
              {{ t('workspace.workflowSpace.workflow_index') }}
            </router-link>
          </a-menu-item>
          <a-sub-menu key="user-workflows">
            <template #title>
              <span>
                <Star theme="filled" />
                {{ t('workspace.workflowSpace.user_fast_access_workflows') }}
              </span>
            </template>
            <a-menu-item :key="workflow.wid" v-for="workflow in userFastAccessWorkflows">
              <div class="starred-workflow-item">
                <a-tooltip placement="topLeft" :title="workflow.title">
                  <router-link :to="{ name: 'WorkflowUse', params: { workflowId: workflow.wid } }"
                    style="overflow: hidden;">
                    {{ workflow.title }}
                  </router-link>
                </a-tooltip>
                <a-dropdown>
                  <div class="starred-workflow-item-more-container">
                    <div class="single-chat-button-more">
                      <More />
                    </div>
                  </div>
                  <template #overlay>
                    <a-menu>
                      <a-menu-item key="delete" @click=deleteWorkflowFromFastAccess(workflow.wid)>
                        <a-typography-text type="danger">
                          <Delete />
                          {{ t('workspace.workflowSpace.delete_from_fast_access') }}
                        </a-typography-text>
                      </a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
              </div>
            </a-menu-item>

            <a-menu-item key="add" @click="add">
              + {{ t('workspace.workflowSpace.add_new_workflow') }}
            </a-menu-item>
          </a-sub-menu>
        </a-menu>
      </a-layout-sider>
      <a-layout-content class="layout-content-container">
        <router-view :key="workflowId"></router-view>
      </a-layout-content>
    </a-layout>
  </div>
</template>

<style scoped>
.space-container {
  height: 100%;
  flex: 1;
}

.space-container .layout {
  padding: 24px 0;
  background: var(--component-background);
}

.space-container .starred-workflow-item {
  display: flex;
  justify-content: space-between;
}

.space-container .starred-workflow-item .starred-workflow-item-more-container {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 3.5rem;
  padding: 0 5px;
  z-index: 5;
  opacity: 0;
  background-image: linear-gradient(to left, #e9e9e9 60%, rgba(0, 0, 0, 0));
  visibility: hidden;
  transition: opacity 0.3s ease-in-out, visibility 0.3s ease-in-out;
  display: flex;
  justify-content: flex-end;
}

.space-container .starred-workflow-item:hover .starred-workflow-item-more-container {
  opacity: 1;
  visibility: visible;
}

.space-container .layout-content-container {
  padding: 0 24px;
  min-height: 280px;
}
</style>