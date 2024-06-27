<script setup>
import { ref, reactive, watch, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { Share, LinkOne } from '@icon-park/vue-next'
import ChatMessage from '@/components/workspace/chat/ChatMessage.vue'
import CopyButton from '@/components/CopyButton.vue'
import QuestionPopover from '@/components/QuestionPopover.vue'
import { formatTime } from '@/utils/util'
import { websiteBase } from '@/utils/common'
import { conversationAPI } from '@/api/chat'

const props = defineProps({
  conversation: {
    type: Object,
    required: true,
  },
  type: {
    type: String,
    required: false,
    default: 'menuItem'
  },
  disabled: {
    type: Boolean,
    required: false,
    default: false
  }
})

const { t } = useI18n()
const loading = ref(true)
const open = ref(false)
const conversation = ref(props.conversation)
const shared = ref(props.conversation.shared)
const savedShared = ref(props.conversation.shared)
const sharedMeta = reactive({
  title: props.conversation.shared_meta?.title ?? props.conversation.title,
  update_time: props.conversation.shared_meta?.update_time || props.conversation.update_time,
  anonymous: props.conversation.shared_meta?.anonymous ?? false,
})
const isPublic = ref(props.conversation.is_public)
const savedIsPublic = ref(props.conversation.is_public)
const conversationId = ref(props.conversation.cid)
const sharedLink = computed(() => `${websiteBase}/public/shared-chat/${props.conversation.cid}`)
const messages = ref([])

watch(() => props.conversation.title, (value) => {
  sharedMeta.title = value
})
watch(() => props.conversation.shared, (value) => {
  shared.value = value
  savedShared.value = value
})
watch(() => props.conversation.is_public, (value) => {
  isPublic.value = value
  savedIsPublic.value = value
})

const openShareChatModal = async () => {
  open.value = true
  loading.value = true
  const res = await conversationAPI('get', { cid: conversationId.value })
  if (res.data.status != 200) {
    message.error(t('workspace.chatSpace.fetch_conversation_failed'))
    return
  }
  conversation.value = res.data.data.conversation
  messages.value = res.data.data.messages
  loading.value = false
}

const updating = ref(false)
const updateRecordShareState = async () => {
  updating.value = true

  // 公开的话必然是分享的，不分享的话也不会公开
  if (shared.value != savedShared.value) {
    if (!shared.value) isPublic.value = false
  }
  if (isPublic.value != savedIsPublic.value) {
    if (isPublic.value) shared.value = true
  }

  const response = await conversationAPI('update-share', {
    cid: props.conversation.cid,
    shared: shared.value,
    shared_meta: sharedMeta,
    is_public: isPublic.value,
  })
  if (response.data.status == 200) {
    conversation.value.shared_at_message = response.data.data.shared_at_message
    conversation.value.current_message = response.data.data.current_message
    savedShared.value = shared.value
    savedIsPublic.value = isPublic.value
    message.success(t('common.share_status_update_success'))
  } else {
    message.error(t('common.share_status_update_failed'))
  }
  updating.value = false
}
</script>

<template>
  <a-menu-item v-if="props.type == 'menuItem'" key="share_chat" :disabled="disabled" @click="openShareChatModal">
    <Share />
    {{ t('workspace.chatSpace.share_chat') }}
  </a-menu-item>
  <a-tooltip v-else-if="props.type == 'icon-button'" :title="t('workspace.chatSpace.share_chat')">
    <a-button type="text" :disabled="disabled" @click="openShareChatModal">
      <template #icon>
        <Share />
      </template>
    </a-button>
  </a-tooltip>
  <a-modal :open="open" width="50vw" :title="t('workspace.chatSpace.share_chat')" :footer="null" @cancel="open = false">
    <a-flex vertical gap="middle">
      <a-typography-text type="secondary">
        {{ t('workspace.chatSpace.share_chat_description') }}
      </a-typography-text>
      <div class="share-chat-preview">
        <div class="share-chat-preview-body custom-scrollbar">
          <a-spin :spinning="loading">
            <template v-for="chatMessageSection in messages" :key="chatMessageSection[0].mid">
              <ChatMessage :loading="chatMessageSection[0].loading" :cid="conversationId"
                :mid="chatMessageSection[0].mid" v-model:status="chatMessageSection[0].status"
                :authorType="chatMessageSection[0].author_type" :contentType="chatMessageSection[0].content_type"
                :createTime="chatMessageSection[0].create_time" :metadata="chatMessageSection[0].metadata"
                :content="chatMessageSection[0].content"
                :workflowInvokeStep="chatMessageSection[0].workflow_invoke_step" :showRunButton="false"
                :anonymous="sharedMeta.anonymous" />
            </template>
          </a-spin>
        </div>
        <div class="share-chat-preview-footer">
          <div>
            <a-typography-title :level="3" v-model:content="sharedMeta.title" :editable="true" />
            <a-typography-text type="secondary" :content="formatTime(sharedMeta.update_time)" />
          </div>
          <a-checkbox v-model:checked="sharedMeta.anonymous">
            {{ t('workspace.chatSpace.hide_nickname') }}
          </a-checkbox>
        </div>
      </div>
      <a-flex justify="space-between">
        <a-flex gap="large" align="center">
          <a-flex vertical gap="small">
            <a-space>
              <a-typography-text v-show="shared">
                {{ t('common.shared') }}
              </a-typography-text>
              <a-typography-text v-show="!shared">
                {{ t('common.not_shared') }}
              </a-typography-text>
              <a-switch v-model:checked="shared" :loading="updating" @change="updateRecordShareState" />
            </a-space>
            <a-typography-text type="secondary"
              v-if="conversation.shared_at_message && conversation.current_message != conversation.shared_at_message">
              {{ t('workspace.chatSpace.message_changed_after_last_share') }}
            </a-typography-text>
          </a-flex>
          <a-space>
            <a-typography-text v-show="isPublic">
              {{ t('workspace.chatSpace.share_to_community') }}
              <QuestionPopover :content="[t('workspace.chatSpace.share_to_community_brief')]" />
            </a-typography-text>
            <a-typography-text v-show="!isPublic">
              {{ t('workspace.chatSpace.not_share_to_community') }}
              <QuestionPopover :content="[t('workspace.chatSpace.share_to_community_brief')]" />
            </a-typography-text>
            <a-switch v-model:checked="isPublic" :loading="updating" @change="updateRecordShareState" />
          </a-space>
        </a-flex>
        <CopyButton :text="t('common.copy_link')" :copyText="sharedLink" :disabled="!shared">
          <template #icon>
            <LinkOne style="margin-right: 4px;" />
          </template>
        </CopyButton>
      </a-flex>
    </a-flex>
  </a-modal>
</template>

<style scoped>
.share-chat-preview {
  gap: 40px;
  background-color: #fff;
  box-shadow: 0 2px 12px 0px rgba(0, 0, 0, .08);
  border-radius: 6px;
}

.share-chat-preview-body {
  display: flex;
  flex-direction: column;
  flex: 1 1;
  overflow: auto;
  overflow-x: hidden;
  padding: 20px 20px 40px;
  position: relative;
  overscroll-behavior: none;
  height: 350px;
}

.share-chat-preview-footer {
  border-top: 1px solid #f0f0f0;
  padding: 20px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>