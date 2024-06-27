<script setup>
import { useI18n } from 'vue-i18n'
import { More } from '@icon-park/vue-next'
import { useRouter } from "vue-router"
import { formatTime } from '@/utils/util'
import logoUrl from "@/assets/logo.svg"

const props = defineProps({
  aid: {
    type: String,
    default: '',
  },
  avatar: {
    type: String,
    default: '',
  },
  name: {
    type: String,
    default: '',
  },
  description: {
    type: String,
    default: '',
  },
  updateTime: {
    type: [String, Number],
    default: '',
  },
  shared: {
    type: [null, Boolean],
    default: null,
  },
  isPublic: {
    type: [null, Boolean],
    default: null,
  },
  showActions: {
    type: Boolean,
    default: true,
  },
  showChat: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['delete', 'duplicate'])

const { t } = useI18n()
const router = useRouter()
</script>

<template>
  <div class="agent-card">
    <div class="card-body">
      <img :src="avatar ? avatar : logoUrl" alt="avatar" class="avatar" />
      <div class="info">
        <div class="head">
          <h3 class="name">{{ name }}</h3>
          <a-dropdown v-if="showActions">
            <More size="24" class="more" @click.stop />
            <template #overlay>
              <a-menu>
                <a-menu-item>
                  <a-typography-text @click="emit('duplicate')">
                    {{ t('common.duplicate') }}
                  </a-typography-text>
                </a-menu-item>
                <a-menu-item>
                  <a-typography-text type="danger" @click="emit('delete')">
                    {{ t('common.delete') }}
                  </a-typography-text>
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
        </div>
        <a-typography-paragraph class="description" :content="description" :ellipsis="{ rows: 2, tooltip: true }" />
      </div>
    </div>
    <a-divider style="margin: 16px 0;" />
    <div class="card-footer">
      <span class="tag">
      </span>
      <span class="time">{{ formatTime(updateTime) }}</span>
    </div>
    <div v-if="showChat" class="card-footer footer-hover-container">
      <a-button type="primary" @click.stop="router.push({ name: 'conversationNew', params: { agentId: aid } })">
        {{ t('workspace.agentSpace.chat_with_agent') }}
      </a-button>
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

.name {
  margin: 0;
  font-weight: bold;
}

.description {
  color: #1c2223cc;
  font-size: 14px;
  line-height: 20px;
}

.more-options {
  margin-left: auto;
}

.card-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  color: #1c212359;
  height: 28px;
}

.tag {
  line-height: 2;
}

.tag-status-false {
  background-color: #2db7f5;
  color: #fff;
}

.tag-status-true {
  background-color: #87d068;
  color: #fff;
}

.footer-hover-container {
  display: flex;
  justify-content: flex-start;
  gap: 8px;
  position: absolute;
  bottom: 14px;
  left: 0;
  right: 0;
  padding: 16px;
  transition: transform 0.3s ease-in-out;
  transform: translateY(150%);
}

.agent-card:hover .footer-hover-container {
  transform: translateY(0);
}
</style>