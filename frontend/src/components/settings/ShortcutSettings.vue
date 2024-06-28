<script setup>
import { ref, onBeforeMount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import ShortcutFormItem from '@/components/settings/ShortcutFormItem.vue'
import { agentAPI } from '@/api/chat'

const { t } = useI18n()
const shortcuts = defineModel()
const loading = ref(true)
const myAgents = ref([])
const selectedAgent = ref('')

onBeforeMount(async () => {
  loading.value = true
  const response = await agentAPI('list', { limit: null, offset: 0 })
  myAgents.value = response.data.agents
  for (const agent of myAgents.value) {
    if (!shortcuts.value[agent.aid]) {
      shortcuts.value[agent.aid] = {
        new_chat_with_agent: '',
        new_chat_with_agent_with_screenshot: '',
        continue_chat_with_agent: '',
        continue_chat_with_agent_with_screenshot: '',
      }
    }
  }
  if (myAgents.value.length > 0) {
    selectedAgent.value = myAgents.value[0].aid
  }
  loading.value = false
})

watch(shortcuts, (newVal) => {
  const keys = new Set()

  const isConflict = (key1, key2) => {
    return key1 !== key2 && (key1.includes(key2) || key2.includes(key1));
  }

  for (const aid in newVal) {
    for (const key in newVal[aid]) {
      const value = newVal[aid][key];
      if (value) {
        for (const existingKey of keys) {
          if (isConflict(value, existingKey)) {
            message.error(t('settings.shortcut_conflict', { key1: value, key2: existingKey }));
            return;
          }
        }
        keys.add(value);
      }
    }
  }
}, { deep: true })
</script>

<template>
  <a-flex v-if="loading" justify="center" align="center" style="height: 300px;">
    <a-spin />
  </a-flex>
  <template v-else>
    <a-flex v-if="myAgents.length == 0" vertical>
      <a-empty>
        <template #description>
          <a-flex vertical gap="middle">
            <a-typography-text>
              {{ t('workspace.agentSpace.no_agents_1') }}
            </a-typography-text>
            <router-link type="primary" :to="{ name: 'myAgents' }">
              {{ t('workspace.agentSpace.no_agents_2') }}
            </router-link>
          </a-flex>
        </template>
      </a-empty>
    </a-flex>
    <a-flex v-else vertical align="center" gap="large">
      <a-alert message="Tips" type="info" show-icon>
        <template #description>
          <a-typography-paragraph :content="t('settings.toggle_recording')" />
          <a-typography-paragraph :content="t('settings.recording_using_shorcut_tip')" />
        </template>
      </a-alert>
      <a-tabs v-model:activeKey="selectedAgent" tab-position="left">
        <a-tab-pane v-for="agent in myAgents" :key="agent.aid" :tab="agent.name">
          <a-form v-if="shortcuts[agent.aid]" :label-col="{ span: 12 }" :wrapper-col="{ span: 12 }">
            <ShortcutFormItem :name="t('settings.new_chat_with_agent')"
              v-model="shortcuts[agent.aid].new_chat_with_agent" />
            <ShortcutFormItem :name="t('settings.new_chat_with_agent_with_screenshot')"
              v-model="shortcuts[agent.aid].new_chat_with_agent_with_screenshot" />
            <ShortcutFormItem :name="t('settings.continue_chat_with_agent')"
              v-model="shortcuts[agent.aid].continue_chat_with_agent" />
            <ShortcutFormItem :name="t('settings.continue_chat_with_agent_with_screenshot')"
              v-model="shortcuts[agent.aid].continue_chat_with_agent_with_screenshot" />
          </a-form>
        </a-tab-pane>
      </a-tabs>
    </a-flex>
  </template>
</template>