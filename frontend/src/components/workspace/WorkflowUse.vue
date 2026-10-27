<script setup>
import { onBeforeMount, onBeforeUnmount, ref, reactive, computed } from "vue"
import { useRouter } from "vue-router"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { FullScreenOne, OffScreenOne, Edit, Lightning, Dot, PlayOne, Eeg } from '@/icons'
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
import WorkflowRunTimeline from "@/components/workspace/WorkflowRunTimeline.vue"
import WorkflowRunArtifacts from "@/components/workspace/WorkflowRunArtifacts.vue"
import WorkflowRecordStatusAlert from "@/components/workspace/WorkflowRecordStatusAlert.vue"
import TextOutput from "@/components/TextOutput.vue"
import HtmlPreview from "@/components/HtmlPreview.vue"
import {
  hasShowFields,
  checkFieldsValid,
  nonFormItemsTypes,
  getNodeConnectedNodes,
  getUIDesignFromWorkflow,
} from '@/utils/workflow'
import { deepCopy, formatTime } from '@/utils/util'
import { settingAPI } from '@/api/user'
import { workflowAPI, workflowRunRecordAPI, workflowScheduleTriggerAPI } from '@/api/workflow'
import { databaseAPI, relationalDatabaseAPI } from "@/api/database"
import { getWorkflowRunStatus } from '@/utils/workflowFailures'
import { findHttpRequestError } from '@/components/nodes/tools/_httpRequestShared.js'

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
const scheduleInfo = ref(null)
const scheduleLoading = ref(false)

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

  if (!props.isTemplate && currentWorkflow.value?.wid) {
    await loadScheduleInfo(currentWorkflow.value.wid)
  }

  loading.value = false
})
onBeforeUnmount(() => {
  stopStatusPolling()
})

const wsPort = ref(null)

