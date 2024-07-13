<script setup>
import { ref, reactive, onBeforeMount, h, onMounted, onBeforeUnmount } from "vue"
import { useI18n } from 'vue-i18n'
import { useRouter } from "vue-router"
import { message, TypographyTitle, Modal } from 'ant-design-vue'
import { Plus } from '@icon-park/vue-next'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import AvatarUpload from '@/components/workspace/AvatarUpload.vue'
import AgentCard from "@/components/workspace/agent/AgentCard.vue"
import InputSearch from "@/components/InputSearch.vue"
import { defaultSettings } from '@/utils/common'
import { agentAPI } from '@/api/chat'

const { t } = useI18n()
const loading = ref(true)
const router = useRouter()

const userSettingsStore = useUserSettingsStore()
const { language } = storeToRefs(userSettingsStore)

const agentsPagination = reactive({
  total: 0,
  limit: 20,
  offset: 0,
})
const myAgents = ref([])

const loadAgents = async () => {
  loading.value = true
  const response = await agentAPI('list', {
    limit: agentsPagination.limit,
    offset: agentsPagination.offset,
  })
  myAgents.value = [...myAgents.value, ...response.data.agents]
  agentsPagination.total = response.data.total
  agentsPagination.limit = response.data.limit
  agentsPagination.offset = response.data.offset + response.data.limit
  loading.value = false
}
onBeforeMount(() => {
  loadAgents()
})

const loadMoreAgents = () => {
  if (loading.value || agentsPagination.offset >= agentsPagination.total) {
    return;
  }
  loadAgents();
}
const handleScroll = () => {
  const { scrollTop, clientHeight, scrollHeight } = document.documentElement;
  if (scrollHeight - scrollTop <= clientHeight * 1.5) {
    loadMoreAgents();
  }
}
onMounted(() => {
  window.addEventListener('scroll', handleScroll, { passive: true });
})
onBeforeUnmount(() => {
  window.removeEventListener('scroll', handleScroll);
})

const searchText = ref('')
const searchAgents = async () => {
  const response = await agentAPI('list', {
    limit: agentsPagination.limit,
    offset: 0,
    search: searchText.value,
  })
  myAgents.value = response.data.agents
  agentsPagination.total = response.data.total
  agentsPagination.limit = response.data.limit
  agentsPagination.offset = response.data.offset + response.data.limit
}
const clearSearch = () => {
  searchText.value = ''
  agentsPagination.offset = 0
  searchAgents()
}

const createFormRef = ref()
const createAgentModal = reactive({
  open: false,
  createLoading: false,
  createForm: {
    avatar: '',
    name: '',
    description: '',
    settings: defaultSettings[language.value],
  },
  ok: async () => {
    createAgentModal.createLoading = true
    try {
      await createFormRef.value.validate()
      const response = await agentAPI('create', createAgentModal.createForm)
      createAgentModal.createLoading = false
      if (response.status == 200) {
        message.success(t('workspace.agentSpace.create_agent_success'))
        createAgentModal.open = false
        router.push({ name: 'agentDetail', params: { agentId: response.data.aid } })
      } else {
        message.error(response.msg)
      }
    } catch (error) {
      console.error(error)
      createAgentModal.createLoading = false
      return
    }
    createAgentModal.open = false
  },
})

const agentActions = reactive({
  delete: async (agent) => {
    Modal.confirm({
      title: h(TypographyTitle, { type: 'danger', level: 3, style: { marginBottom: 0 } }, () => t('workspace.agentSpace.delete_agent_confirm_title')),
      content: t('workspace.agentSpace.delete_agent_confirm_content', { 'name': agent.name }),
      okText: t('common.yes'),
      okType: 'danger',
      cancelText: t('common.no'),
      maskClosable: true,
      async onOk() {
        const response = await agentAPI('delete', { aid: agent.aid })
        if (response.status == 200) {
          message.success(t('workspace.agentSpace.delete_agent_success'))
          myAgents.value = myAgents.value.filter((item) => item.aid != agent.aid)
        } else {
          message.error(response.msg)
        }
      },
      onCancel() {
      },
    })
  },
  duplicate: async (aid) => {
    const response = await agentAPI('duplicate', { aid })
    if (response.status == 200) {
      message.success(t('workspace.agentSpace.duplicate_agent_success'))
      myAgents.value.unshift(response.data)
    } else {
      message.error(response.msg)
    }
  },
})
</script>

