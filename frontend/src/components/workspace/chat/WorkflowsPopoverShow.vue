<script setup>
import { reactive, watch } from "vue"
import { useI18n } from 'vue-i18n'
import { WholeSiteAccelerator } from '@icon-park/vue-next'
import IconButton from '@/components/IconButton.vue'

const props = defineProps({
  selectedFlows: {
    type: Object,
    required: false,
    default: () => ({
      workflows: {},
      templates: {},
    }),
  }
})

const selectedFlows = reactive({
  workflows: props.selectedFlows.workflows,
  templates: props.selectedFlows.templates,
})

watch(() => props.selectedFlows.workflows, (newVal) => {
  selectedFlows.workflows = newVal
})
watch(() => props.selectedFlows.templates, (newVal) => {
  selectedFlows.templates = newVal
})

const { t } = useI18n()
</script>

<template>
  <div>
    <a-popover
      :title="Object.keys(selectedFlows.workflows).length == 0 && Object.keys(selectedFlows.templates).length == 0 ? t('workspace.chatSpace.no_selected_workflows') : t('workspace.chatSpace.selected_workflows')"
      placement="topLeft">
      <template #content>
        <ul>
          <li v-for="flow in selectedFlows.workflows">
            <a-typography-paragraph>
              {{ flow.title }}
            </a-typography-paragraph>
          </li>
          <li v-for="flow in selectedFlows.templates">
            <a-typography-paragraph>
              {{ flow.title }}
            </a-typography-paragraph>
          </li>
        </ul>
      </template>
      <IconButton :text="t('workspace.chatSpace.workflows')" size="small" type="text" shape="round">
        <template #icon>
          <WholeSiteAccelerator />
        </template>
      </IconButton>
    </a-popover>
  </div>
</template>