let pollEpoch = 0
const runSockets = new Set()
const timelineSnapshot = ref({})
const timelineFresh = ref(false)
const artifactsRevision = ref(0)
const showTimeline = ref(false)
function stopStatusPolling() {
  pollEpoch += 1
  runSockets.forEach(socket => socket.close())
  runSockets.clear()
  clearInterval(checkStatusTimer.value)
  checkStatusTimer.value = null
  checkingStatus.value = false
}
function startStatusPolling() {
  clearInterval(checkStatusTimer.value)
  checkStatusTimer.value = setInterval(checkWorkflowRunningStatus, 1000)
}
const checkingStatus = ref(false)
const checkWorkflowRunningStatus = async () => {
  if (checkingStatus.value) {
    return
  }
  checkingStatus.value = true
  const epoch = pollEpoch
  const rid = runRecordId.value
  try {
    const statusResponse = await workflowAPI('check_status', { rid })
    if (epoch !== pollEpoch || rid !== runRecordId.value) return
    artifactsRevision.value++
    const snapshot = statusResponse.status === 202 ? statusResponse.data : statusResponse.data?.data
    if (snapshot) {
      timelineFresh.value = false
      timelineSnapshot.value = { ...timelineSnapshot.value, ...snapshot, nodes: snapshot.nodes || timelineSnapshot.value.nodes }
      if (statusResponse.status === 202 && snapshot.finished_nodes) {
        timelineSnapshot.value.nodes = timelineSnapshot.value.nodes.map(node => snapshot.finished_nodes.find(item => item.id === node.id) || node)
      }
    }
    if (['FINISHED', 'STOPPED'].includes(getWorkflowRunStatus(statusResponse))) {
      if (getWorkflowRunStatus(statusResponse) === 'FINISHED') message.success(t('workspace.workflowSpace.run_workflow_success'))
      clearInterval(checkStatusTimer.value)
      running.value = false
      recordStatus.value = getWorkflowRunStatus(statusResponse)
      stopStatusPolling()
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

    } else if (statusResponse.status === 102 && statusResponse.msg === 'PAUSED') {
      recordStatus.value = 'PAUSED'
      running.value = false
      showingRecord.value = true
      currentWorkflow.value = statusResponse.data
      currentWorkflow.value.data.ui = savedWorkflow.value.data?.ui || {}
      await loadPendingFeedbackRuns(currentWorkflow.value.data, epoch, rid)
      if (epoch !== pollEpoch || rid !== runRecordId.value) return
      const uiDesign = currentWorkflow.value.data.ui_design
      if (uiDesign) outputNodes.value = uiDesign.output_nodes || outputNodes.value
      else outputNodes.value.forEach(node => {
        const updated = currentWorkflow.value.data.nodes?.find(item => item.id === node.id)
        if (updated) node.data = updated.data
      })
    } else if (statusResponse.status == 202) {
      running.value = true
      recordStatus.value = ['RUNNING', 'QUEUED', 'STOPPING'].includes(statusResponse.msg) ? statusResponse.msg : 'RUNNING'
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
            const connectedOutputNodes = getNodeConnectedNodes(node.id, 'output', edges.value)
            // 找出 connectedNodes 中在 outputNodes 中且是 Text 的Type的节点，获取 node 对象
            const outputTextNodeIds = connectedOutputNodes.filter((item) => {
              return outputNodes.value.some((outputNode) => outputNode.id == item && outputNode.type == 'Text')
            })
            const outputTextNodes = outputNodes.value.filter((item) => outputTextNodeIds.includes(item.id))
            outputTextNodes.forEach((textNode) => {
              textNode.data.template.text.value = ''
              textNode.finished = true
            })

            const connectedReasoningContentNodes = getNodeConnectedNodes(node.id, 'reasoning_content', edges.value)
            const reasoningContentNodes = outputNodes.value.filter((item) => connectedReasoningContentNodes.includes(item.id))
            reasoningContentNodes.forEach((reasoningContentNode) => {
              reasoningContentNode.data.template.text.value = ''
              reasoningContentNode.finished = true
            })

            if (wsPort.value === null) {
              const res = await settingAPI('get_port', { port_name: 'chat_ws_port' })
              wsPort.value = res.data.port
            }

            if (epoch !== pollEpoch || rid !== runRecordId.value) return
            const chatSocket = new ReconnectingWebSocket(
              `ws://localhost:${wsPort.value}/ws/workflow_node/${rid}_${node.id}`,
              null,
              { maxReconnectAttempts: 5 }
            );
            runSockets.add(chatSocket)

            chatSocket.onopen = () => {
              chatSocket.send('start')
              console.log('连接成功')
            }
            chatSocket.onmessage = async (e) => {
              if (epoch !== pollEpoch || rid !== runRecordId.value) {
                chatSocket.close()
                runSockets.delete(chatSocket)
                return
              }
              const data = JSON.parse(e.data)
              if (data.end) {
                chatSocket.close()
                runSockets.delete(chatSocket)
                return
              }
              outputTextNodes.forEach((outputTextNode) => {
                outputTextNode.data.template.text.value += data.content ?? ''
              });
              reasoningContentNodes.forEach((reasoningContentNode) => {
                reasoningContentNode.data.template.text.value += data.reasoning_content ?? ''
              });
            }
          }
        }
      })
    } else if (getWorkflowRunStatus(statusResponse) === 'FAILED') {
      running.value = false
      recordStatus.value = 'FAILED'
      clearInterval(checkStatusTimer.value)
      if (Array.isArray(statusResponse.data?.data?.nodes)) {
        currentWorkflow.value = statusResponse.data
      } else {
        currentWorkflow.value.data = {
          ...currentWorkflow.value.data,
          failures: statusResponse.data?.data?.failures,
          error_task: statusResponse.data?.data?.error_task,
        }
      }
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
      showingRecord.value = true
    }
  } catch {
    if (epoch !== pollEpoch || rid !== runRecordId.value) return
    message.error({ key: 'workflow-status', content: t('workspace.workflowSpace.check_workflow_status_retrying') })
  } finally {
    if (epoch === pollEpoch) checkingStatus.value = false
  }
}

const runWorkflowVersionModal = ref(false)