<template>
  <div class="main-container">
    <a-flex class="header" wrap="wrap" justify="space-between" align="flex-end">
      <a-typography-title :level="2">
        {{ t('workspace.agentSpace.my_agents') }}
      </a-typography-title>
      <a-space>
        <InputSearch v-model="searchText" @search="searchAgents" @clear-search="clearSearch" />
        <a-button type="primary" @click="createAgentModal.open = true">
          <template #icon>
            <Plus theme="filled" />
          </template>
          {{ t('workspace.agentSpace.create_agent') }}
        </a-button>
        <a-modal :title="t('workspace.agentSpace.create_agent')" @ok="createAgentModal.ok"
          :confirm-loading="createAgentModal.createLoading" v-model:open="createAgentModal.open">
          <a-flex justify="center" style="margin: 24px 0;">
            <AvatarUpload v-model="createAgentModal.createForm.avatar" />
          </a-flex>
          <a-form ref="createFormRef" :model="createAgentModal.createForm" layout="vertical">
            <a-form-item :label="t('workspace.agentSpace.agent_name')" name="name"
              :rules="[{ required: true, message: t('workspace.agentSpace.agent_name_required') }]">
              <a-input v-model:value="createAgentModal.createForm.name"
                :placeholder="t('workspace.agentSpace.agent_name_placeholder')" />
            </a-form-item>
            <a-form-item :label="t('workspace.agentSpace.agent_description')" name="description">
              <a-textarea :autoSize="{ minRows: 3, maxRows: 10 }"
                v-model:value="createAgentModal.createForm.description"
                :placeholder="t('workspace.agentSpace.agent_description_placeholder')" />
            </a-form-item>
          </a-form>
        </a-modal>
      </a-space>
    </a-flex>
    <a-row :gutter="[24, 24]">
      <a-col :span="24" v-if="loading" style="display: flex; justify-content: center;">
        <a-spin />
      </a-col>
      <a-col :span="24" v-else-if="myAgents.length == 0">
        <a-flex vertical gap="middle" align="center">
          <a-typography-paragraph type="secondary">
            {{ t('workspace.agentSpace.no_agents_1') }}
          </a-typography-paragraph>
          <a-typography-paragraph type="secondary">
            {{ t('workspace.agentSpace.no_agents_2') }}
          </a-typography-paragraph>
          <router-link :to="{ name: 'publicAgents' }">
            {{ t('workspace.agentSpace.public_agents') }}
          </router-link>
        </a-flex>
      </a-col>
      <a-col :xs="24" :md="12" :lg="8" :xl="6" v-for="agent in myAgents" :key="agent.aid">
        <AgentCard :aid="agent.aid" :avatar="agent.avatar" :name="agent.name" :description="agent.description"
          :updateTime="agent.update_time" :shared="agent.shared" :isPublic="agent.is_public"
          @click="router.push({ name: 'agentDetail', params: { agentId: agent.aid } })"
          @delete="agentActions.delete(agent)" @duplicate="agentActions.duplicate(agent.aid)" />
      </a-col>
    </a-row>
    <a-flex justify="center">
      <a-button :loading="loading" v-if="agentsPagination.offset < agentsPagination.total" @click="loadAgents">
        {{ t('common.load_more') }}
      </a-button>
    </a-flex>
  </div>
</template>

<style scoped>
.main-container {
  background-color: var(--component-background);
  padding: 24px;
}
</style>