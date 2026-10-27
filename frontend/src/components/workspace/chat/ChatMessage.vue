<script setup>
import { ref, watch, computed, nextTick, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { Share, LoadingFour, Redo, Delete, BranchTwo, Edit } from '@/icons'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useUserChatsStore } from '@/stores/userChats'
import { useUserAccountStore } from '@/stores/userAccount'
import ChatAuthor from '@/components/workspace/chat/ChatAuthor.vue'
import WorkflowRecordShow from '@/components/workspace/WorkflowRecordShow.vue'
import WorkflowFailureDetails from '@/components/workspace/WorkflowFailureDetails.vue'
import IconButton from '@/components/IconButton.vue'
import AttachmentsList from '@/components/workspace/chat/AttachmentsList.vue'
import TextOutput from '@/components/TextOutput.vue'
import { workflowAPI, workflowRunRecordAPI } from "@/api/workflow"
import { messageAPI } from '@/api/chat'
import { getWorkflowFailures, getWorkflowRunStatus, getWorkflowFailureSnapshot } from '@/utils/workflowFailures'

const props = defineProps({
  editable: { type: Boolean, default: false },
  editLoading: { type: Boolean, default: false },
  deleteLoading: { type: Boolean, default: false },
  forkable: { type: Boolean, default: false },
  forkDisabled: { type: Boolean, default: false },
  forkLoading: { type: Boolean, default: false },
  retryDisabled: { type: Boolean, default: false },
  loading: {
    type: Boolean,
    default: false,
  },
  cid: {
    type: String,
    required: true,
  },
  mid: {
    type: String,
    required: true,
  },
  status: {
    type: String,
    required: true,
  },
  authorType: {
    type: String,
    required: true,
  },
  contentType: {
    type: String,
    required: true,
  },
  createTime: {
    type: Number,
    required: true
  },
  metadata: {
    type: Object,
    required: true
  },
  content: {
    type: Object,
    required: true
  },
  workflowInvokeStep: {
    type: String,
    default: ''
  },
  expandWorkflowRecord: {
    type: Boolean,
    default: false,
  },
  showRunButton: {
    type: Boolean,
    default: true
  },
  anonymous: {
    type: Boolean,
    default: false
  },
  author: {
    type: Object,
    default: () => ({})
  },
  agent: {
    type: Object,
    default: () => ({})
  },
  workflowData: {
    type: Object,
    default: () => ({})
  },
  attachments: {
    type: Array,
    default: () => []
  },
})

const emit = defineEmits(['update:status', 'append-answer', 'regenerate', 'delete', 'fork', 'edit'])
const editing = ref(false)
const editText = ref('')
const editInput = ref(null)
const canEdit = computed(() => props.editable && props.authorType === 'U' && props.contentType === 'TXT' &&
  props.status === 'S' && typeof props.content.text === 'string' && !props.loading)
const startEditing = async () => {
  if (!canEdit.value || props.retryDisabled) return
  editText.value = props.content.text
  editing.value = true
  await nextTick()
  editInput.value?.focus()
}
const cancelEditing = () => { if (!props.editLoading) editing.value = false }
const submitEdit = () => {
  if (editing.value && canEdit.value && !props.retryDisabled && !props.editLoading &&
      editText.value.trim() && editText.value !== props.content.text) emit('edit', editText.value)
}
const canForkReply = computed(() => props.forkable && props.authorType === 'A' && !props.forkDisabled &&
  !props.forkLoading && !props.loading && !['P', 'G', 'R'].includes(props.status))
const forkReply = () => {
  if (canForkReply.value) emit('fork', props.mid)
}

const { t } = useI18n()
const router = useRouter()
const activeKey = ref([])
if (props.expandWorkflowRecord) {
  activeKey.value.push(`${props.mid}-workflow`)
}

const content = ref(props.content)
watch(() => props.content, value => { content.value = value })
const failedChat = computed(() => props.authorType === 'A' && props.status === 'F' &&
  (props.contentType !== 'WKF' || !!props.metadata?.error))
