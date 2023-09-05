<script setup>
import { ref } from "vue"
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import { AppstoreAddOutlined, UserOutlined } from "@ant-design/icons-vue"
import { getFullUrl } from "@/utils/util"
import MyWorkflows from '@/components/workspace/MyWorkflows.vue'
import WorkflowTemplatesMarket from "@/components/workspace/WorkflowTemplatesMarket.vue"

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const activeKey = ref(route.query.tab ? route.query.tab : 'my-workflows')

const tabChange = async (key) => {
  await router.push(getFullUrl(route.path, { tab: key }))
}
</script>

<template>
  <a-tabs v-model:activeKey="activeKey" @change="tabChange">
    <a-tab-pane key="my-workflows">
      <template #tab>
        <span>
          <UserOutlined />
          {{ t('workspace.workflowSpaceMain.my_workflows') }}
        </span>
      </template>
      <MyWorkflows />
    </a-tab-pane>
    <a-tab-pane key="official-workflow-templates">
      <template #tab>
        <span>
          <AppstoreAddOutlined />
          {{ t('workspace.workflowSpaceMain.official_workflow_template') }}
        </span>
      </template>
      <WorkflowTemplatesMarket />
    </a-tab-pane>
  </a-tabs>
</template>

<style scoped>
.space-container {
  height: calc(100vh - 64px);
}
</style>
  