const running = ref(false)
const checkStatusTimer = ref(null)
const runRecordId = ref(null)
const stopRequest = ref(null)
const stopWorkflow = async () => {
  if (!runRecordId.value || !['QUEUED', 'RUNNING', 'PAUSED'].includes(recordStatus.value) || stopRequest.value === runRecordId.value || resumeRequest.value === runRecordId.value) return
  const rid = runRecordId.value
  const epoch = pollEpoch
  stopRequest.value = rid
  try {
    const response = await workflowRunRecordAPI('stop', { rid })
    if (epoch !== pollEpoch || rid !== runRecordId.value) return
    if (response.status !== 200) {
      message.error(response.msg || t('workspace.workflowSpace.stop_workflow_failed'))
      return
    }
    recordStatus.value = response.data.status
    await checkWorkflowRunningStatus()
  } catch {
    if (epoch === pollEpoch && rid === runRecordId.value) message.error(t('workspace.workflowSpace.stop_workflow_failed'))
  } finally {
    if (stopRequest.value === rid) stopRequest.value = null
  }
}
const feedbackDrafts = reactive({})
const feedbackRunRecords = ref([])
const resumeRequest = ref(null)
const activeRun = computed(() => ['QUEUED', 'RUNNING', 'PAUSED', 'STOPPING'].includes(recordStatus.value))
const pendingFeedbackNodes = computed(() => {
  if (recordStatus.value !== 'PAUSED') return []
  return [{rid: runRecordId.value, data: currentWorkflow.value.data}, ...feedbackRunRecords.value].flatMap(record => {
    const ids = record.data?.pending_feedback_nodes || []
    return (record.data?.nodes || []).filter(node => node.type === 'HumanFeedback' && ids.includes(node.id)).map(node => ({
      ...node, feedbackRid: record.rid, draftKey: record.rid === runRecordId.value ? node.id : `${record.rid}:${node.id}`,
    }))
  })
})
const loadPendingFeedbackRuns = async (snapshot, epoch, rid) => {
  const records = []
  const load = async data => {
    for (const childRid of data?.pending_feedback_runs || []) {
      if (records.some(record => record.rid === childRid) || childRid === rid) continue
      const response = await workflowRunRecordAPI('get', {rid: childRid})
      if (epoch !== pollEpoch || rid !== runRecordId.value) return
      if (response.status === 200) {
        records.push(response.data)
        await load(response.data.data)
      }
    }
  }
  await load(snapshot)
  if (epoch === pollEpoch && rid === runRecordId.value) feedbackRunRecords.value = records
}
const feedbackReadyRuns = computed(() => {
  if (recordStatus.value !== 'PAUSED') return []
  return [{rid:runRecordId.value,data:currentWorkflow.value.data}, ...feedbackRunRecords.value]
    .filter(record => record.data?.feedback_resume_ready).map(record => record.rid)
})
const canContinue = computed(() => pendingFeedbackNodes.value.length > 0 || feedbackReadyRuns.value.length > 0)
const resumeWorkflow = async () => {
  const rid = runRecordId.value
  if (recordStatus.value !== 'PAUSED' || !rid || resumeRequest.value === rid || stopRequest.value === rid || !canContinue.value) return
  const feedback = pendingFeedbackNodes.value.map(node => ({node_id: node.id, rid: node.feedbackRid, draftKey: node.draftKey, content: feedbackDrafts[node.draftKey] || ''}))
  if (feedback.some(node => !node.content.trim())) {
    message.error(t('workspace.workflowSpace.human_feedback_required'))
    return
  }
  const epoch = pollEpoch
  resumeRequest.value = rid
  try {
    for (const feedbackRid of new Set([...feedback.map(node => node.rid), ...feedbackReadyRuns.value])) {
      const nodes = feedback.filter(node => node.rid === feedbackRid)
      const response = await workflowAPI('resume', {rid: feedbackRid, human_feedback_nodes: nodes.map(node => ({node_id: node.node_id, content: node.content}))})
      if (epoch !== pollEpoch || rid !== runRecordId.value) return
      if (response.status !== 200) {
        message.error(response.msg || t('workspace.workflowSpace.resume_workflow_failed'))
        return
      }
      nodes.forEach(node => { delete feedbackDrafts[node.draftKey] })
      if (feedbackRid === rid) {
        recordStatus.value = response.data.status
        running.value = ['QUEUED', 'RUNNING', 'STOPPING'].includes(recordStatus.value)
      }
    }
    stopStatusPolling()
    startStatusPolling()
    await checkWorkflowRunningStatus()
  } catch {
    if (epoch === pollEpoch && rid === runRecordId.value) message.error(t('workspace.workflowSpace.resume_workflow_failed'))
  } finally {
    if (resumeRequest.value === rid) resumeRequest.value = null
  }
}
const hasButtonTrigger = computed(() => triggerNodes.value.some((node) => node.type === 'ButtonTrigger'))
const hasScheduleTrigger = computed(() => triggerNodes.value.some((node) => node.type === 'ScheduleTrigger'))
const scheduleSummary = computed(() => {
  if (!scheduleInfo.value) {
    return t('workspace.workflowSpace.schedule_not_configured')
  }
  const items = [
    `${t('workspace.workflowSpace.schedule_expression')}: ${scheduleInfo.value.cron_expression || '-'}`,
  ]
  if (scheduleInfo.value.next_run_display) {
    items.push(`${t('workspace.workflowSpace.schedule_next_run')}: ${scheduleInfo.value.next_run_display}`)
  }
  if (scheduleInfo.value.last_run_display) {
    items.push(`${t('workspace.workflowSpace.schedule_last_run')}: ${scheduleInfo.value.last_run_display}`)
  }
  return items.join(' · ')
})

