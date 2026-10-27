<script setup>
import { ref, reactive, toRaw, computed, watch } from "vue"
import { useI18n } from 'vue-i18n'
import { message, Modal } from 'ant-design-vue'
import { Delete } from '@/icons'
import { deepCopy, hashObject } from '@/utils/util'
import { settingAPI } from "@/api/user"
import ModelEndpointTest from '@/components/settings/ModelEndpointTest.vue'

const { t } = useI18n()
const props = defineProps({
  saveSettings: { type: Function, required: true },
  saving: { type: Boolean, default: false },
})
const emit = defineEmits(['dirty'])

const endpoints = defineModel('endpoints')
const localModels = defineModel('localModels')
const modelFamilyMap = defineModel('modelFamilyMap')

const endpointFormStatus = ref('')
const endpointEditIndex = ref()
const defaultParams = {
  id: '',
  api_base: '',
  api_key: '',
  rpm: 10,
  tpm: 300000,
  concurrent_requests: 1,
  region: '',
  endpoint_type: 'default',
  credentials: '',
}
const endpointForm = reactive(deepCopy(defaultParams))
const originalFormHash = ref(0)
const testBackend = computed(() => endpointForm.endpoint_type?.startsWith('anthropic') ? 'anthropic' : 'local')
const endpointPresets = [
  { key: 'ollama', label: 'Ollama', api_base: 'http://127.0.0.1:11434/v1', endpoint_type: 'openai' },
  { key: 'lmstudio', label: 'LM Studio', api_base: 'http://127.0.0.1:1234/v1', endpoint_type: 'openai' },
  { key: 'vllm', label: 'vLLM', api_base: 'http://127.0.0.1:8000/v1', endpoint_type: 'openai' },
  { key: 'openai', label: 'OpenAI Compatible', api_base: 'https://api.openai.com/v1', endpoint_type: 'openai' },
]

const endpointFormRemove = (index) => {
  if (props.saving) return
  endpoints.value.splice(index, 1)
  if (endpointFormStatus.value === 'edit') {
    if (endpointEditIndex.value === index) closeEditor()
    else if (endpointEditIndex.value > index) endpointEditIndex.value--
  }
}

const hasUnsavedChanges = () => {
  return !!endpointFormStatus.value && hashObject(endpointForm) !== originalFormHash.value
}
watch(hasUnsavedChanges, value => emit('dirty', value), { immediate: true })

const switchEndpoint = (endpoint, index) => {
  clearForm()
  const copiedEndpoint = deepCopy(toRaw(endpoint))
  copiedEndpoint.credentials = copiedEndpoint.credentials ? JSON.stringify(copiedEndpoint.credentials, null, 2) : ''
  Object.assign(endpointForm, copiedEndpoint)
  endpointFormStatus.value = 'edit'
  endpointEditIndex.value = index

  // 保存初始状态的哈希值，用于后续比较
  originalFormHash.value = hashObject(toRaw(endpointForm))
}

const endpointFormEdit = (endpoint, index) => {
  if (props.saving) return
  // 检查当前表单是否有未保存的更改
  if (endpointFormStatus.value !== '' && hasUnsavedChanges()) {
    Modal.confirm({
      title: t('settings.unsaved_changes'),
      content: t('settings.save_changes_confirm'),
      okText: t('settings.save'),
      cancelText: t('common.cancel'),
      onOk: async () => {
        if (!await props.saveSettings()) throw new Error('Settings save failed')
        switchEndpoint(endpoint, index)
      },
    })
  } else {
    switchEndpoint(endpoint, index)
  }
}

const readEndpoint = () => {
  const formData = deepCopy(toRaw(endpointForm))
  if (!formData.api_base) {
    message.error(t('settings.api_base_empty'))
    return ''
  }
  if (!formData.id) {
    message.error(t('settings.endpoint_id_empty'))
    return ''
  }
  if (endpoints.value.some((endpoint, index) => endpoint.id === formData.id &&
      (endpointFormStatus.value !== 'edit' || index !== endpointEditIndex.value))) {
    message.error(t('settings.endpoint_id_duplicate'))
    return ''
  }
  try {
    formData.credentials = formData.credentials ? JSON.parse(formData.credentials) : {}
  } catch (error) {
    message.error(t('settings.credentials_parse_failed'))
    return ''
  }

  return formData
}
const clearForm = () => {
  Object.keys(endpointForm).forEach(key => delete endpointForm[key])
  Object.assign(endpointForm, defaultParams)
}
const closeEditor = () => {
  clearForm()
  endpointFormStatus.value = ''
  endpointEditIndex.value = undefined
  originalFormHash.value = 0
}
const prepareSave = () => {
  if (!endpointFormStatus.value) return null
  const endpoint = readEndpoint()
  if (!endpoint) return false
  const submitted = deepCopy(toRaw(endpoints.value))
  if (endpointFormStatus.value === 'edit') submitted[endpointEditIndex.value] = endpoint
  else submitted.push(endpoint)
  return submitted
}
defineExpose({ prepareSave, markSaved: closeEditor })