const chatError = computed(() => {
  const error = props.metadata?.error
  if (['CHAT_CONNECTION_FAILED', 'CHAT_CONNECTION_CLOSED', 'CHAT_TIMEOUT'].includes(error?.code)) {
    return t(`workspace.chatSpace.${error.code.toLowerCase()}`)
  }
  return typeof error?.message === 'string' && error.message.trim() ? error.message : t('workspace.chatSpace.chat_response_failed')
})

const userChatsStore = useUserChatsStore()
const { conversations } = storeToRefs(userChatsStore)
const conversation = conversations.value.find((item) => item.cid == props.cid)
const userAccountStore = useUserAccountStore()
const { userAccount } = storeToRefs(userAccountStore)

const author = computed(() => {
  if (props.authorType == 'U' && Object.keys(props.author).length > 0) {
    return props.author
  } else if (props.authorType == 'U' && !props.anonymous) {
    return {
      ...userAccount.value,
      type: 'U',
    }
  } else if (props.authorType == 'U' && props.anonymous) {
    return {
      nickname: t('common.me'),
      type: 'U',
    }
  } else if (props.authorType == 'A') {
    return {
      nickname: props.agent?.name ?? 'AI',
      avatar: props.agent?.avatar,
      type: 'A',
    }
  }
})
watch(
  [() => props.workflowInvokeStep, () => props.status],
  ([workflowInvokeStep, status]) => {
    if (workflowInvokeStep === 'wait_for_invoke' && status === 'W') {
      if (conversation?.settings?.auto_run_workflow) {
        runWorkflow()
      }
    }
  }
)

const runRecordId = ref(props.metadata?.record_id ?? '')
const showingRecord = ref(false)
const recordStatus = ref(props.metadata?.recordStatus || '')
const runningWorkflow = ref(false)
const checkStatusTimer = ref(null)
const workflowData = ref(props.workflowData)
const failureSnapshot = computed(() => getWorkflowFailureSnapshot(
  workflowData.value?.data, props.metadata?.workflow_result
))
const failedWorkflow = computed(() => props.contentType === 'WKF' && !failedChat.value && (recordStatus.value ? recordStatus.value === 'FAILED' :
  !runningWorkflow.value && (['Z', 'F'].includes(props.status) || getWorkflowFailures(failureSnapshot.value).length > 0)))
