<script setup>
import { onBeforeMount, onBeforeUnmount, ref, reactive, computed } from "vue"
import { useRouter } from "vue-router"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { FullScreenOne, OffScreenOne, Edit, Lightning, Dot, PlayOne, Eeg } from '@icon-park/vue-next'
import ReconnectingWebSocket from 'reconnecting-websocket'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import { useUserDatabasesStore } from "@/stores/userDatabase"
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import { useUserRelationalDatabasesStore } from "@/stores/userRelationalDatabase"
import ListFieldUse from "@/components/workspace/ListFieldUse.vue"
import UploaderFieldUse from "@/components/workspace/UploaderFieldUse.vue"
import AudioPlayer from "@/components/workspace/AudioPlayer.vue"
import MindmapRenderer from "@/components/workspace/MindmapRenderer.vue"
import MermaidRenderer from "@/components/workspace/MermaidRenderer.vue"
import EchartsRenderer from "@/components/workspace/EchartsRenderer.vue"
import TableRenderer from "@/components/workspace/TableRenderer.vue"
import TemperatureInput from '@/components/nodes/TemperatureInput.vue'
import WorkflowRecordStatusAlert from "@/components/workspace/WorkflowRecordStatusAlert.vue"
import TextOutput from "@/components/TextOutput.vue"
import {
  hasShowFields,
  checkFieldsValid,
  nonFormItemsTypes,
  getNodeConnectedNodes,
  getUIDesignFromWorkflow,
} from '@/utils/workflow'
import { deepCopy } from '@/utils/util'
import { settingAPI } from '@/api/user'
import { workflowAPI } from '@/api/workflow'
import { databaseAPI, relationalDatabaseAPI } from "@/api/database"

