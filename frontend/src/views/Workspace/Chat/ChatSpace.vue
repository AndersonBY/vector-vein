<script setup>
import { ref, reactive, onBeforeMount, onMounted, onBeforeUnmount, watch, h } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from 'vue-router'
import { Edit, More, Delete, ExpandLeft, ExpandRight } from '@icon-park/vue-next'
import { Modal, message, TypographyTitle } from 'ant-design-vue'
import { storeToRefs } from 'pinia'
import { useUserChatsStore } from '@/stores/userChats'
import { useUserAgentsStore } from '@/stores/userAgents'
import { conversationAPI } from '@/api/chat'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const loading = ref(true)
const agentId = route.params.agentId
const agentData = ref({})

const conversationsPagination = reactive({
  total: 0,
  limit: 10,
  offset: 0,
})

const userAgentsStore = useUserAgentsStore()
const userChatsStore = useUserChatsStore()
const { conversations, conversationsLength } = storeToRefs(userChatsStore)

const chatSectionsByDate = reactive({
  today: [],
  yesterday: [],
  last30Days: [],
  earlier: [],
})
const updateChatSectionsByDate = () => {
  chatSectionsByDate.today = []
  chatSectionsByDate.yesterday = []
  chatSectionsByDate.last30Days = []
  chatSectionsByDate.earlier = []
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000)
  const last30Days = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000)
  conversations.value.forEach((item) => {
    const itemDate = new Date(parseInt(item.update_time))
    if (itemDate > today) {
      chatSectionsByDate.today.push(item)
    } else if (itemDate > yesterday) {
      chatSectionsByDate.yesterday.push(item)
    } else if (itemDate > last30Days) {
      chatSectionsByDate.last30Days.push(item)
    } else {
      chatSectionsByDate.earlier.push(item)
    }
  })
  // sort chatSectionsByDate
  chatSectionsByDate.today.sort((a, b) => {
    return parseInt(b.update_time) - parseInt(a.update_time)
  })
  chatSectionsByDate.yesterday.sort((a, b) => {
    return parseInt(b.update_time) - parseInt(a.update_time)
  })
  chatSectionsByDate.last30Days.sort((a, b) => {
    return parseInt(b.update_time) - parseInt(a.update_time)
  })
  chatSectionsByDate.earlier.sort((a, b) => {
    return parseInt(b.update_time) - parseInt(a.update_time)
  })
}
onBeforeMount(async () => {
  const res = await conversationAPI('list', { aid: agentId })
  if (res.status != 200) {
    message.error(t('workspace.chatSpace.fetch_conversations_failed'))
    return
  }
  agentData.value = res.data.agent
  userAgentsStore.addAgent(agentData.value)
  conversations.value = res.data.conversations
  conversationsPagination.total = res.data.total
  conversationsPagination.limit = res.data.limit
  conversationsPagination.offset = res.data.offset + res.data.limit
  updateChatSectionsByDate()
  loading.value = false
})

watch(() => conversationsLength.value, () => {
  updateChatSectionsByDate()
})

const conversationsListRef = ref()
const loadingMore = ref(false)
onMounted(() => {
  checkScreenSize()
  window.addEventListener('resize', checkScreenSize)
  const list = conversationsListRef.value

  list.addEventListener('scroll', () => {
    if (list.scrollTop + list.clientHeight >= list.scrollHeight && !loadingMore.value && conversationsPagination.offset < conversationsPagination.total) {
      loadMore()
    }
  })
})
onBeforeUnmount(() => {
  window.removeEventListener('resize', checkScreenSize)
})

const loadMore = async () => {
  loadingMore.value = true

  const res = await conversationAPI('list', {
    aid: agentId,
    limit: conversationsPagination.limit,
    offset: conversationsPagination.offset
  })
  if (res.status != 200) {
    message.error(t('workspace.chatSpace.fetch_conversations_failed'))
    return
  }
  conversations.value.push(...res.data.conversations)
  conversationsLength.value = res.data.total
  conversationsPagination.total = res.data.total
  conversationsPagination.limit = res.data.limit
  conversationsPagination.offset = res.data.offset + res.data.limit
  updateChatSectionsByDate()
  loadingMore.value = false
}


const openChat = (cid) => {
  isConversationsListOpen.value = false
  router.push({ name: 'conversationDetail', params: { agentId: agentData.aid, conversationId: cid } })
}
const openNewChat = () => {
  isConversationsListOpen.value = false
  router.push({ name: 'conversationNew', params: { agentId: agentData.aid } })
}