const loadScheduleInfo = async (wid) => {
  scheduleLoading.value = true
  const response = await workflowScheduleTriggerAPI('get', { wid })
  if (response.status === 200) {
    scheduleInfo.value = {
      ...response.data,
      next_run_display: response.data?.next_run_at ? formatTime(response.data.next_run_at) : '',
      last_run_display: response.data?.latest_record?.start_time ? formatTime(response.data.latest_record.start_time) : '',
    }
  } else if (response.status === 404) {
    scheduleInfo.value = null
  }
  scheduleLoading.value = false
}

const openScheduleManager = async () => {
  await router.push({
    name: 'WorkflowScheduleManager',
    query: currentWorkflow.value?.wid ? { wid: currentWorkflow.value.wid } : {},
  })
}

const runWorkflow = async (workflowVersion = null) => {
  if (running.value || activeRun.value) return
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
  const httpError = findHttpRequestError(workflowDataForRun.data)
  if (httpError) {
    const prefix = 'components.nodes.tools.HttpRequest'
    message.error(`${httpError.node.data.title || t(`${prefix}.title`)} · ${t(`${prefix}.${httpError.field}`)}: ${t(`${prefix}.${httpError.error}`)}`)
    return
  }
  outputNodes.value.forEach((node) => {
    const definition = workflowDataForRun.data.nodes.find(item => item.id === node.id)
    if (definition) node.data = deepCopy(definition.data)
    node.finished = false
  })
  stopStatusPolling()
  const epoch = pollEpoch
  Object.keys(feedbackDrafts).forEach(id => { delete feedbackDrafts[id] })
  runRecordId.value = null
  recordStatus.value = 'QUEUED'
  showingRecord.value = false
  showTimeline.value = false
  streamableNodes.value = []
  timelineFresh.value = true
  timelineSnapshot.value = { nodes: deepCopy(workflowDataForRun.data.nodes).map(node => {
    delete node.run_time
    if (node.data) {
      delete node.data.status
      delete node.data.debug
    }
    return node
  }) }
  running.value = true
  try {
    const response = await workflowAPI(props.isTemplate ? 'run-template' : 'run', workflowDataForRun)
    if (epoch !== pollEpoch) return
    if (response.status == 200 && response.data?.rid) {
      message.success(t('workspace.workflowSpace.submit_workflow_success'))
      runRecordId.value = response.data.rid
      showingRecord.value = true
      startStatusPolling()
    } else {
      message.error(t('workspace.workflowSpace.submit_workflow_failed'))
    }
  } catch {
    if (epoch !== pollEpoch) return
    message.error(t('workspace.workflowSpace.submit_workflow_failed'))
  } finally {
    if (epoch === pollEpoch && !runRecordId.value) running.value = false
  }
}

const showingRecord = ref(false)
const recordStatus = ref('')