const displayedRecordStatus = computed(() => failedWorkflow.value ? 'FAILED' : recordStatus.value)
watch(failedWorkflow, (failed) => {
  if (failed) activeKey.value = [`${props.mid}-workflow`]
}, { immediate: true })
const checkingStatus = ref(false)
let disposed = false
let workflowEpoch = 0
let appendedRecordId = ''
const currentWorkflow = (epoch, mid, cid) => !disposed && epoch === workflowEpoch && mid === props.mid && cid === props.cid
const startPolling = () => {
  clearInterval(checkStatusTimer.value)
  checkStatusTimer.value = setInterval(pollWorkflowStatus, 1000)
}
const runWorkflow = async () => {
  if (disposed || runningWorkflow.value || ['PAUSED', 'QUEUED', 'RUNNING', 'STOPPING'].includes(recordStatus.value)) return
  const epoch = ++workflowEpoch, mid = props.mid, cid = props.cid
  checkingStatus.value = false
  runningWorkflow.value = true
  clearInterval(checkStatusTimer.value)
  recordStatus.value = ''
  workflowData.value = {}
  let submitted = false
  try {
    let response
    if (props.metadata.selected_workflow.type == 'Workflow') {
      response = await messageAPI('run_workflow', {
        mid: props.mid,
        wid: props.metadata.selected_workflow.wid,
        params: props.metadata.selected_workflow.params,
      })
    } else {
      response = await messageAPI('run_template', {
        mid: props.mid,
        tid: props.metadata.selected_workflow.tid,
        params: props.metadata.selected_workflow.params,
      })
    }

    if (!currentWorkflow(epoch, mid, cid)) return
    const newRecordId = response.data?.rid

    if (response.status == 200 && newRecordId) {
      submitted = true
      message.success(t('workspace.workflowSpace.submit_workflow_success'))
      runRecordId.value = newRecordId
      recordStatus.value = 'RUNNING'
      emit('update:status', 'R')
      startPolling()
    } else {
      message.error(t('workspace.workflowSpace.submit_workflow_failed'))
    }
  } catch {
    if (currentWorkflow(epoch, mid, cid)) message.error(t('workspace.workflowSpace.submit_workflow_failed'))
  } finally {
    if (currentWorkflow(epoch, mid, cid) && !submitted) runningWorkflow.value = false
  }
}
const pollWorkflowStatus = async () => {
  if (disposed || checkingStatus.value || !runRecordId.value) return
  const epoch = workflowEpoch, mid = props.mid, cid = props.cid, rid = runRecordId.value
  checkingStatus.value = true
  try {
    const response = await workflowAPI('check_status', { rid })
    if (!currentWorkflow(epoch, mid, cid) || rid !== runRecordId.value) return
    if (response.status === 102 && response.msg === 'PAUSED') {
      recordStatus.value = 'PAUSED'
      workflowData.value = response.data
      runningWorkflow.value = false
      showingRecord.value = true
      activeKey.value = [`${props.mid}-workflow`]
      return
    }
    if (response.status === 202) {
      recordStatus.value = response.msg
      runningWorkflow.value = response.msg !== 'PAUSED'
      workflowData.value = { ...workflowData.value, rid, status: response.msg,
        data: { ...workflowData.value?.data, ...response.data } }
      if (Array.isArray(workflowData.value.data.nodes)) {
        const finished = response.data?.finished_nodes || []
        workflowData.value.data.nodes = workflowData.value.data.nodes.map(node => finished.find(item => item.id === node.id) || node)
      }
    }
    const status = getWorkflowRunStatus(response)
    if (!status) return
    const wasActive = ['QUEUED', 'RUNNING', 'STOPPING', 'PAUSED'].includes(recordStatus.value) || props.status === 'R'
    clearInterval(checkStatusTimer.value)
    recordStatus.value = status
    workflowData.value = response.data || {}
    runRecordId.value = response.data?.rid || runRecordId.value // runRecordId 放在 workflowData 改变后改变，强迫 WorkflowRecordShow 根据新数据重新渲染
    runningWorkflow.value = false
    showingRecord.value = true
    emit('update:status', status === 'FINISHED' ? 'S' : 'Z')
    if (status === 'FAILED') activeKey.value = [`${props.mid}-workflow`]
    if (wasActive && status !== 'STOPPED') message[status === 'FAILED' ? 'error' : 'success'](t(
      `workspace.workflowSpace.${status === 'FAILED' ? 'run_workflow_failed' : 'run_workflow_success'}`
    ))
    try {
      const msgResponse = await messageAPI('get', { mid: props.mid })
      if (!currentWorkflow(epoch, mid, cid) || rid !== runRecordId.value) return
      if (msgResponse.status == 200) content.value = msgResponse.data.content
    } catch {
      if (currentWorkflow(epoch, mid, cid)) message.error(t('workspace.workflowSpace.get_workflow_record_failed'))
    }
    if (currentWorkflow(epoch, mid, cid) && rid === runRecordId.value && status === 'FINISHED' && appendedRecordId !== rid) {
      appendedRecordId = rid
      emit('append-answer', mid, rid)
    }
  } catch {
    if (currentWorkflow(epoch, mid, cid)) message.error({ key: `workflow-status-${props.mid}`,
      content: t('workspace.workflowSpace.check_workflow_status_retrying') })
  } finally {
    if (currentWorkflow(epoch, mid, cid)) checkingStatus.value = false
  }
}
onMounted(() => {
  watch([() => props.mid, () => props.cid, () => props.metadata?.record_id], () => {
    workflowEpoch++
    checkingStatus.value = false
    loadingWorkflowRecord.value = false
    clearInterval(checkStatusTimer.value)
    runRecordId.value = props.metadata?.record_id || ''
    recordStatus.value = props.metadata?.recordStatus || ''
    runningWorkflow.value = ['QUEUED', 'RUNNING', 'STOPPING'].includes(recordStatus.value) || props.status === 'R'
    if (props.contentType !== 'WKF' || props.anonymous || !runRecordId.value) return
    startPolling()
    void pollWorkflowStatus()
  }, { immediate: true })
})
const alertType = computed(() => {
  if (displayedRecordStatus.value == 'FINISHED') {
    return 'success'
  }
  else if (displayedRecordStatus.value == 'FAILED') {
    return 'error'
  }
  else {
    return 'info'
  }
})
const setWorkflowRecord = (record) => {
  if (['FINISHED', 'FAILED', 'STOPPED'].includes(recordStatus.value) && record.status !== recordStatus.value) return
  workflowData.value = record
  runRecordId.value = record.rid
  recordStatus.value = record.status
  showingRecord.value = true
}

