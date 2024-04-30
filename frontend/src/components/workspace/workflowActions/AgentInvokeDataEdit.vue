<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import QuestionPopover from '@/components/QuestionPopover.vue'
import { workflowAPI, workflowTemplateAPI } from '@/api/workflow'

const props = defineProps({
  workflowData: {
    type: Object,
    required: true,
  },
  type: {
    type: String,
    required: false,
    default: 'menuItem'
  },
  block: {
    type: Boolean,
    required: false,
    default: false
  },
  workflowType: {
    type: String,
    required: false,
    default: 'workflow'
  }
})

const { t } = useI18n()
const open = ref(false)
const loading = ref(false)
const toolCallData = ref(props.workflowData.tool_call_data || {})
const parameters = ref([])
parameters.value = Object.keys(props.workflowData?.tool_call_data?.parameters?.properties ?? {}).map(key => {
  return {
    key: key,
    value: props.workflowData.tool_call_data.parameters.properties[key],
    source: props.workflowData.tool_call_data.parameter_sources[key],
    required: props.workflowData.tool_call_data.parameters.required.includes(key),
  }
})

const saveSettings = async () => {
  loading.value = true
  // toolCallData.name Must be a-z, A-Z, 0-9, or contain underscores and dashes, with a maximum length of 64.
  const reg = /^[a-zA-Z0-9_-]{1,64}$/
  if (!reg.test(toolCallData.value.name)) {
    message.error(t('components.workspace.agentInvokeDataEdit.tool_name_error'))
    loading.value = false
    return
  }

  toolCallData.value.parameters = {
    type: 'object',
    properties: parameters.value.reduce((obj, item) => {
      obj[item.key] = item.value
      if (item.description) {
        obj[item.key].description = item.description
      }
      return obj
    }, {}),
    required: parameters.value.filter(item => item.required).map(item => item.key),
  }
  toolCallData.value.parameter_sources = parameters.value.reduce((obj, item) => {
    obj[item.key] = {
      ...item.source,
      required: item.required,
    }
    return obj
  }, {})

  let res = {}
  if (props.workflowType == 'workflow') {
    res = await workflowAPI('update-tool-call-data', {
      wid: props.workflowData.wid,
      tool_call_data: toolCallData.value,
    })
  } else {
    res = await workflowTemplateAPI('update-tool-call-data', {
      tid: props.workflowData.tid,
      tool_call_data: toolCallData.value,
    })
  }
  if (res.data.status == 200) {
    message.success(t('common.save_success'))
    open.value = false
  } else {
    message.error(res.data.msg)
  }
  loading.value = false
}
</script>

<template>
  <div>
    <a-menu-item key="agent_invoke" @click="open = true" v-if="props.type == 'menuItem'">
      {{ t('components.workspace.agentInvokeDataEdit.agent_invoke') }}
    </a-menu-item>
    <a-button :block="block" @click="open = true" v-else-if="props.type == 'button'">
      {{ t('components.workspace.agentInvokeDataEdit.agent_invoke') }}
    </a-button>
    <a-drawer :title="t('components.workspace.agentInvokeDataEdit.agent_invoke')" :open="open" @close="open = false">
      <template #extra>
        <a-button type="primary" @click="saveSettings">
          {{ t('common.save') }}
        </a-button>
      </template>
      <a-spin :spinning="loading">
        <a-form ref="modifyFormRef" :model="toolCallData" layout="vertical">
          <a-form-item name="name"
            :rules="[{ required: true, message: t('components.workspace.agentInvokeDataEdit.tool_name_required') }]">
            <template #label>
              {{ t('components.workspace.agentInvokeDataEdit.tool_name') }}
              <QuestionPopover :content="[t('components.workspace.agentInvokeDataEdit.tool_name_tip')]" />
            </template>
            <a-input v-model:value="toolCallData.name" :showCount="true"
              :placeholder="t('components.workspace.agentInvokeDataEdit.tool_name_placeholder')" />
          </a-form-item>
          <a-form-item name="description">
            <template #label>
              {{ t('components.workspace.agentInvokeDataEdit.tool_description') }}
              <QuestionPopover :content="[t('components.workspace.agentInvokeDataEdit.tool_description_tip')]" />
            </template>
            <a-textarea :autoSize="{ minRows: 3, maxRows: 10 }" v-model:value="toolCallData.description"
              :placeholder="t('components.workspace.agentInvokeDataEdit.tool_description_placeholder')" />
          </a-form-item>
          <a-divider>{{ t('components.workspace.agentInvokeDataEdit.parameters') }}</a-divider>
          <a-flex vertical gap="middle">
            <a-card v-for="parameter in parameters" :title="parameter.key">
              <a-form-item :label="t('components.workspace.agentInvokeDataEdit.parameter_name')">
                <a-input v-model:value="parameter.key" />
              </a-form-item>
              <a-form-item :label="t('components.workspace.agentInvokeDataEdit.parameter_description')">
                <a-input v-model:value="parameter.description" />
              </a-form-item>
              <a-form-item>
                <a-checkbox v-model:checked="parameter.required">
                  {{ t('components.workspace.agentInvokeDataEdit.parameter_required') }}
                </a-checkbox>
              </a-form-item>
            </a-card>
          </a-flex>
        </a-form>
      </a-spin>
    </a-drawer>
  </div>
</template>