const addNewEndpoint = () => {
  if (props.saving) return
  // 检查当前表单是否有未保存的更改
  if (endpointFormStatus.value !== '' && hasUnsavedChanges()) {
    Modal.confirm({
      title: t('settings.unsaved_changes'),
      content: t('settings.save_changes_confirm'),
      okText: t('settings.save'),
      cancelText: t('common.cancel'),
      onOk: async () => {
        if (!await props.saveSettings()) throw new Error('Settings save failed')
        resetForm()
      },
    })
  } else {
    resetForm()
  }
}

const resetForm = () => {
  clearForm()
  endpointForm.id = 'new-endpoint'
  endpointFormStatus.value = 'add'
  originalFormHash.value = hashObject(toRaw(endpointForm))
}

const applyPreset = (preset) => {
  if (!endpointFormStatus.value) {
    resetForm()
  }
  endpointForm.api_base = preset.api_base
  endpointForm.endpoint_type = preset.endpoint_type
  if (endpointForm.id === 'new-endpoint') {
    endpointForm.id = preset.key
  }
}

const availableModelsState = reactive({
  listing: false,
  list: async () => {
    availableModelsState.listing = true
    try {
      const response = await settingAPI('list_models', { api_key: endpointForm.api_key, base_url: endpointForm.api_base })
      if (response?.status !== 200) {
        message.error(t('settings.list_models_failed'))
        return
      }
      availableModelsState.availableModels = (response?.data?.models?.data || []).map(item => ({ key: item.id, ...item }))
      availableModelsState.total = response?.data?.models?.data?.length || 0
      availableModelsState.modalOpen = true
    } catch (error) {
      message.error(t('settings.list_models_failed'))
      availableModelsState.modalOpen = false
    } finally {
      availableModelsState.listing = false
    }
  },
  availableModels: [],
  selectedModel: [],
  onSelectChange: (selectedRowKeys) => {
    availableModelsState.selectedModel = selectedRowKeys
  },
  total: 0,
  current: 1,
  pageSize: 10,
  pagination: computed(() => ({
    total: availableModelsState.total,
    current: availableModelsState.current,
    pageSize: availableModelsState.pageSize,
  })),
  handleTableChange: (page, filters, sorter) => {
    availableModelsState.current = page.current
    availableModelsState.pageSize = page.pageSize
  },
  columns: [
    {
      title: t('settings.model_id'),
      dataIndex: 'id',
      key: 'id',
    },
    {
      title: t('settings.model_owned_by'),
      dataIndex: 'owned_by',
      key: 'owned_by',
    }
  ],
  modalOpen: false,
  selectAll: () => {
    availableModelsState.selectedModel = availableModelsState.availableModels.map(item => item.id)
  },
  addToCustomModels: async () => {
    if (props.saving) return
    const endpoint = readEndpoint()
    if (endpoint) {
      const endpointId = endpoint.id
      availableModelsState.selectedModel.forEach(item => {
        localModels.value.models[item] = {
          "id": item,
          "endpoints": [endpointId],
          "function_call_available": false,
          "response_format_available": false,
          "native_multimodal": false,
          "context_length": 32768,
          "max_output_tokens": 4096
        }
      })
      modelFamilyMap.value[endpointId] = availableModelsState.selectedModel
      if (await props.saveSettings()) availableModelsState.modalOpen = false
    }
  },
})
</script>

