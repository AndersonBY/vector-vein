<script setup>
import { onBeforeMount, defineComponent, ref, reactive, computed } from "vue"
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import { FullScreenOne, OffScreenOne, Edit, Lightning } from '@icon-park/vue-next'
import VueMarkdown from 'vue-markdown-render'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import { useUserDatabasesStore } from "@/stores/userDatabase"
import ListFieldUse from "@/components/workspace/ListFieldUse.vue"
import UploaderFieldUse from "@/components/workspace/UploaderFieldUse.vue"
import AudioPlayer from "@/components/workspace/AudioPlayer.vue"
import MindmapRenderer from "@/components/workspace/MindmapRenderer.vue"
import MermaidRenderer from "@/components/workspace/MermaidRenderer.vue"
import EchartsRenderer from "@/components/workspace/EchartsRenderer.vue"
import TemperatureInput from '@/components/nodes/TemperatureInput.vue'
import WorkflowRunRecordsDrawer from "@/components/workspace/WorkflowRunRecordsDrawer.vue"
import TextOutput from "@/components/TextOutput.vue"
import { getUIDesignFromWorkflow, hasShowFields, nonFormItemsTypes } from '@/utils/workflow'
import { workflowAPI, workflowRunRecordAPI, workflowScheduleTriggerAPI } from "@/api/workflow"
import { databaseAPI } from "@/api/database"

defineComponent({
  name: 'WorkflowSpace',
})

const { t } = useI18n()
const userSettingsStore = useUserSettingsStore()
const { language, setting } = storeToRefs(userSettingsStore)
const userDatabasesStore = useUserDatabasesStore()
const { userDatabases } = storeToRefs(userDatabasesStore)
const loading = ref(true)
const updating = ref(false)
const userWorkflowsStore = useUserWorkflowsStore()
const route = useRoute()
const router = useRouter()
const workflowId = route.params.workflowId
const briefModalOpen = ref(false)
const briefModalWidth = ref(window.innerWidth <= 768 ? '90vw' : '60vw')
const outputMaximized = ref(false)
const inputFields = ref([])
const outputNodes = ref([])
const triggerNodes = ref([])

onBeforeMount(async () => {
  const getWorkflowRequest = workflowAPI('get', { wid: workflowId })
  const listDatabasesRequest = databaseAPI('list', {})
  const workflowResponse = await getWorkflowRequest
  const listDatabasesResponse = await listDatabasesRequest
  if (listDatabasesResponse.status == 200) {
    userDatabasesStore.setUserDatabases(listDatabasesResponse.data)
  }
  if (workflowResponse.status != 200) {
    message.error(t('workspace.workflowSpace.get_workflow_failed'))
    router.push({ name: 'WorkflowSpaceMain' })
    return
  }
  currentWorkflow.value = workflowResponse.data
  currentWorkflow.value.data.nodes.forEach((node) => {
    if (node.category == "vectorDb") {
      node.data.template.database.options = userDatabases.value.filter((database) => {
        return database.status == 'VALID'
      }).map((item) => {
        return {
          value: item.vid,
          label: item.name,
        }
      })
    }
  })
  const uiDesign = getUIDesignFromWorkflow(currentWorkflow.value)
  const reactiveUIDesign = reactive(uiDesign)
  inputFields.value = reactiveUIDesign.inputFields
  outputNodes.value = reactiveUIDesign.outputNodes
  triggerNodes.value = reactiveUIDesign.triggerNodes

  savedWorkflow.value = JSON.parse(JSON.stringify(currentWorkflow.value))

  if (route.query.rid) {
    const recordRequest = workflowRunRecordAPI('get', { rid: route.query.rid })
    const recordResponse = await recordRequest
    try {
      setWorkflowRecord(recordResponse.data)
    } catch (e) {
      message.error(t('workspace.workflowSpace.get_workflow_record_failed'))
    }
  }

  loading.value = false
})