function setWorkflowRecord(record) {
  if (record.rid !== runRecordId.value) Object.keys(feedbackDrafts).forEach(id => { delete feedbackDrafts[id] })
  feedbackRunRecords.value = []
  stopStatusPolling()
  artifactsRevision.value++
  showTimeline.value = false
  running.value = false
  timelineFresh.value = false
  timelineSnapshot.value = { ...record.data, nodes: Array.isArray(record.data?.nodes) ? record.data.nodes : deepCopy(savedWorkflow.value.data.nodes) }
  runRecordId.value = record.rid
  recordStatus.value = record.status
  if (['RUNNING', 'QUEUED', 'STOPPING', 'PAUSED'].includes(record.status)) {
    running.value = record.status !== 'PAUSED'
    startStatusPolling()
  }
  currentWorkflow.value.data = {
    ...record.data,
    nodes: Array.isArray(record.data?.nodes) ? record.data.nodes : savedWorkflow.value.data.nodes,
    ui: savedWorkflow.value.data?.ui || {}
  }
  currentWorkflow.value.shared = record.shared
  currentWorkflow.value.is_public = record.is_public
  currentWorkflow.value.public_shared_record = record.public_shared_record
  currentWorkflow.value.version = record.workflow_version
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
  stopStatusPolling()
  showTimeline.value = false
  running.value = false
  showingRecord.value = false
  runRecordId.value = null
  recordStatus.value = ''
  timelineSnapshot.value = {}
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
        :closable="!activeRun"
        :recordWorkflowVersion="currentWorkflow.version" :status="recordStatus" :snapshot="currentWorkflow.data"
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
          <a-card v-if="hasScheduleTrigger" size="small" class="schedule-overview-card" :loading="scheduleLoading">
            <a-flex justify="space-between" align="start" gap="middle">
              <div>
                <a-typography-text strong>
                  {{ t('workspace.workflowSpace.schedule_overview') }}
                </a-typography-text>
                <a-typography-paragraph type="secondary" style="margin: 8px 0 0;">
                  {{ scheduleSummary }}
                </a-typography-paragraph>
              </div>
              <a-button size="small" @click="openScheduleManager">
                {{ t('workspace.workflowSpace.manage_schedule') }}
              </a-button>
            </a-flex>
          </a-card>

          <a-flex v-if="pendingFeedbackNodes.length > 0" vertical gap="small">
            <a-typography-title :level="5" style="margin-bottom: 0;">
              {{ t('components.workspace.workflowRunRecordsDrawer.status_paused') }}
            </a-typography-title>
            <a-card v-for="node in pendingFeedbackNodes" :key="node.draftKey" size="small">
              <a-typography-text strong>{{ node.data?.title || t('components.nodes.controlFlows.HumanFeedback.title') }}</a-typography-text>
              <a-typography-paragraph v-if="node.data?.template?.hint_message?.value" type="secondary">
                {{ node.data.template.hint_message.value }}
              </a-typography-paragraph>
              <a-textarea v-model:value="feedbackDrafts[node.draftKey]" :aria-label="node.data?.title || t('components.nodes.controlFlows.HumanFeedback.title')" :disabled="resumeRequest === runRecordId || stopRequest === runRecordId"
                :autoSize="{ minRows: 3, maxRows: 10 }"
                :placeholder="t('workspace.workflowSpace.human_feedback_placeholder')" />
            </a-card>
          </a-flex>

          <a-button v-if="canContinue" type="primary" block :loading="resumeRequest === runRecordId" :disabled="stopRequest === runRecordId" @click="resumeWorkflow">
            {{ t('workspace.workflowSpace.continue_workflow') }}
          </a-button>
          <a-button v-if="activeRun && runRecordId" danger block :loading="stopRequest === runRecordId"
            :disabled="recordStatus === 'STOPPING' || resumeRequest === runRecordId" @click="stopWorkflow">
            {{ t(recordStatus === 'STOPPING' ? 'components.workspace.workflowRunRecordsDrawer.status_stopping' : 'workspace.workflowSpace.stop_workflow') }}
          </a-button>
          <template v-for="(node) in triggerNodes" :key="`node-${node.id}`">
            <a-button type="primary" block @click="runWorkflow(null)" :loading="running"
              v-if="node.type == 'ButtonTrigger' && !(activeRun && runRecordId)">
              <template #icon>
                <PlayOne />
              </template>
              {{ node.data.template.button_text.value }}
            </a-button>
          </template>
          <a-button v-if="!hasButtonTrigger && !(activeRun && runRecordId)" type="primary" ghost block @click="runWorkflow(null)" :loading="running">
            <template #icon>
              <PlayOne />
            </template>
            {{ t('workspace.workflowSpace.run_once') }}
          </a-button>
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
          <a-button v-if="running || showingRecord" type="text" size="small" :aria-pressed="showTimeline"
            @click="showTimeline = !showTimeline">
            {{ t(showTimeline ? 'workspace.workflowSpace.hide_debug_details' : 'workspace.workflowSpace.show_debug_details') }}
          </a-button>
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
      <WorkflowRunTimeline v-if="showTimeline && (running || showingRecord)" :snapshot="timelineSnapshot" :active="running" :status="recordStatus" :fresh="timelineFresh" />
      <a-flex vertical gap="small">
        <a-spin :spinning="running && !['Document', 'Html'].includes(node.type) && !node.finished && node.field_type != 'typography-paragraph'"
          v-show="node.type !== 'Document' || !Array.isArray(node.data?.artifacts) || !node.data.artifacts.some(artifact => artifact?.path === node.data.template?.output?.value)"
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
            <HtmlPreview :url="node.data.template.output.value" :title="node.data.title || ''" :pending="running && !node.finished" />
          </div>

          <div v-else>
            <div v-if="node.field_type == 'typography-paragraph'">
              <TextOutput :text="node.value" :showCopy="false" class="ui-special-item" />
            </div>
          </div>
        </a-spin>
      </a-flex>
      <WorkflowRunArtifacts v-if="runRecordId && (running || showingRecord)" :rid="runRecordId" :revision="artifactsRevision" :status="recordStatus" />
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

.text-output-title {
  color: #005b79;
}



.schedule-overview-card {
  border-radius: 14px;
}
</style>