const deleteChat = (chat) => {
  Modal.confirm({
    title: h(TypographyTitle, { type: 'danger', level: 3, style: { marginBottom: 0 } }, () => t('workspace.chatSpace.delete_chat_confirm_title')),
    content: t('workspace.chatSpace.delete_chat_confirm_content', { 'title': chat.title }),
    okText: t('common.yes'),
    okType: 'danger',
    cancelText: t('common.no'),
    maskClosable: true,
    async onOk() {
      const res = await conversationAPI('delete', { cid: chat.cid })
      if (res.status != 200) {
        message.error(t('workspace.chatSpace.delete_chat_failed'))
        return
      } else {
        message.success(t('workspace.chatSpace.delete_chat_success'))
        userChatsStore.deleteConversation(chat.cid)
      }
      openNewChat()
    },
    onCancel() {
    },
  })
}

// 小屏幕下功能
const isConversationsListOpen = ref(false) // 控制侧边栏是否展开
const isSmallScreen = ref(false) // 用于判断是否是小屏幕
const checkScreenSize = () => {
  isSmallScreen.value = window.innerWidth < 768;
}
</script>

<template>
  <div class="chat-space-container">
    <div class="breadcrumb-container">
      <a-button type="text" class="toggle-conversations-list-btn" :class="{ 'open': isConversationsListOpen }"
        @click="isConversationsListOpen = !isConversationsListOpen" v-if="isSmallScreen">
        <template #icon>
          <ExpandLeft v-if="!isConversationsListOpen" />
          <ExpandRight v-else />
        </template>
      </a-button>
      <a-breadcrumb>
        <a-breadcrumb-item>
          <router-link :to="{ name: 'myAgents' }">
            {{ t('workspace.agentSpace.my_agents') }}
          </router-link>
        </a-breadcrumb-item>
        <a-breadcrumb-item>
          <router-link :to="{ name: 'agentDetail', params: { agentId: agentData.aid } }">
            {{ agentData.name }}
          </router-link>
        </a-breadcrumb-item>
        <a-breadcrumb-item>{{ t('common.chat') }}</a-breadcrumb-item>
      </a-breadcrumb>
    </div>
    <div class="conversation-container">
      <div ref="conversationsListRef" class="conversations-list custom-scrollbar"
        :class="{ 'open': isConversationsListOpen }">
        <div class="new-conversation">
          <a-button type="text" size="large" class="new-conversation-button" @click="openNewChat">
            <a-typography-text style="font-size: 16px; font-weight: 600;">
              {{ t('workspace.chatSpace.new_chat') }}
            </a-typography-text>
            <Edit />
          </a-button>
        </div>
        <div>
          <a-skeleton v-if="loading" active />
          <template v-for="section in Object.keys(chatSectionsByDate)">
            <div class="conversations-section" v-if="chatSectionsByDate[section].length > 0">
              <a-typography-text class="section-title">
                {{ t(`workspace.chatSpace.${section}`) }}
              </a-typography-text>
              <a-button class="single-chat-button"
                :class="[route.params.conversationId == chat.cid ? 'chat-button-selected' : '']" type="text"
                v-for="chat in chatSectionsByDate[section]" @click="openChat(chat.cid)">
                <a-typography-text class="single-chat-button-text black-text">
                  {{ chat.title }}
                </a-typography-text>
                <a-dropdown :trigger="['click']">
                  <div class="single-chat-button-more-container">
                    <div class="single-chat-button-more">
                      <More />
                    </div>
                  </div>
                  <template #overlay>
                    <a-menu>
                      <a-menu-item key="delete" @click="deleteChat(chat)">
                        <a-typography-text type="danger">
                          <Delete />
                          {{ t('workspace.chatSpace.delete_chat') }}
                        </a-typography-text>
                      </a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
              </a-button>
            </div>
          </template>
          <a-flex justify="center">
            <a-spin v-if="loadingMore" />
          </a-flex>
        </div>
        <div class="footer-settings">
        </div>
      </div>
      <router-view></router-view>
    </div>
  </div>
</template>

<style scoped>
.chat-button-selected {
  background-color: rgba(0, 0, 0, 0.06);
}

.chat-space-container {
  width: 100vw;
  height: calc(100vh - 64px);
  padding: 20px 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 8px;
}

@media screen and (max-width: 768px) {
  .chat-space-container {
    padding: 0;
    gap: 0;
  }
}

