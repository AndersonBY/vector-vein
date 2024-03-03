<script setup>
import { ref, nextTick, watch } from "vue"
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useRoute, useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import { useUserSettingsStore } from '@/stores/userSettings'
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import { Home, User } from '@icon-park/vue-next'
import { workflowAPI } from "@/api/workflow"

const { t } = useI18n()
const loading = ref(false)
const userSettingsStore = useUserSettingsStore()
const { language } = storeToRefs(userSettingsStore)
const userWorkflowsStore = useUserWorkflowsStore()
const { userFastAccessWorkflows } = storeToRefs(userWorkflowsStore)
const route = useRoute()
const router = useRouter()
const workflowId = ref(route.params.workflowId)
watch(route, (route) => {
  workflowId.value = route.params.workflowId
  selectedKeys.value = [route.params.workflowId]
})

const selectedKeys = ref([workflowId.value])
const openKeys = ref(['user-workflows'])

const newWorkflowIndex = ref(1)
const newWorkflowModal = ref()
const openNewWorkflowModal = () => {
  newWorkflowModal.value.showModal()
}
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
  workflow.update_time = new Date(workflow.update_time).toLocaleString()
  workflow.create_time = new Date(workflow.create_time).toLocaleString()
  userWorkflowsStore.addUserWorkflow(workflow)

  nextTick(() => {
    selectedKeys.value = [workflow.wid]
    router.push(`/workflow/editor/${workflow.wid}`)
  })
}
</script>

<template>
  <div class="space-container">
    <a-layout class="layout">
      <a-layout-sider width="200" style="background: #fff" breakpoint="lg" collapsed-width="0">
        <a-skeleton active v-if="loading" />
        <a-menu v-model:selectedKeys="selectedKeys" v-model:openKeys="openKeys" mode="inline" style="height: 100%"
          v-else>
          <a-menu-item key="my_index">
            <router-link to="/workflow/">
              <Home />
              {{ t('workspace.workflowSpace.workflow_index') }}
            </router-link>
          </a-menu-item>
          <a-sub-menu key="user-workflows">
            <template #title>
              <span>
                <User />
                {{ t('workspace.workflowSpace.user_fast_access_workflows') }}
              </span>
            </template>
            <a-menu-item :key="workflow.wid" v-for="workflow in userFastAccessWorkflows">
              <a-tooltip placement="topLeft" :title="workflow.title">
                <router-link :to="`/workflow/${workflow.wid}`">
                  {{ workflow.title }}
                </router-link>
              </a-tooltip>
            </a-menu-item>

            <a-menu-item key="add" @click="add">
              + {{ t('workspace.workflowSpace.add_new_workflow') }}
            </a-menu-item>
            <!-- <NewWorkflowModal ref="newWorkflowModal" @create="add" /> -->
          </a-sub-menu>
        </a-menu>
      </a-layout-sider>
      <a-layout-content :style="{ padding: '0 24px', minHeight: '280px' }">
        <a-skeleton active v-if="loading" />
        <router-view :key="workflowId" v-else></router-view>
      </a-layout-content>
    </a-layout>
  </div>
</template>

<style scoped>
.space-container {
  height: calc(100vh - 64px);
}

.space-container .layout {
  height: 100%;
  padding: 24px 0;
  background: #fff;
}
</style>