const loadingWorkflowRecord = ref(false)
const workflowPanelChange = async (key) => {
  if (key.length > 0 && !loadingWorkflowRecord.value &&
      !Array.isArray(workflowData.value?.data?.nodes) && runRecordId.value) {
    loadingWorkflowRecord.value = true
    const epoch = workflowEpoch, mid = props.mid, cid = props.cid
    try {
      const recordRequest = await workflowRunRecordAPI('get', { rid: runRecordId.value })
      if (!currentWorkflow(epoch, mid, cid)) return
      if (recordRequest.status == 200 && recordRequest.data) {
        setWorkflowRecord(recordRequest.data)
      } else {
        message.error(t('workspace.workflowSpace.get_workflow_record_failed'))
      }
    } catch {
      if (currentWorkflow(epoch, mid, cid)) message.error(t('workspace.workflowSpace.get_workflow_record_failed'))
    } finally {
      if (currentWorkflow(epoch, mid, cid)) loadingWorkflowRecord.value = false
    }
  }
}
if (props.expandWorkflowRecord || failedWorkflow.value) workflowPanelChange(activeKey.value)

const navigateToWorkflowRecord = async () => {
  try {
    let wid = props.metadata.selected_workflow?.type === 'Workflow' ? props.metadata.selected_workflow.wid : ''
    if (!wid && runRecordId.value) {
      const response = await workflowRunRecordAPI('get', {rid: runRecordId.value})
      if (response.status !== 200) {
        message.error(response.msg || t('workspace.workflowSpace.get_workflow_record_failed'))
        return
      }
      wid = response.data.workflow?.wid
    }
    if (wid) await router.push({name:'WorkflowUse',params:{workflowId:wid},query:{rid:runRecordId.value}})
    else message.error(t('workspace.agentSpace.cant_open_template_record'))
  } catch {
    message.error(t('workspace.workflowSpace.get_workflow_record_failed'))
  }
}

const markdownRenderRef = ref()
watch(() => props.content.text, async (newVal, oldVal) => {
  if (newVal !== oldVal) {
    content.value.text = newVal
    if (!['P', 'G'].includes(props.status)) return
    let markdownEl
    try {
      markdownEl = markdownRenderRef.value.$el
    } catch (error) {
      return
    }
    await nextTick(); // 确保DOM更新
    if (!['P', 'G'].includes(props.status)) return

    // 移除之前可能存在的小黑点
    const existingDots = markdownEl.querySelectorAll('.typing-dot');
    existingDots.forEach(dot => dot.remove());

    // 获取渲染后的Markdown内容的最后一个元素
    const lastElement = markdownEl.querySelector('.markdown-body > *:last-child');
    if (lastElement) {
      // 创建小黑点元素
      const typingDot = document.createElement('span');
      typingDot.classList.add('typing-dot');
      // 将小黑点元素添加到最后一个元素中
      lastElement.appendChild(typingDot);
    } else {
      const typingDot = document.createElement('span');
      typingDot.classList.add('typing-dot');
      markdownEl.appendChild(typingDot);
    }
  }
});

