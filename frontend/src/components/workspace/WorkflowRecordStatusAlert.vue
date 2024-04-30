<script setup>
import { ref } from "vue"
import { useI18n } from 'vue-i18n'

const props = defineProps({
  status: {
    type: String,
    required: true,
  },
  rawErrorTask: {
    type: String,
    default: '',
  }
})

const getErrorTask = (rawErrorTask) => {
  let [category, node] = (rawErrorTask || '.').split('.')
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
  return `${category}.${node}`
}
const errorTask = ref(getErrorTask(props.rawErrorTask))

const { t } = useI18n()
const getAlertType = () => {
  if (props.status == 'FINISHED') {
    return 'success'
  }
  else if (props.status == 'FAILED') {
    return 'error'
  } else if (props.status == 'STOPPED' || props.status == 'STOPPING') {
    return 'warning'
  } else {
    return 'info'
  }
}
const alertType = ref(getAlertType())
</script>

<template>
  <a-alert :type="alertType" banner="" show-icon>
    <template #message>
      <span>
        {{ t('workspace.workflowSpace.record_status', {
          status:
            t(`components.workspace.workflowRunRecordsDrawer.status_${status.toLowerCase()}`)
        }) }}
      </span>
      <a-divider type="vertical" />
      <span v-if="status == 'FAILED' && errorTask != '.'">
        {{ t('workspace.workflowSpace.record_error_task', {
          task: t(`components.nodes.${errorTask}.title`)
        }) }}
      </span>
    </template>
  </a-alert>
</template>