<template>
  <a-row :gutter="[12, 12]">
    <a-col :sm="24" :md="8">
      <a-flex vertical gap="small">
        <a-flex v-for="(endpoint, index) in endpoints" :key="endpoint.id" gap="small" align="center">
          <a-button type="text" block :disabled="saving" @click="endpointFormEdit(endpoint, index)">
            <a-typography-text ellipsis :content="endpoint.id" />
          </a-button>
          <a-button type="text" :disabled="saving" :aria-label="t('common.delete')" @click="endpointFormRemove(index)">
            <template #icon>
              <Delete fill="#ff4d4f" />
            </template>
          </a-button>
        </a-flex>
        <a-button type="dashed" block :disabled="saving" @click="addNewEndpoint">
          {{ t('settings.add_endpoint') }}
        </a-button>
      </a-flex>
    </a-col>
    <a-col v-show="['edit', 'add'].includes(endpointFormStatus)" :sm="24" :md="16">
      <a-flex wrap gap="small" style="margin-bottom: 12px;">
        <a-button v-for="preset in endpointPresets" :key="preset.key" size="small" :disabled="saving" @click="applyPreset(preset)">
          {{ preset.label }}
        </a-button>
      </a-flex>
      <a-form :disabled="saving" :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <a-form-item :label="t('settings.endpoint_id')" :required="true">
          <a-input v-model:value="endpointForm.id" />
        </a-form-item>
        <a-form-item :label="t('settings.endpoint_type')">
          <a-select v-model:value="endpointForm.endpoint_type" :options="[
            { label: t('settings.endpoint_type_default'), value: 'default' },
            { label: 'OpenAI', value: 'openai' },
            { label: 'OpenAI Azure', value: 'openai_azure' },
            { label: 'Anthropic', value: 'anthropic' },
            { label: 'Anthropic Vertex', value: 'anthropic_vertex' },
            { label: 'Anthropic Bedrock', value: 'anthropic_bedrock' },
          ]" />
        </a-form-item>
        <a-form-item :label="t('settings.api_base')">
          <a-input v-model:value="endpointForm.api_base" />
        </a-form-item>
        <a-form-item :label="t('settings.api_key')">
          <a-input-password v-model:value="endpointForm.api_key" />
        </a-form-item>
        <a-form-item label="RPM">
          <a-input-number v-model:value="endpointForm.rpm" />
        </a-form-item>
        <a-form-item label="TPM">
          <a-input-number v-model:value="endpointForm.tpm" />
        </a-form-item>
        <a-form-item :label="t('settings.region')"
          :required="['anthropic_vertex', 'anthropic_bedrock'].includes(endpointForm.endpoint_type)">
          <a-input v-model:value="endpointForm.region" />
        </a-form-item>
        <a-form-item :label="t('settings.credentials')"
          :required="['anthropic_vertex', 'anthropic_bedrock'].includes(endpointForm.endpoint_type)">
          <a-textarea v-model:value="endpointForm.credentials" :placeholder="t('settings.credentials_placeholder')"
            :auto-size="{ minRows: 4, maxRows: 8 }" />
        </a-form-item>
        <a-form-item :label="t('settings.concurrent_requests')">
          <a-input-number v-model:value="endpointForm.concurrent_requests" />
        </a-form-item>
      </a-form>
      <a-flex justify="space-between" gap="small">
        <a-button block @click="availableModelsState.list" :disabled="saving" :loading="availableModelsState.listing">
          {{ t('settings.list_models') }}
        </a-button>
        <a-button type="primary" block @click="saveSettings()" :loading="saving" :disabled="!endpointForm.id">
          {{ t('settings.save') }}
        </a-button>
        <a-button :disabled="saving" @click="closeEditor">{{ t('settings.cancel_endpoint_edit') }}</a-button>
        <a-modal v-model:open="availableModelsState.modalOpen" :title="t('settings.available_models')">
          <a-table :dataSource="availableModelsState.availableModels" :columns="availableModelsState.columns"
            :rowSelection="{ selectedRowKeys: availableModelsState.selectedModel, onChange: availableModelsState.onSelectChange }"
            :pagination="availableModelsState.pagination" @change="availableModelsState.handleTableChange">
          </a-table>
          <template #footer>
            <a-flex justify="space-between" gap="small">
              <a-space>
                <a-button @click="availableModelsState.selectAll">
                  {{ t('settings.select_all') }}
                </a-button>
                <a-button @click="availableModelsState.selectedModel = []"
                  :disabled="!availableModelsState.selectedModel.length">
                  {{ t('settings.clear') }}
                </a-button>
              </a-space>
              <a-button type="primary" @click="availableModelsState.addToCustomModels"
                :loading="saving" :disabled="!availableModelsState.selectedModel.length || saving">
                {{ t('settings.add_to_custom_models') }}
              </a-button>
            </a-flex>
          </template>
        </a-modal>
      </a-flex>
      <ModelEndpointTest :endpoint="endpointForm" :backend="testBackend" :active="!!endpointFormStatus"
        editable-model select-backend />
    </a-col>
  </a-row>
</template>