watch(() => props.status, async (newVal, oldVal) => {
  if (newVal !== oldVal) {
    if (!['P', 'G'].includes(newVal)) {
      // 移除之前可能存在的小黑点
      let markdownEl
      try {
        markdownEl = markdownRenderRef.value.$el
      } catch (error) {
        return
      }
      const existingDots = markdownEl.querySelectorAll('.typing-dot');
      existingDots.forEach(dot => dot.remove());
    }
  }
})

onUnmounted(() => {
  disposed = true
  workflowEpoch++
  if (checkStatusTimer.value) {
    clearInterval(checkStatusTimer.value)
  }
})

const regenerate = () => {
  if (props.retryDisabled) return
  emit('regenerate', props.mid)
}

const deleteMessage = () => {
  if (props.retryDisabled) return
  emit('delete', props.mid)
}
</script>

<template>
  <div class="chat-message" :class="[authorType == 'U' ? 'chat-message-user' : 'chat-message-assistant', { 'chat-message-editing': editing }]">
    <div class="chat-message-container">
      <div class="chat-message-header">
        <ChatAuthor class="chat-message-author" :author="author" :time="createTime" :key="createTime" />
      </div>
      <div class="chat-message-body">
        <span class="typing-dot" v-if="loading && ['P', 'G'].includes(status)" />
        <template v-else>
          <a-collapse v-if="content?.hasOwnProperty('reasoning_content') && content.reasoning_content.length > 0"
            :bordered="false">
            <a-collapse-panel :key="`${props.mid}-reasoning`">
              <template #header>
                <a-typography-text>
                  {{ t('workspace.chatSpace.reasoning_content') }}
                  {{ content.reasoning_content.length }}
                </a-typography-text>
              </template>
              <TextOutput :text="content.reasoning_content" :showCopy="false" />
            </a-collapse-panel>
          </a-collapse>

          <div v-if="editing" class="chat-message-editor">
            <a-textarea ref="editInput" v-model:value="editText" :aria-label="t('workspace.chatSpace.edit_message')"
              :auto-size="{ minRows: 3, maxRows: 12 }" :disabled="editLoading"
              @keydown.ctrl.enter.prevent="submitEdit" @keydown.esc="cancelEditing" />
            <a-flex justify="flex-end" gap="small">
              <a-button :disabled="editLoading" @click="cancelEditing">{{ t('common.cancel') }}</a-button>
              <a-button type="primary" :loading="editLoading"
                :disabled="retryDisabled || !editText.trim() || editText === props.content.text" @click="submitEdit">
                {{ t('workspace.chatSpace.edit_and_regenerate') }}
              </a-button>
            </a-flex>
          </div>
          <template v-else-if="content?.hasOwnProperty('text')">
            <TextOutput ref="markdownRenderRef" :text="content.text" :showCopy="false" :checkFileCodeBlocks="!failedChat" />
            <span class="typing-dot" v-if="content.text.length == 0 && status == 'G'" />
          </template>
          <div v-if="failedChat" class="chat-response-error">
            <p role="alert">{{ chatError }}</p>
            <a-button size="small" :disabled="retryDisabled" @click="regenerate">{{ t('workspace.chatSpace.retry_response') }}</a-button>
          </div>
          <div v-if="authorType === 'A' && status === 'C'" class="chat-response-stopped">
            {{ t('workspace.chatSpace.stopped') }}
          </div>
          <div class="workflow-container" v-if="contentType == 'WKF' && !failedChat">
            <a-collapse v-model:activeKey="activeKey" :bordered="false" @change="workflowPanelChange">
              <a-collapse-panel :key="`${props.mid}-workflow`">

                <template #header>
                  <a-flex justify="space-between" wrap="wrap">
                    <div>
                      <a-typography-paragraph>
                        {{ t('workspace.chatSpace.use_workflow') }}
                        {{ metadata.selected_workflow?.title || '' }}
                      </a-typography-paragraph>
                      <a-typography-paragraph v-if="workflowInvokeStep == 'generating_params'">
                        <LoadingFour :spin="true" />
                        {{ t('workspace.chatSpace.generating_params') }}
                      </a-typography-paragraph>
                    </div>
                    <a-button class="run-workflow-button" type="primary" @click.stop="runWorkflow"
                      :loading="runningWorkflow" :disabled="workflowInvokeStep == 'generating_params'"
                      v-if="showRunButton">
                      <template v-if="!runningWorkflow">
                        {{ t('workspace.chatSpace.run_workflow') }}
                      </template>

                      <template v-else>
                        {{ t('workspace.chatSpace.workflow_running') }}
                      </template>
                    </a-button>
                  </a-flex>
                </template>
                <div v-if="status == 'W'">
                  <a-typography-paragraph v-for="param in Object.keys(props.metadata.selected_workflow.params)">
                    {{ param }}: {{ props.metadata.selected_workflow.params[param] }}
                  </a-typography-paragraph>
                </div>
                <a-spin v-else-if="['S', 'A', 'R', 'Z', 'F'].includes(status) || showingRecord"
                  :spinning="loadingWorkflowRecord || runningWorkflow">
                  <a-alert :type="alertType" banner="" show-icon v-if="displayedRecordStatus.length > 0">

                    <template #message>
                      <a-flex justify="space-between">
                        <div>
                          <span>
                            {{ t('workspace.workflowSpace.record_status', {
                              status:
                                t(`components.workspace.workflowRunRecordsDrawer.status_${displayedRecordStatus.toLowerCase()}`)
                            }) }}
                          </span>
                        </div>
                        <a-tooltip :title="t('workspace.chatSpace.open_workflow_record_page')">
                          <IconButton size="small" type="text" shape="round" @click="navigateToWorkflowRecord">
                            <template #icon>
                              <Share />
                            </template>
                          </IconButton>
                        </a-tooltip>
                      </a-flex>
                    </template>
                    <template v-if="displayedRecordStatus === 'PAUSED'" #description>
                      <a-button type="link" size="small" @click="navigateToWorkflowRecord">{{ t('workspace.workflowSpace.paused_workflow_action') }}</a-button>
                    </template>
                    <template v-else-if="failedWorkflow" #description>
                      <WorkflowFailureDetails :snapshot="failureSnapshot" />
                    </template>
                  </a-alert>
                  <WorkflowRecordShow class="workflow-record" :key="runRecordId" :workflowData="workflowData"
                    v-if="Array.isArray(workflowData?.data?.nodes)" />
                </a-spin>
              </a-collapse-panel>
            </a-collapse>
          </div>
        </template>
        <AttachmentsList :model-value="props.attachments" :removable="false" />
        <a-flex v-if="!editing && !loading && (content?.hasOwnProperty('text') || authorType === 'A')" class="chat-message-footer" gap="small">
          <a-typography-paragraph v-if="content?.hasOwnProperty('text')" :copyable="{ text: content.text }" />
          <a-tooltip v-if="canEdit" :title="t('workspace.chatSpace.edit_message')">
            <a-button type="text" size="small" :aria-label="t('workspace.chatSpace.edit_message')"
              :disabled="retryDisabled" @click="startEditing">
              <template #icon><Edit /></template>
            </a-button>
          </a-tooltip>
          <a-tooltip v-if="authorType === 'A' && !failedChat" :title="t('workspace.chatSpace.regenerate_message')">
            <a-button type="text" size="small" :disabled="retryDisabled" @click="regenerate">
              <template #icon><Redo fill="#28c5e5" /></template>
            </a-button>
          </a-tooltip>
          <a-tooltip v-if="forkable && authorType === 'A'" :title="t('workspace.chatSpace.fork_description')">
            <a-button type="text" size="small" :aria-label="t('workspace.chatSpace.fork_conversation')"
              :loading="forkLoading" :disabled="!canForkReply" @click="forkReply">
              <template #icon><BranchTwo fill="#28c5e5" /></template>
            </a-button>
          </a-tooltip>
          <a-tooltip :title="t('workspace.chatSpace.delete_message')">
            <a-popconfirm :title="t('workspace.chatSpace.delete_message_confirm')" :disabled="retryDisabled" @confirm="deleteMessage">
              <a-button type="text" size="small" danger :disabled="retryDisabled" :loading="deleteLoading"
                :aria-label="t('workspace.chatSpace.delete_message')">
                <template #icon><Delete v-if="!deleteLoading" /></template>
              </a-button>
            </a-popconfirm>
          </a-tooltip>
        </a-flex>
      </div>
    </div>
  </div>
