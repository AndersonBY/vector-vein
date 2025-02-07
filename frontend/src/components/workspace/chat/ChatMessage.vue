<script setup>
import { ref, watch, computed, nextTick, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { Share, LoadingFour, Redo, Delete } from '@icon-park/vue-next'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { useUserChatsStore } from '@/stores/userChats'
import { useUserAccountStore } from '@/stores/userAccount'
import ChatAuthor from '@/components/workspace/chat/ChatAuthor.vue'
import WorkflowRecordShow from '@/components/workspace/WorkflowRecordShow.vue'
import IconButton from '@/components/IconButton.vue'
import AttachmentsList from '@/components/workspace/chat/AttachmentsList.vue'
import TextOutput from '@/components/TextOutput.vue'
import { workflowAPI, workflowRunRecordAPI } from "@/api/workflow"
import { messageAPI } from '@/api/chat'

const props = defineProps({
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

const emit = defineEmits(['update:status', 'append-answer', 'regenerate', 'delete'])

const { t } = useI18n()
const router = useRouter()
const activeKey = ref([])
if (props.expandWorkflowRecord) {
  activeKey.value.push(`${props.mid}-workflow`)
}

const attachments = ref(props.attachments)
const content = ref(props.content)

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
      if (conversation.settings.auto_run_workflow) {
        runWorkflow()
      }
    }
  }
)

const runRecordId = ref(props.metadata?.record_id ?? '')
const showingRecord = ref(false)
const recordStatus = ref('')
const recordErrorTask = ref('')
const runningWorkflow = ref(false)
const checkStatusTimer = ref(null)
const workflowData = ref(props.workflowData)
const runWorkflow = async () => {
  let response = {}
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

  const newRecordId = response.data.rid

  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.submit_workflow_success'))
    runningWorkflow.value = true
    checkStatusTimer.value = setInterval(async () => {
      const response = await workflowAPI('check_status', { rid: newRecordId })
      if (response.status == 200) {
        message.success(t('workspace.workflowSpace.run_workflow_success'))
        clearInterval(checkStatusTimer.value)
        recordStatus.value = 'FINISHED'
        workflowData.value = response.data
        runRecordId.value = newRecordId // runRecordId 放在 workflowData 改变后改变，强迫 WorkflowRecordShow 根据新数据重新渲染
        runningWorkflow.value = false
        showingRecord.value = true
        emit('update:status', 'S')
        const msgResponse = await messageAPI('get', { mid: props.mid })
        if (msgResponse.status == 200) {
          content.value = msgResponse.data.content
        }
        activeKey.value = `${props.mid}-workflow`
        emit('append-answer', props.mid)
      } else if (response.status == 500) {
        runningWorkflow.value = false
        recordStatus.value = 'FAILED'
        message.error(t('workspace.workflowSpace.run_workflow_failed'))
        clearInterval(checkStatusTimer.value)
        setErrorTask(response.data.error_task)
      }
    }, 1000)
  } else {
    message.error(t('workspace.workflowSpace.submit_workflow_failed'))
    runningWorkflow.value = false
  }
}
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
  workflowData.value = record
  runRecordId.value = record.rid
  recordStatus.value = record.status
  setErrorTask(record.data.error_task)
  showingRecord.value = true
}

const loadingWorkflowRecord = ref(false)
const workflowPanelChange = async (key) => {
  if (key.length > 0 && Object.keys(workflowData.value).length == 0 && props.metadata?.record_id?.length > 0) {
    loadingWorkflowRecord.value = true
    const recordRequest = await workflowRunRecordAPI('get', { rid: props.metadata.record_id })
    if (recordRequest.data.status == 200) {
      setWorkflowRecord(recordRequest.data.data)
    } else {
      message.error(t('workspace.workflowSpace.get_workflow_record_failed'))
    }
    loadingWorkflowRecord.value = false
  }
}

const navigateToWorkflowRecord = () => {
  if (props.metadata.selected_workflow.type == 'Workflow') {
    router.push({ name: 'WorkflowUse', params: { workflowId: props.metadata.selected_workflow.wid }, query: { rid: runRecordId.value } })

  } else {
    message.error(t('workspace.agentSpace.cant_open_template_record'))
  }
}

const markdownRenderRef = ref()
watch(() => props.content.text, async (newVal, oldVal) => {
  if (newVal !== oldVal) {
    content.value.text = newVal
    if (props.status == 'S') return
    let markdownEl
    try {
      markdownEl = markdownRenderRef.value.$el
    } catch (error) {
      return
    }
    await nextTick(); // 确保DOM更新

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
    if (newVal == 'S') {
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
  if (checkStatusTimer.value) {
    clearInterval(checkStatusTimer.value)
  }
})

const regenerate = () => {
  emit('regenerate', props.mid)
}

const deleteMessage = () => {
  emit('delete', props.mid)
}
</script>

<template>
  <div class="chat-message" :class="[authorType == 'U' ? 'chat-message-user' : 'chat-message-assistant']">
    <div class="chat-message-container">
      <div class="chat-message-header">
        <ChatAuthor class="chat-message-author" :author="author" :time="createTime" :key="createTime" />
      </div>
      <div class="chat-message-body">
        <span class="typing-dot" v-if="loading" />
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

          <template v-if="content?.hasOwnProperty('text')">
            <TextOutput ref="markdownRenderRef" :text="content.text" :showCopy="false" :checkFileCodeBlocks="true" />
            <span class="typing-dot" v-if="content.text.length == 0 && status == 'G'" />
            <a-flex class="chat-message-footer" gap="small">
              <a-typography-paragraph :copyable="{ text: content.text }" />
              <a-tooltip v-if="props.authorType == 'A'" :title="t('workspace.chatSpace.regenerate_message')">
                <a-button type="text" size="small" @click="regenerate">
                  <template #icon>
                    <Redo fill="#28c5e5" />
                  </template>
                </a-button>
              </a-tooltip>
              <a-tooltip :title="t('workspace.chatSpace.delete_message')">
                <a-popconfirm :title="t('workspace.chatSpace.delete_message_confirm')" @confirm="deleteMessage">
                  <a-button type="text" size="small" danger>
                    <template #icon>
                      <Delete />
                    </template>
                  </a-button>
                </a-popconfirm>
              </a-tooltip>
            </a-flex>

          </template>
          <div class="workflow-container" v-if="contentType == 'WKF'">
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
                <a-spin v-else-if="status == 'S'" :spinning="loadingWorkflowRecord || runningWorkflow">
                  <a-alert :type="alertType" banner="" show-icon v-if="recordStatus.length > 0">

                    <template #message>
                      <a-flex justify="space-between">
                        <div>
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
                  </a-alert>
                  <WorkflowRecordShow class="workflow-record" :key="runRecordId" :workflowData="workflowData"
                    v-if="Object.keys(workflowData).length > 0" />
                </a-spin>
              </a-collapse-panel>
            </a-collapse>
          </div>
        </template>
        <AttachmentsList v-model="attachments" :removable="false" />
      </div>
    </div>
  </div>
</template>

<style>
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