const props = defineProps({
  workflow: {
    type: Object,
    required: true,
  },
  isTemplate: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const { t } = useI18n()
const userSettings = useUserSettingsStore()
const { setting } = storeToRefs(userSettings)
const userDatabasesStore = useUserDatabasesStore()
const { userDatabases } = storeToRefs(userDatabasesStore)
const userRelationalDatabasesStore = useUserRelationalDatabasesStore()
const { userRelationalDatabases } = storeToRefs(userRelationalDatabasesStore)
const userWorkflowsStore = useUserWorkflowsStore()
const loading = ref(true)
const outputMaximized = ref(false)
const inputFields = ref([])
const outputNodes = ref([])
const triggerNodes = ref([])
const humanFeedbackNodes = ref([])
const streamableNodes = ref([])
const edges = ref([])

const currentWorkflow = ref({})
const savedWorkflow = ref({}) // 

function setCurrentWorkflow(workflow) {
  currentWorkflow.value = deepCopy(workflow)
  currentWorkflow.value.data.nodes.forEach(node => {
    if (node.category === 'vectorDb') {
      node.data.template.database.options = userDatabases.value
        .filter(database => database.status === 'VALID')
        .map(item => ({
          value: item.vid,
          label: item.name,
        }));
    } else if (node.category === 'relationalDb') {
      node.data.template.database.options = userRelationalDatabases.value
        .filter(database => database.status === 'VALID')
        .map(item => ({
          value: item.rid,
          label: item.name,
        }));
    } else if (node.type === 'LocalLlm') {
      node.data.template.model_family.options = Object.keys(setting.value.data?.custom_llms)?.map((llm) => ({
        value: llm,
        text: llm,
      }))

      const models = setting.value.data?.custom_llms[node.data.template.model_family.value]
      node.data.template.llm_model.options = models ? models.map((model) => ({
        value: model,
        text: model,
      })) : []
    }
  });

  if (currentWorkflow.value.ui_design) {
    inputFields.value = currentWorkflow.value.ui_design.input_fields
    outputNodes.value = currentWorkflow.value.ui_design.output_nodes
    triggerNodes.value = currentWorkflow.value.ui_design.trigger_nodes
    humanFeedbackNodes.value = currentWorkflow.value.ui_design.human_feedback_nodes
    edges.value = currentWorkflow.value.ui_design?.edges || []
  } else {
    const uiDesign = getUIDesignFromWorkflow(currentWorkflow.value)
    const reactiveUIDesign = reactive(uiDesign)
    inputFields.value = reactiveUIDesign.inputFields
    outputNodes.value = reactiveUIDesign.outputNodes
    triggerNodes.value = reactiveUIDesign.triggerNodes
    humanFeedbackNodes.value = reactiveUIDesign.humanFeedbackNodes
    edges.value = currentWorkflow.value.data.edges || []
  }

  const nodeModelFamilies = ref({})

  inputFields.value.forEach((field) => {
    if (field.nodeType === 'LocalLlm' && field.fieldName === 'model_family') {
      nodeModelFamilies.value[field.nodeId] = field
    }
  })

  inputFields.value.forEach((field) => {
    if (field.nodeType === 'LocalLlm' && field.fieldName === 'llm_model') {
      if (nodeModelFamilies.value[field.nodeId]) {
        field.options = computed(() => {
          const modelFamily = nodeModelFamilies.value[field.nodeId].value
          const models = setting.value.data?.custom_llms[modelFamily]
          return models ? models.map((model) => ({
            value: model,
            text: model,
          })) : []
        })
      }
    }
  })
}

onBeforeMount(async () => {
  currentWorkflow.value = props.workflow
  const hasVectorDbNode = currentWorkflow.value.data.nodes.some(node => node.category === 'vectorDb');
  const hasRelationalDbNode = currentWorkflow.value.data.nodes.some(node => node.category === 'relationalDb');

  const requests = [];

  if (hasVectorDbNode) {
    requests.push(databaseAPI('list', {}));
  }

  if (hasRelationalDbNode) {
    requests.push(relationalDatabaseAPI('list', {}));
  }

  const responses = await Promise.all(requests);

  let listVectorDBResponse, listRelationalDBResponse;

  if (hasVectorDbNode) {
    listVectorDBResponse = responses.shift();
    if (listVectorDBResponse.status === 200) {
      userDatabasesStore.setUserDatabases(listVectorDBResponse.data);
    }
  }

  if (hasRelationalDbNode) {
    listRelationalDBResponse = responses.shift();
    if (listRelationalDBResponse.status === 200) {
      userRelationalDatabasesStore.setUserRelationalDatabases(listRelationalDBResponse.data);
    }
  }

  setCurrentWorkflow(currentWorkflow.value)

  savedWorkflow.value = deepCopy(currentWorkflow.value)

  loading.value = false
})
onBeforeUnmount(() => {
  clearInterval(checkStatusTimer.value)
})

const wsPort = ref(null)

const checkingStatus = ref(false)
const checkWorkflowRunningStatus = async () => {
  if (checkingStatus.value) {
    return
  }
  checkingStatus.value = true
  const statusResponse = await workflowAPI('check_status', { rid: runRecordId.value })
  if (statusResponse.status == 200) {
    message.success(t('workspace.workflowSpace.run_workflow_success'))
    clearInterval(checkStatusTimer.value)
    running.value = false
    recordStatus.value = 'FINISHED'
    currentWorkflow.value = statusResponse.data
    currentWorkflow.value.data.ui = savedWorkflow.value.data?.ui || currentWorkflow.value.data?.ui_design
    if (currentWorkflow.value.data?.ui_design) {
      // currentWorkflow.value.data?.ui_design 里的是运行结果的ui_design
      // currentWorkflow.value.ui_design 里的是原本工作流的ui_design
      const uiDesign = currentWorkflow.value.data.ui_design
      outputNodes.value = uiDesign.output_nodes
      triggerNodes.value = uiDesign.trigger_nodes
      humanFeedbackNodes.value = uiDesign.human_feedback_nodes
    } else {
      const uiDesign = getUIDesignFromWorkflow(currentWorkflow.value)
      const reactiveUIDesign = reactive(uiDesign)
      inputFields.value = reactiveUIDesign.inputFields
      outputNodes.value = reactiveUIDesign.outputNodes
      triggerNodes.value = reactiveUIDesign.triggerNodes
      humanFeedbackNodes.value = reactiveUIDesign.humanFeedbackNodes
    }
    showingRecord.value = true

  } else if (statusResponse.status == 202) {
    const finishedNodes = statusResponse.data.finished_nodes ?? []
    outputNodes.value.forEach((node) => {
      const finishedNode = finishedNodes.find((item) => {
        return item.id == node.id
      })
      if (finishedNode) {
        node.data = finishedNode.data
        node.finished = true
      }
    })
    finishedNodes.forEach(async (node) => {
      if (node.category == 'llms') {
        const isExist = streamableNodes.value.some((item) => item.id == node.id)
        if (!isExist) {
          streamableNodes.value.push(node)
          const connectedNodes = getNodeConnectedNodes(node.id, 'output', edges.value)
          // 找出 connectedNodes 中在 outputNodes 中且是 Text 的Type的节点，获取 node 对象
          const textNodeIds = connectedNodes.filter((item) => {
            return outputNodes.value.some((outputNode) => outputNode.id == item && outputNode.type == 'Text')
          })
          const textNodes = outputNodes.value.filter((item) => textNodeIds.includes(item.id))
          textNodes.forEach((textNode) => {
            textNode.data.template.text.value = ''
            textNode.finished = true
          })

          if (wsPort.value === null) {
            const res = await settingAPI('get_port', { port_name: 'chat_ws_port' })
            wsPort.value = res.data.port
          }
          const chatSocket = new ReconnectingWebSocket(
            `ws://localhost:${wsPort.value}/ws/workflow_node/${runRecordId.value}_${node.id}`,
            null,
            { maxReconnectAttempts: 5 }
          );

          chatSocket.onopen = () => {
            chatSocket.send('start')
            console.log('连接成功')
          }
          chatSocket.onmessage = async (e) => {
            const data = JSON.parse(e.data)
            if (data.end) {
              chatSocket.close()
              return
            }
            textNodes.forEach((textNode) => {
              textNode.data.template.text.value += data.content || ''
            });
          }

          if (node.type === 'Deepseek') {
            const connectedNodes = getNodeConnectedNodes(node.id, 'reasoning_content', edges.value)
            // 找出 connectedNodes 中在 outputNodes 中且是 Text 的Type的节点，获取 node 对象
            const textNodeIds = connectedNodes.filter((item) => {
              return outputNodes.value.some((outputNode) => outputNode.id == item && outputNode.type == 'Text')
            })
            const textNodes = outputNodes.value.filter((item) => textNodeIds.includes(item.id))
            textNodes.forEach((textNode) => {
              textNode.data.template.text.value = ''
              textNode.finished = true
            })

            const chatSocket = new ReconnectingWebSocket(
              `ws://localhost:${wsPort.value}/ws/workflow_node/${runRecordId.value}_${node.id}`,
              null,
              { maxReconnectAttempts: 5 }
            );

            chatSocket.onopen = () => {
              chatSocket.send('start')
              console.log('连接成功')
            }
            chatSocket.onmessage = async (e) => {
              const data = JSON.parse(e.data)
              if (data.end) {
                chatSocket.close()
                return
              }
              textNodes.forEach((textNode) => {
                textNode.data.template.text.value += data.reasoning_content
              });
            }
          }
        }
      }
    })
  } else if (statusResponse.status == 500) {
    running.value = false
    recordStatus.value = 'FAILED'
    currentWorkflow.value = statusResponse.data
    currentWorkflow.value.data.ui = savedWorkflow.value.data?.ui || {}
    if (currentWorkflow.value.data?.ui_design) {
      const uiDesign = currentWorkflow.value.data.ui_design
      outputNodes.value = uiDesign.output_nodes
      triggerNodes.value = uiDesign.trigger_nodes
      humanFeedbackNodes.value = uiDesign.human_feedback_nodes
    } else {
      const uiDesign = getUIDesignFromWorkflow(currentWorkflow.value)
      const reactiveUIDesign = reactive(uiDesign)
      inputFields.value = reactiveUIDesign.inputFields
      outputNodes.value = reactiveUIDesign.outputNodes
      triggerNodes.value = reactiveUIDesign.triggerNodes
      humanFeedbackNodes.value = reactiveUIDesign.humanFeedbackNodes
    }
    message.error(t('workspace.workflowSpace.run_workflow_failed'))
    clearInterval(checkStatusTimer.value)
    rawErrorTask.value = statusResponse.data?.data?.error_task
    showingRecord.value = true
  }
  checkingStatus.value = false
}

const runWorkflowVersionModal = ref(false)

const running = ref(false)
const checkStatusTimer = ref(null)
const runRecordId = ref(null)
const runWorkflow = async (workflowVersion = null) => {
  let workflowDataForRun = deepCopy(savedWorkflow.value)
  if (savedWorkflow.value.version !== null && currentWorkflow.value.version !== null && savedWorkflow.value.version !== currentWorkflow.value.version) {
    if (workflowVersion === null) {
      runWorkflowVersionModal.value = true
      return
    } else {
      runWorkflowVersionModal.value = false
      switch (workflowVersion) {
        case 'record':
          workflowDataForRun = deepCopy(currentWorkflow.value)
          break;
        case 'latest':
          workflowDataForRun = deepCopy(savedWorkflow.value)
          break;
        default:
          return
      }
    }
  }

  runRecordId.value = null
  showingRecord.value = false
  streamableNodes.value = []
  if (!checkFieldsValid(inputFields.value)) {
    return
  }
  // Iterate all nodes from workflowDataForRun, update the value of fields that are shown from currentWorkflow
  // 这样做的目的是如果每次都直接提交currentWorkflow的话，由于currentWorkflow是会被运行结果更新的，如果一旦更新后再次提交
  // 有些字段的类型就直接发生改变了，运行会报错
  if (workflowDataForRun.data?.nodes) {
    workflowDataForRun.data.nodes.forEach((node) => {
      if (node.data.has_inputs && hasShowFields(node) && !['triggers'].includes(node.category)) {
        Object.keys(node.data.template).forEach((field) => {
          if (node.data.template[field].show) {
            const inputField = inputFields.value.find((item) => item.nodeId == node.id && item.fieldName == field)
            if (inputField) {
              node.data.template[field].value = inputField.value
            }
          }
        })
      }
    })
  }
  outputNodes.value.forEach((node) => {
    if (node.category == 'outputs') {
      node.finished = false
    }
    return node
  })
  running.value = true
  let response
  if (props.isTemplate) {
    response = await workflowAPI('run-template', workflowDataForRun)
  } else {
    response = await workflowAPI('run', workflowDataForRun)
  }
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.submit_workflow_success'))
    runRecordId.value = response.data.rid
    checkStatusTimer.value = setInterval(checkWorkflowRunningStatus, 1000)
  } else {
    message.error(t('workspace.workflowSpace.submit_workflow_failed'))
    running.value = false
  }
}

const showingRecord = ref(false)
const recordStatus = ref('')
const rawErrorTask = ref('')

function setWorkflowRecord(record) {
  runRecordId.value = record.rid
  recordStatus.value = record.status
  if (record.status == 'RUNNING') {
    running.value = true
    checkStatusTimer.value = setInterval(checkWorkflowRunningStatus, 1000)
  }
  currentWorkflow.value.data = {
    ...record.data,
    ui: savedWorkflow.value.data?.ui || {}
  }
  currentWorkflow.value.shared = record.shared
  currentWorkflow.value.is_public = record.is_public
  currentWorkflow.value.public_shared_record = record.public_shared_record
  currentWorkflow.value.version = record.workflow_version
  rawErrorTask.value = record.data.error_task
  if (currentWorkflow.value.data?.ui_design) {
    // currentWorkflow.value.data?.ui_design 里的是运行结果的 ui_design
    // currentWorkflow.value.ui_design 里的是原本工作流的 ui_design
    const uiDesign = currentWorkflow.value.data.ui_design
    inputFields.value = uiDesign.input_fields
    outputNodes.value = uiDesign.output_nodes
    triggerNodes.value = uiDesign.trigger_nodes
    humanFeedbackNodes.value = uiDesign.human_feedback_nodes
  } else {
    const uiDesign = getUIDesignFromWorkflow(currentWorkflow.value)
    const reactiveUIDesign = reactive(uiDesign)
    inputFields.value = reactiveUIDesign.inputFields
    outputNodes.value = reactiveUIDesign.outputNodes
    triggerNodes.value = reactiveUIDesign.triggerNodes
    humanFeedbackNodes.value = reactiveUIDesign.humanFeedbackNodes
  }
  showingRecord.value = true
}

const openLocalFile = (file) => {
  window.pywebview.api.open_local_file(file)
}

const router = useRouter()
const diagnosisRecord = async () => {
  userWorkflowsStore.setDiagnosisRecord(currentWorkflow.value)
  await router.push({
    name: 'WorkflowEditor',
    params: { workflowId: props.workflow.wid },
    query: { rid: runRecordId.value }
  })
}

defineExpose({
  setWorkflowRecord,
})

function clearWorkflow() {
  setCurrentWorkflow(savedWorkflow.value)
}
</script>

<template>
  <div class="space-container" v-if="loading">
    <a-skeleton active />
  </div>
  <a-row :gutter="[16, 16]" class="main-use-container" v-else>
    <a-col :span="24" v-if="showingRecord">
      <WorkflowRecordStatusAlert :key="`${runRecordId}-${recordStatus}`"
        :recordWorkflowVersion="currentWorkflow.version" :status="recordStatus" :rawErrorTask="rawErrorTask"
        @close="clearWorkflow" />
    </a-col>

    <a-col :xxl="6" :xl="8" :lg="10" :md="24" :sm="24" :xs="24" v-show="!outputMaximized" style="width: 100%;">
      <a-flex vertical gap="small">
        <a-typography-title :level="3">
          <Edit fill="#28c5e5" />
          {{ t('workspace.workflowSpace.inputs') }}
        </a-typography-title>
        <a-form layout="vertical">
          <div v-for="(field, fieldIndex) in inputFields" :key="`field-${field}-${fieldIndex}`">
            <a-form-item v-if="!nonFormItemsTypes.includes(field.field_type)">
              <template #label>
                {{ field.display_name }}
              </template>
              <TemperatureInput v-model="field.value" v-if="field.field_type == 'temperature'" />
              <a-select v-else-if="field.field_type == 'select'" v-model:value="field.value" :options="field.options" />
              <a-textarea v-model:value="field.value" :autoSize="{ minRows: 2, maxRows: 30 }" :showCount="true"
                :placeholder="field.placeholder" :maxlength="field.max_length ?? null"
                v-else-if="field.field_type == 'textarea'" />
              <a-input v-model:value="field.value" :placeholder="field.placeholder"
                :maxlength="field.max_length ?? null" v-else-if="field.field_type == 'input'" />
              <a-input-number v-model:value="field.value" :placeholder="field.placeholder" :max="field.max ?? null"
                :min="field.min ?? null" v-else-if="field.field_type == 'number'" />
              <a-checkbox v-model:checked="field.value" v-else-if="field.field_type == 'checkbox'" />
              <UploaderFieldUse v-else-if="field.field_type == 'file'" v-model="field.value" :multiple="true"
                :supportFileTypes="field.support_file_types || '.docx, .pptx, .xlsx, .pdf, .txt, .md, .html, .json, .csv, .srt, .zip'" />
              <ListFieldUse v-model="field.value" v-else-if="field.field_type == 'list'" />
            </a-form-item>
            <a-row v-if="field.field_type == 'typography-paragraph'">
              <a-col :span="24" class="ui-special-item-container">
                <TextOutput :text="field.value" :showCopy="false" class="ui-special-item" />
              </a-col>
            </a-row>
          </div>
        </a-form>

        <a-divider />

        <a-flex vertical gap="small">
          <template v-for="(node) in triggerNodes" :key="`node-${node.id}`">
            <a-button type="primary" block @click="runWorkflow(null)" :loading="running"
              v-if="node.type == 'ButtonTrigger'">
              <template #icon>
                <PlayOne />
              </template>
              {{ node.data.template.button_text.value }}
            </a-button>
          </template>
        </a-flex>
      </a-flex>
    </a-col>

    <a-col class="output-container" :xxl="outputMaximized ? 24 : 18" :xl="outputMaximized ? 24 : 16"
      :lg="outputMaximized ? 24 : 14" :md="24" style="width: 100%;">
      <a-typography-title :level="3" style="display: flex; justify-content: space-between;">
        <span>
          <lightning fill="#28c5e5" />
          {{ t('workspace.workflowSpace.outputs') }}
        </span>
        <a-space>
          <a-button v-if="showingRecord && !isTemplate" type="text" size="small" @click="diagnosisRecord">
            <template #icon>
              <Eeg />
            </template>
          </a-button>
          <a-tooltip placement="topLeft" :title="t('workspace.workflowSpace.maximize_output')">
            <a-button type="text" size="small" @click="outputMaximized = !outputMaximized" v-show="!outputMaximized">
              <template #icon>
                <FullScreenOne />
              </template>
            </a-button>
          </a-tooltip>
          <a-tooltip placement="topLeft" :title="t('workspace.workflowSpace.normalize_output')">
            <a-button type="text" size="small" @click="outputMaximized = !outputMaximized" v-show="outputMaximized">
              <template #icon>
                <OffScreenOne />
              </template>
            </a-button>
          </a-tooltip>
        </a-space>
      </a-typography-title>
      <a-flex vertical gap="small">
        <a-spin :spinning="running && !node.finished && node.field_type != 'typography-paragraph'"
          class="draggable-item" v-for="(node, index) in outputNodes" :key="`node-${node.id}-${index}`">
          <div v-if="node.type == 'Text'">
            <a-typography-title :level="5" class="text-output-title">
              <Dot fill="#28c5e5" />
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
            <AudioPlayer :audios="[node.data.template.audio_url?.value]" :isMidi="node.data.template.is_midi?.value" />
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

          <div v-else-if="node.type == 'Table'">
            <TableRenderer :data="node.data.template.output.value" :bordered="node.data.template.bordered.value"
              style="width: 100%;" />
          </div>

          <div v-else-if="node.type == 'Html'">
            <iframe class="html-iframe" :src="node.data.template.output.value" />
          </div>

          <div v-else>
            <div v-if="node.field_type == 'typography-paragraph'">
              <TextOutput :text="node.value" :showCopy="false" class="ui-special-item" />
            </div>
          </div>
        </a-spin>
      </a-flex>
    </a-col>

    <a-modal v-model:open="runWorkflowVersionModal"
      :title="t('workspace.workflowSpace.run_workflow_version_inconsistent')" :footer="false">
      <a-typography-paragraph :content="t('workspace.workflowSpace.run_workflow_version_inconsistent_tip1')" />
      <a-typography-paragraph :content="t('workspace.workflowSpace.run_workflow_version_inconsistent_tip2')" />
      <a-flex justify="space-between" gap="large">
        <a-button type="primary" block @click="runWorkflow('record')">
          {{ t('workspace.workflowSpace.run_record_version') }}
        </a-button>
        <a-button type="primary" block @click="runWorkflow('latest')">
          {{ t('workspace.workflowSpace.run_latest_version') }}
        </a-button>
      </a-flex>
    </a-modal>
  </a-row>
</template>

<style scoped>
.space-container {
  height: calc(100vh - 64px);
}

.main-use-container {
  padding-bottom: 60px;
}

.ui-special-item {
  margin-bottom: 24px;
}

.html-iframe {
  border: 2px solid #dedede;
  border-radius: 10px;
  width: 100%;
  min-height: 80vh;
}

.text-output-title {
  color: #005b79;
}

.human-feedback-nodes-container {
  border: 3px solid #28c5e5;
  border-radius: 10px;
  padding: 16px;
}
</style>