</template>

<style>
.chat-message-editing .chat-message-container { width: 640px; }
.chat-message-editing .chat-message-body { width: 100%; box-sizing: border-box; }
.chat-message-editor { display: flex; flex-direction: column; gap: 10px; margin-bottom: 10px; }
.chat-response-stopped { margin-top: 8px; font-size: 12px; color: var(--site-light-text-color); }
.chat-message .chat-message-body .typing-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: black;
  margin-left: 5px;
  vertical-align: middle;
  animation: typing-dot-pulse 1.5s infinite ease-in-out both;
}

@keyframes typing-dot-pulse {

  0%,
  100% {
    transform: scale(1);
  }

  50% {
    transform: scale(1.5);
  }
}

.chat-message-container {
  max-width: 80%;
  display: flex;
  flex-direction: column;
  align-items: flex-start;
}

@media screen and (max-width: 768px) {
  .chat-message-container {
    max-width: 100%;
    margin-top: 20px;
  }
}

@keyframes last-chat-message-animation {
  0% {
    opacity: 0;
    transform: translateY(20px)
  }

  to {
    opacity: 1;
    transform: translateY(0)
  }
}

.chat-message .chat-message-header {
  width: 100%;
}

.chat-message .chat-message-header .chat-message-author {
  width: 100%;
}