const clearNodesFiles = () => {
  currentWorkflow.value.data.nodes.forEach((node) => {
    if (node.data.has_inputs) {
      Object.keys(node.data.template).forEach((field) => {
        if (node.data.template[field].field_type == 'file') {
          node.data.template[field].value = []
        }
      })
    }
  })
}

const currentWorkflow = ref({})
const savedWorkflow = ref({})

const running = ref(false)
const checkStatusTimer = ref(null)
const runRecordId = ref(null)
const runWorkflow = async () => {
  runRecordId.value = null
  showingRecord.value = false
  let checkFieldsValid = true
  try {
    inputFields.value.forEach((field) => {
      let currentFieldValid = true
      if (field.field_type == 'checkbox') {
        return
      }
      if (!field.show) {
        return
      }
      if (!field.required) {
        return
      }

      if (field.field_type == 'file' && field.value.length == 0) {
        currentFieldValid = false
      } else if (field.field_type == 'number' && typeof field.value != 'number') {
        currentFieldValid = false
      } else if (!field.value && !field.value === 0) {
        currentFieldValid = false
      }
      if (!currentFieldValid) {
        message.error(t('workspace.workflowSpace.field_is_empty', { field: field.display_name }))
        checkFieldsValid = false
      }
    })
  } catch (errorInfo) {
    checkFieldsValid = false
  }
  if (!checkFieldsValid) {
    return
  }
  let workflowDataForRun = JSON.parse(JSON.stringify(savedWorkflow.value))
  // 遍历workflowDataForRun，找出currentWorkflow中放在了input中展示的让用户填写的字段，将其值替换为currentWorkflow中的值
  workflowDataForRun.data.nodes.forEach((node) => {
    if (node.data.has_inputs && hasShowFields(node) && !['triggers'].includes(node.category)) {
      Object.keys(node.data.template).forEach((field) => {
        if (node.data.template[field].show) {
          node.data.template[field].value = currentWorkflow.value.data.nodes.find((item) => {
            return item.id == node.id
          }).data.template[field].value
        }
      })
    }
  })
  running.value = true
  workflowDataForRun.data.setting = setting.value.data
  const response = await workflowAPI('run', workflowDataForRun)
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.submit_workflow_success'))
    runRecordId.value = response.data.rid
    checkStatusTimer.value = setInterval(async () => {
      const response = await workflowAPI('check_status', { rid: runRecordId.value })
      if (response.status == 200) {
        message.success(t('workspace.workflowSpace.run_workflow_success'))
        clearInterval(checkStatusTimer.value)
        running.value = false
        currentWorkflow.value = response.data
        const uiDesign = getUIDesignFromWorkflow(currentWorkflow.value)
        const reactiveUIDesign = reactive(uiDesign)
        inputFields.value = reactiveUIDesign.inputFields
        outputNodes.value = reactiveUIDesign.outputNodes
        triggerNodes.value = reactiveUIDesign.triggerNodes
        // clearNodesFiles()
      } else if (response.status == 500) {
        running.value = false
        recordStatus.value = 'FAILED'
        message.error(t('workspace.workflowSpace.run_workflow_failed'))
        clearInterval(checkStatusTimer.value)
        setErrorTask(response.data.error_task)
        showingRecord.value = true
      }
    }, 1000)
  } else {
    message.error(t('workspace.workflowSpace.submit_workflow_failed'))
    running.value = false
  }
}

const updateWorkflowScheduleTrigger = async () => {
  running.value = true
  const response = await workflowScheduleTriggerAPI('update', {
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    ...currentWorkflow.value
  })
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.update_schedule_success'))
  } else {
    message.error(t('workspace.workflowSpace.update_schedule_failed'))
  }
  running.value = false
}

