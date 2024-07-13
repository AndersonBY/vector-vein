<script setup>
import { ref, reactive, onBeforeMount, onMounted, onBeforeUnmount } from "vue"
import { useI18n } from 'vue-i18n'
import { useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import AgentCard from "@/components/workspace/agent/AgentCard.vue"
import InputSearch from "@/components/InputSearch.vue"
import { defaultSettings } from '@/utils/common'
import { officialSiteAPI } from '@/api/remote'

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
const officialAgents = ref([])

const loadAgents = async () => {
  loading.value = true
  const response = await officialSiteAPI('list_agents', {
    limit: agentsPagination.limit,
    offset: agentsPagination.offset,
  })
  officialAgents.value = [...officialAgents.value, ...response.data.agents]
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
  const response = await officialSiteAPI('list_agents', {
    limit: agentsPagination.limit,
    offset: 0,
    search: searchText.value,
  })
  officialAgents.value = response.data.agents
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
      createFormRef.value.validate()
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
      return
    }
    createAgentModal.open = false
  },
})
</script>

<template>
  <div class="main-container">
    <a-flex wrap="wrap" justify="space-between" align="flex-end">
      <a-typography-title :level="2">
        {{ t('workspace.agentSpace.public_agents') }}
      </a-typography-title>
      <div>
        <InputSearch v-model="searchText" @search="searchAgents" @clear-search="clearSearch" />
      </div>
    </a-flex>
    <a-row :gutter="[24, 24]">
      <a-col :span="24" v-if="loading" style="display: flex; justify-content: center;">
        <a-spin />
      </a-col>
      <a-col :xs="24" :md="12" :lg="8" :xl="6" v-for="agent in officialAgents" :key="agent.aid">
        <AgentCard :aid="agent.aid" :avatar="agent.avatar ? `${agent.avatar}?x-oss-process=style/thumbnail` : ''"
          :name="agent.name" :description="agent.description" :updateTime="agent.update_time"
          @click="router.push({ name: 'agentDetail', params: { agentId: agent.aid }, query: { from: 'public' } })"
          :showActions="false" :showChat="false" />
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