@media screen and (min-width: 768px) {
  .chat-space-container .breadcrumb-container {
    width: 100%;
    min-width: 600px;
    max-width: 1200px;
    width: 90vw;
    display: flex;
    justify-content: flex-start;
  }
}

@media screen and (max-width: 768px) {
  .chat-space-container .breadcrumb-container {
    width: 100%;
    display: flex;
    justify-content: flex-end;
    background-color: #fff;
    padding: 10px 10px 0 10px;
  }
}

@media screen and (min-width: 768px) {
  .chat-space-container .conversation-container {
    border: 1px solid #dedede;
    border-radius: 20px;
    box-shadow: 50px 50px 100px 10px rgba(0, 0, 0, .1);
    min-width: 600px;
    min-height: 370px;
    max-width: 1200px;
    display: flex;
    overflow: hidden;
    box-sizing: border-box;
    width: 90vw;
    height: 90%;
  }
}

@media screen and (max-width: 768px) {
  .chat-space-container .conversation-container {
    display: flex;
    overflow: hidden;
    box-sizing: border-box;
    flex-grow: 1;
    width: 100vw;
  }
}

.chat-space-container .conversation-container .conversations-list {
  width: 260px;
  background-color: #d5eef9;
  overflow-y: scroll;
  padding: 0 0.75rem;
}

/* 这个样式会在小屏幕上隐藏 conversations-list */
@media screen and (max-width: 768px) {
  .chat-space-container .conversation-container .conversations-list {
    width: 0;
    height: calc(100vh - 64px);
    overflow: hidden;
    padding: 0;
    transition: width 0.3s ease;
    position: absolute;
    left: 0;
    top: 0;
    z-index: 10;
  }

  .toggle-conversations-list-btn {
    position: absolute;
    left: 0;
    top: 0;
    transition: left 0.3s ease;
    z-index: 10;
  }

  .toggle-conversations-list-btn.open {
    position: absolute;
    left: 260px;
    transition: left 0.3s ease;
  }

  /* 当侧边栏打开时的样式 */
  .chat-space-container .conversation-container .conversations-list.open {
    width: 260px;
  }
}

.chat-space-container .conversation-container .conversations-list .new-conversation {
  position: sticky;
  top: 0;
  left: 0;
  font-weight: 500;
  border-radius: 0.5rem;
  padding-top: 0.875rem;
  align-items: center;
  background-color: #d5eef9;
  z-index: 10;
}

.chat-space-container .conversation-container .conversations-list .new-conversation .new-conversation-button {
  width: 100%;
  display: flex;
  flex-direction: row;
  justify-content: space-between;
  align-items: center;
  padding: 0.8rem 0.8rem;
}

.chat-space-container .conversation-container .conversations-list .conversations-section {
  width: 100%;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  padding: 0.8rem 0;
}

.chat-space-container .conversation-container .conversations-list .conversations-section .section-title {
  color: #999999;
  padding: 4px 15px;
}

.chat-space-container .conversation-container .conversations-list .conversations-section .single-chat-button {
  font-size: 16px;
  font-weight: 600;
  display: flex;
  height: 100%;
  padding: 0.5rem;
}

.chat-space-container .conversation-container .conversations-list .conversations-section .single-chat-button-text {
  font-size: 16px;
  font-weight: 600;
  overflow: hidden;
}

.chat-space-container .conversation-container .conversations-list .conversations-section .single-chat-button-more-container {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 3.5rem;
  padding: 0 5px;
  z-index: 5;
  opacity: 0;
  background-image: linear-gradient(to left, rgb(200 224 234) 60%, rgba(0, 0, 0, 0));
  visibility: hidden;
  transition: opacity 0.3s ease-in-out, visibility 0.3s ease-in-out;
  display: flex;
  justify-content: flex-end;
}

.chat-space-container .conversation-container .conversations-list .conversations-section .single-chat-button:hover .single-chat-button-more-container {
  opacity: 1;
  visibility: visible;
}

.chat-space-container .conversation-container .conversations-list .conversations-section .single-chat-button-more {
  height: 100%;
  width: 2rem;
  display: flex;
  justify-content: center;
  align-items: center;
}

.chat-space-container .conversation-container .conversations-list .footer-settings {
  position: sticky;
  bottom: 0;
  left: 0;
  padding: 0.875rem 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  background-color: #d5eef9;
  z-index: 10;
}
</style>