.chat-message.chat-message-user .chat-message-header .chat-message-author {
  justify-content: flex-end;
}

.chat-message-container:last-child {
  animation: last-chat-message-animation .3s ease;
}

.chat-message-container .chat-message-body .markdown-body {
  line-height: 2;
  background-color: unset;
}

.chat-message-assistant .chat-message-container .chat-message-body {
  width: 100%;
  margin-top: 10px;
}

.chat-message-user .chat-message-container .chat-message-body {
  max-width: 100%;
  margin-top: 10px;
}

.chat-message-user {
  display: flex;
  flex-direction: row-reverse;
}

.chat-message-user .chat-message-container {
  align-items: flex-end;
}

.chat-message.chat-message-assistant .chat-message-body {
  padding-left: 32px;
}

.chat-message.chat-message-user .chat-message-body {
  padding-right: 32px;
}

.chat-message .chat-message-body .run-workflow-button {
  background-color: #87d068;
}

.chat-message .chat-message-body .run-workflow-button:hover {
  background-color: #b1ee97;
}

.chat-message .chat-message-body .workflow-record {
  max-width: 80vw;
}

.chat-message .chat-message-footer {
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s ease-in-out, visibility 0.3s ease-in-out;
}

.chat-message:hover .chat-message-footer {
  opacity: 1;
  visibility: visible;
}

.attachment-item {
  background-color: #f2f2f2;
  border-radius: 10px;
  padding: 16px;
  position: relative;
  margin-bottom: 8px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  align-items: center;
}

.attachment-item .a-typography-text {
  color: #333;
  margin-right: auto;
}
</style>