const deletingSchedule = ref(false)
const deleteWorkflowScheduleTrigger = async () => {
  deletingSchedule.value = true
  const response = await workflowScheduleTriggerAPI('delete', {
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    ...currentWorkflow.value
  })
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.delete_schedule_success'))
  } else {
    message.error(t('workspace.workflowSpace.delete_schedule_failed'))
  }
  deletingSchedule.value = false
}

const deleteWorkflow = async () => {
  const response = await workflowAPI('delete', { wid: currentWorkflow.value.wid })
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.delete_success'))
    userWorkflowsStore.deleteUserWorkflow(currentWorkflow.value.wid)
    userWorkflowsStore.deleteUserWorkflow(currentWorkflow.value.wid, true)
    router.push({ name: 'WorkflowSpaceMain' })
  } else {
    message.error(t('workspace.workflowSpace.delete_failed'))
  }
}

const openEditor = () => {
  router.push({ name: 'WorkflowEditor', params: { workflowId: workflowId } })
}

const showingRecord = ref(false)
const recordStatus = ref('')
const recordErrorTask = ref('')
const alertType = computed(() => {
  if (recordStatus.value == 'FINISHED') {
    return 'success'
  }
  else if (recordStatus.value == 'FAILED') {
    return 'error'
  }
  else {
    return 'info'
  }
})
const setErrorTask = (errorTask) => {
  let [category, node] = (errorTask || '.').split('.')
  category = category.split('_')
    .map((word, index) => {
      if (index === 0) {
        return word.charAt(0).toLowerCase() + word.slice(1);
      }
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join('')
  if (category == 'output') {
    category = 'outputs'
  }
  node = node.split('_')
    .map((word) => {
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join('')
  if (node == 'OpenAi') {
    node = 'OpenAI'
  } else if (node == 'ChatGlm') {
    node = 'ChatGLM'
  } else if (node == 'SearchData' && category == 'vectorDb') {
    node = 'Search'
  }
  recordErrorTask.value = `${category}.${node}`
}
const setWorkflowRecord = (record) => {
  runRecordId.value = record.rid
  recordStatus.value = record.status
  currentWorkflow.value.data = {
    ...record.data,
    ui: savedWorkflow.value.data.ui || {}
  }
  setErrorTask(record.data.error_task)
  const uiDesign = getUIDesignFromWorkflow(currentWorkflow.value)
  const reactiveUIDesign = reactive(uiDesign)
  inputFields.value = reactiveUIDesign.inputFields
  outputNodes.value = reactiveUIDesign.outputNodes
  triggerNodes.value = reactiveUIDesign.triggerNodes
  showingRecord.value = true
}

const openLocalFile = (file) => {
  window.pywebview.api.open_local_file(file)
}
</script>

<template>
  <div class="space-container" v-if="loading">
    <a-skeleton active />
  </div>
  <a-spin :spinning="updating" class="space-container" v-else>
    <a-row justify="space-between" align="middle">
      <a-col>
        <a-typography-title>
          {{ currentWorkflow.title }}
        </a-typography-title>
        <a-space>
          <a-typography-text type="secondary">
            {{ t('workspace.workflowSpace.update_time', {
              time: new
                Date(currentWorkflow.update_time).toLocaleString()
            }) }}
          </a-typography-text>
          <a-divider type="vertical" />
          <a-typography-link @click="briefModalOpen = true">
            {{ t('workspace.workflowSpace.brief') }}
            <a-modal :open="briefModalOpen" :title="t('workspace.workflowSpace.brief')" :width="briefModalWidth"
              :footer="null" class="introduction-modal" @cancel="briefModalOpen = false">
              <a-carousel autoplay arrows dots-class="slick-dots slick-thumb">
                <template #customPaging="props">
                  <a>
                    <img :src="currentWorkflow.images[props.i]" />
                  </a>
                </template>
                <div v-for="(image, index) in currentWorkflow.images" :key="index">
                  <img :src="image" />
                </div>
              </a-carousel>
              <VueMarkdown v-highlight :source="currentWorkflow.brief"
                class="custom-scrollbar markdown-body custom-hljs" />
            </a-modal>
          </a-typography-link>
          <a-divider type="vertical" />
          <a-tag :color="tag.color" v-for="(tag, index) in currentWorkflow.tags" :key="index">
            {{ tag.title }}
          </a-tag>
        </a-space>
      </a-col>
      <a-col>
        <a-space>
          <WorkflowRunRecordsDrawer :workflowId="workflowId" @open-record="setWorkflowRecord" />
          <a-button @click="openEditor">
            {{ t('workspace.workflowSpace.edit') }}
          </a-button>
          <a-popconfirm placement="leftTop" :title="t('workspace.workflowSpace.delete_confirm')"
            @confirm="deleteWorkflow">
            <a-button type="primary" danger>
              {{ t('workspace.workflowSpace.delete') }}
            </a-button>
          </a-popconfirm>
        </a-space>
      </a-col>
    </a-row>
    <a-divider />
    <a-row :gutter="[16, 16]">
      <a-col :span="24" v-if="showingRecord">
        <a-alert :type="alertType" show-icon>
          <template #message>
            <span>
              {{ t('workspace.workflowSpace.record_status', {
                status:
                  t(`components.workspace.workflowRunRecordsDrawer.status_${recordStatus.toLowerCase()}`)
              }) }}
            </span>
            <a-divider type="vertical" />
            <span v-if="recordStatus == 'FAILED' && recordErrorTask != '.'">
              {{ t('workspace.workflowSpace.record_error_task', {
                task: t('components.nodes.' + recordErrorTask + '.title')
              }) }}
            </span>
          </template>
        </a-alert>
      </a-col>

      <a-col :xxl="6" :xl="8" :lg="10" :md="24" v-show="!outputMaximized">
        <a-row :gutter="[16, 16]">
          <a-typography-title :level="3">
            <Edit fill="#28c5e5" />
            {{ t('workspace.workflowSpace.inputs') }}
          </a-typography-title>
          <a-col :span="24">
            <a-form layout="vertical">
              <div v-for="( field, fieldIndex ) in inputFields " :key="`field-${field}-${fieldIndex}`">
                <a-form-item v-if="!nonFormItemsTypes.includes(field.field_type)">
                  <template #label>
                    {{ field.display_name }}
                  </template>
                  <TemperatureInput v-model="field.value" v-if="field.category == 'llms' && field == 'temperature'" />
                  <a-select v-model:value="field.value" :options="field.options"
                    v-else-if="field.field_type == 'select'" />
                  <a-textarea v-model:value="field.value" :autoSize="true" :showCount="true"
                    :placeholder="field.placeholder" v-else-if="field.field_type == 'textarea'" />
                  <a-input v-model:value="field.value" :placeholder="field.placeholder"
                    v-else-if="field.field_type == 'input'" />
                  <a-input-number v-model:value="field.value" :placeholder="field.placeholder"
                    v-else-if="field.field_type == 'number'" />
                  <a-checkbox v-model:checked="field.value" v-else-if="field.field_type == 'checkbox'" />
                  <UploaderFieldUse v-model="field.value" v-else-if="field.field_type == 'file'" />
                  <ListFieldUse v-model="field.value" v-else-if="field.field_type == 'list'" />
                </a-form-item>
                <a-row v-if="field.field_type == 'typography-paragraph'">
                  <a-col :span="24" class="ui-special-item-container">
                    <vue-markdown v-highlight :source="field.value" class="markdown-body custom-hljs ui-special-item" />
                  </a-col>
                </a-row>
              </div>
            </a-form>
          </a-col>

          <a-divider />

          <a-col :span="24">
            <a-row :gutter="[16, 16]">
              <template v-for="(node) in triggerNodes" :key="`node-${node.id}`">
                <a-col :span="24">
                  <a-button type="primary" block @click="runWorkflow" :loading="running"
                    v-if="node.type == 'ButtonTrigger'">
                    {{ node.data.template.button_text.value }}
                  </a-button>
                  <a-card :title="t('components.nodes.triggers.ScheduleTrigger.schedule_settings')"
                    v-else-if="node.type == 'ScheduleTrigger'">
                    <template #extra>
                      <a-space>
                        <a-button type="primary" @click="updateWorkflowScheduleTrigger" :loading="running">
                          {{ t('components.nodes.triggers.ScheduleTrigger.save_schedule_settings') }}
                        </a-button>
                        <a-popconfirm :title="t('workspace.workflowSpace.delete_schedule_trigger_confirm')"
                          @confirm="deleteWorkflowScheduleTrigger">
                          <a-button type="primary" danger>
                            {{ t('workspace.workflowSpace.delete') }}
                          </a-button>
                        </a-popconfirm>
                      </a-space>
                    </template>
                    <cron-ant v-model="node.data.template.schedule.value"
                      :button-props="{ type: 'primary', shape: 'round', }" :locale="language" />
                  </a-card>
                </a-col>
              </template>
            </a-row>
          </a-col>
        </a-row>
      </a-col>

      <a-col :xxl="outputMaximized ? 24 : 18" :xl="outputMaximized ? 24 : 16" :lg="outputMaximized ? 24 : 14" :md="24">
        <a-typography-title :level="3" style="display: flex; justify-content: space-between;">
          <span>
            <lightning fill="#28c5e5" />
            {{ t('workspace.workflowSpace.outputs') }}
          </span>
          <span>
            <a-tooltip :title="t('workspace.workflowSpace.maximize_output')">
              <FullScreenOne @click="outputMaximized = !outputMaximized" v-show="!outputMaximized" />
            </a-tooltip>
            <a-tooltip :title="t('workspace.workflowSpace.normalize_output')">
              <OffScreenOne @click="outputMaximized = !outputMaximized" v-show="outputMaximized" />
            </a-tooltip>
          </span>
        </a-typography-title>
        <a-spin :spinning="running">
          <a-row :gutter="[16, 16]">
            <a-col :span="24" class="draggable-item" v-for="(node, index) in outputNodes"
              :key="`node-${node.id}-${index}`">
              <div v-if="node.type == 'Text'">
                <a-typography-title :level="5">
                  {{ node.data.template.output_title.value }}
                </a-typography-title>
                <TextOutput :text="node.data.template.text.value"
                  :renderMarkdown="node.data.template.render_markdown.value" />
              </div>

              <div v-else-if="node.type == 'Document'">
                <a-typography-link @click="openLocalFile(node.data.template.output.value)">
                  {{ node.data.template.output.value }}
                </a-typography-link>
              </div>

              <div v-else-if="node.type == 'Audio'">
                <AudioPlayer :audios="[node.data.template.audio_url?.value]" />
              </div>

              <div v-else-if="node.type == 'Mindmap'">
                <MindmapRenderer :content="node.data.template.content.value" style="width: 100%;min-height: 50vh;" />
              </div>

              <div v-else-if="node.type == 'Mermaid'">
                <MermaidRenderer :content="node.data.template.content.value" style="width: 100%;min-height: 50vh;" />
              </div>

              <div v-else-if="node.type == 'Echarts'">
                <EchartsRenderer :option="node.data.template.option.value" style="width: 100%;min-height: 50vh;" />
              </div>

              <div v-else>
                <div v-if="node.field_type == 'typography-paragraph'">
                  <vue-markdown v-highlight :source="node.value" class="markdown-body custom-hljs ui-special-item" />
                </div>
              </div>
            </a-col>
          </a-row>
        </a-spin>
      </a-col>
    </a-row>
  </a-spin>
</template>

<style scoped>
.space-container {
  height: calc(100vh - 64px);
}

.ui-special-item {
  margin-bottom: 24px;
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
</style>