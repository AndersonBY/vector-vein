<script setup>
import { ref, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import TextOutput from "@/components/TextOutput.vue"
import { logAPI } from "@/api/user"

const props = defineProps({
  logId: {
    type: String,
    default: 'default'
  },
  title: {
    type: String,
    default: ''
  },
})

const open = defineModel('open', { default: false })

const { t } = useI18n()
const loading = ref(false)
const error = ref(null)
const logContent = ref('')
const isAutoRefreshing = ref(false)
let refreshInterval = null

const loadLogContent = async () => {
  error.value = null
  try {
    const response = await logAPI('get_log_content', {
      log_id: props.logId
    })
    if (response.status === 200) {
      logContent.value = `\`\`\`prolog\n${response.data.content}\n\`\`\``
    } else {
      throw new Error('获取日志内容失败')
    }
  } catch (err) {
    error.value = err.message
  }
}

const toggleAutoRefresh = () => {
  isAutoRefreshing.value = !isAutoRefreshing.value
  if (isAutoRefreshing.value) {
    refreshInterval = setInterval(loadLogContent, 500)
  } else {
    clearInterval(refreshInterval)
  }
}

watch(() => open.value, async (newValue) => {
  if (newValue && !logContent.value) {
    await loadLogContent()
    setTimeout(() => {
      const logContainer = document.querySelector('.log-modal-content');
      if (logContainer) {
        logContainer.scrollTop = logContainer.scrollHeight;
      }
    }, 100);
  }
})

function handleClose() {
  open.value = false
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
}

onUnmounted(() => {
  handleClose()
})
</script>

<template>
  <a-modal v-model:open="open" :title="title" :footer="null" width="70%" @cancel="handleClose">
    <a-skeleton v-if="loading" active />
    <div v-else-if="error">{{ t('components.help.logModal.load_error') }}</div>
    <a-flex v-else vertical gap="middle">
      <div class="log-modal-content custom-scrollbar">
        <TextOutput :text="logContent" :showCopy="false" />
      </div>
      <a-flex justify="end">
        <a-button @click="toggleAutoRefresh" :type="isAutoRefreshing ? 'primary' : 'default'">
          {{ isAutoRefreshing ? t('components.help.logModal.stop_refresh') : t('components.help.logModal.auto_refresh')
          }}
        </a-button>
      </a-flex>
    </a-flex>
  </a-modal>
</template>

<style scoped>
.log-modal-content {
  max-height: 70vh;
  overflow-y: auto;
}
</style>
