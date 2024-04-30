<script setup>
import { onBeforeMount, ref } from "vue"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import VueMarkdown from 'vue-markdown-render'
import { workflowAPI, workflowTemplateAPI } from "@/api/workflow"

const open = ref(false)
const show = ref(false)
const emit = defineEmits(['selected'])
const props = defineProps({
  workflowId: {
    type: String,
    required: true,
  },
  isTemplate: {
    type: Boolean,
    default: false,
  },
})

const activeKey = ref()
const workflowOrTemplateAPI = props.isTemplate ? workflowTemplateAPI : workflowAPI
const queryKey = props.isTemplate ? 'tid' : 'wid'
const pluralKey = props.isTemplate ? 'templates' : 'workflows'

const { t } = useI18n()
const loading = ref(true)
const modalWidth = ref(window.innerWidth <= 768 ? '90vw' : '60vw')
const relatedWorkflows = ref([])

onBeforeMount(async () => {
  const response = await workflowOrTemplateAPI('list', { workflow_related: props.workflowId, page_size: 100 })
  if (response.status != 200) {
    message.error(t('workspace.workflowSpace.get_workflow_failed'))
  } else {
    relatedWorkflows.value = response.data[pluralKey]
    if (relatedWorkflows.value.length > 0) activeKey.value = relatedWorkflows.value[0][queryKey]
  }
  if (relatedWorkflows.value.length > 0) {
    show.value = true
  }
  loading.value = false
})
</script>

<template>
  <div v-if="!loading">
    <a-typography-link class="related-workflows-link-text" @click="open = true" v-if="show">
      {{ t('workspace.workflowSpace.related_workflows') }}
    </a-typography-link>
    <a-modal :open="open" :title="t('components.workspace.relatedWorkflowsModal.title')" :width="modalWidth"
      :footer="null" :destroyOnClose="true" class="introduction-modal" @cancel="open = false">
      <a-tabs v-model:activeKey="activeKey" tab-position="left" :tabBarStyle="{ maxWidth: '250px' }">
        <a-tab-pane v-for="relatedWorkflow in relatedWorkflows" :key="relatedWorkflow[queryKey]"
          :tab="relatedWorkflow.title">
          <template v-if="isTemplate || relatedWorkflow.is_template">
            <a-typography-link :href="`/workspace/workflow/template/${relatedWorkflow.tid}`" class="workflow-title">
              {{ t('workspace.workflowTemplate.template') }}: {{ relatedWorkflow.title }}
            </a-typography-link>
          </template>
          <template v-else>
            <a-typography-link :href="`/workspace/workflow/${relatedWorkflow.wid}`" class="workflow-title">
              {{ relatedWorkflow.title }}
            </a-typography-link>
          </template>
          <a-typography-text type="secondary">
            {{ t('workspace.workflowSpace.update_time', {
    time: new
      Date(parseInt(relatedWorkflow.update_time)).toLocaleString()
  }) }}
          </a-typography-text>
          <a-divider></a-divider>
          <VueMarkdown v-highlight :source="relatedWorkflow.brief" :options="{ html: true }"
            class="custom-scrollbar markdown-body custom-hljs" />
        </a-tab-pane>
      </a-tabs>
    </a-modal>
  </div>
</template>

<style scoped>
.workflow-title {
  display: block;
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 16px;
}

.related-workflows-link-text {
  font-weight: 400;
}
</style>