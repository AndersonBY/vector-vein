<script setup>
import { useI18n } from 'vue-i18n'
import { RobotOne } from '@icon-park/vue-next'
import { useRouter } from "vue-router"
import ModelTag from '@/components/workspace/chat/ModelTag.vue'
import { formatTime } from '@/utils/util'
import logoUrl from "@/assets/logo.svg"

const props = defineProps({
  cid: {
    type: String,
    default: '',
  },
  agent: {
    type: Object,
    default: () => ({}),
  },
  title: {
    type: String,
    default: '',
  },
  sharedMeta: {
    type: Object,
    default: () => ({}),
  },
  model: {
    type: String,
    default: '',
  },
  updateTime: {
    type: [String, Number],
    default: '',
  },
})

const { t } = useI18n()
const router = useRouter()
</script>

<template>
  <div class="agent-card">
    <div class="card-body">
      <img :src="agent.avatar ? `${agent.avatar}` : logoUrl" alt="avatar"
        class="avatar" />
      <div class="info">
        <div class="head">
          <h3 class="title">{{ title }}</h3>
        </div>
        <a-typography-paragraph class="description" :content="sharedMeta?.first_message?.content?.text ?? ''"
          :ellipsis="{ rows: 2, tooltip: true }" />
        <a-flex justify="flex-end">
          <a-tooltip :title="agent.shared ? agent.description : t('workspace.agentSpace.not_shared_agent')">
            <a-button type="text" :disabled="!agent.shared"
              @click.stop="router.push({ name: 'agentDetail', params: { agentId: agent.aid } })">
              <template #icon>
                <RobotOne style="margin-inline-end: 3px;" />
              </template>
              {{ agent.name }}
            </a-button>
          </a-tooltip>
        </a-flex>
      </div>
    </div>
    <a-divider style="margin: 16px 0;" />
    <div class="card-footer">
      <span class="model">
        <ModelTag :model=model />
      </span>
      <span class="time">{{ formatTime(updateTime) }}</span>
    </div>
  </div>
</template>

<style scoped>
.agent-card {
  background-color: white;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  padding: 16px;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  height: 100%;
  display: flex;
  flex-direction: column;
}

.agent-card:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.card-body {
  display: flex;
  align-items: center;
  flex-grow: 1;
}

.info {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  gap: 2px;
  flex-grow: 1;
}

.info .head {
  display: flex;
  justify-content: space-between;
}

.info .head .more {
  cursor: pointer;
}

.info .head .more:hover {
  background-color: #f5f5f5;
}

.avatar {
  width: 70px;
  height: 70px;
  border-radius: 8px;
  margin-right: 10px;
  object-fit: cover;
}

.title {
  margin: 0;
}

.description {
  color: #1c2223cc;
  font-size: 14px;
  line-height: 20px;
  margin-bottom: 0;
}

.more-options {
  margin-left: auto;
  /* Add more styling for the more options */
}

.card-footer {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  padding-top: 10px;
  color: #1c212359;
}

.footer-hover-container {
  display: flex;
  justify-content: flex-start;
  gap: 8px;
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  padding: 16px;
  transition: transform 0.3s ease-in-out;
  transform: translateY(100%);
}

.agent-card:hover .footer-hover-container {
  transform: translateY(0);
}
</style>