<script setup>
import { Refresh } from '@/icons'
import IconButton from '@/components/IconButton.vue'
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
const hasSavedSecret = key => endpointForm._saved_secret_fields?.includes(key)
const editSecret = key => {
  if (endpointForm._saved_secret_fields) {
    endpointForm._saved_secret_fields = endpointForm._saved_secret_fields.filter(field => field !== key)
  }
}
const originalFormHash = ref(0)
const testBackend = computed(() => endpointForm.endpoint_type?.startsWith('anthropic') ? 'anthropic' : 'local')

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

const availableModelsState = reactive({
  listing: false,
  list: async () => {
    const endpoint = readEndpoint()
    if (!endpoint) return
    availableModelsState.listing = true
    try {
      const response = await settingAPI('list_models', { endpoint })
      if (response?.status !== 200) {
        message.error(response?.msg || t('settings.list_models_failed'))
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
    <a-col :xs="24" :md="8">
      <a-flex vertical gap="small">
        <a-flex v-for="(endpoint, index) in endpoints" :key="endpoint.id" class="endpoint-row" gap="small" align="center">
          <a-button type="text" class="endpoint-select" :disabled="saving" :title="endpoint.id"
            :aria-pressed="endpointFormStatus === 'edit' && endpointEditIndex === index" @click="endpointFormEdit(endpoint, index)">
            <span class="endpoint-name">{{ endpoint.id }}</span>
          </a-button>
          <IconButton :text="t('common.delete')" class="endpoint-delete" :disabled="saving" @click="endpointFormRemove(index)">
            <template #icon>
              <Delete fill="#ff4d4f" />
            </template>
          </IconButton>
        </a-flex>
        <a-button type="dashed" block :disabled="saving" @click="addNewEndpoint">
          {{ t('settings.add_endpoint') }}
        </a-button>
      </a-flex>
    </a-col>
    <a-col v-show="['edit', 'add'].includes(endpointFormStatus)" :xs="24" :md="16">
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
          <a-input-password v-model:value="endpointForm.api_key" @change="editSecret('api_key')"
            :placeholder="hasSavedSecret('api_key') ? t('settings.saved_secret_placeholder') : ''" />
          <a-typography-text v-if="hasSavedSecret('api_key')" type="secondary">{{ t('settings.saved_secret_hint') }}</a-typography-text>
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
          <a-textarea v-model:value="endpointForm.credentials" @change="editSecret('credentials')"
            :placeholder="hasSavedSecret('credentials') ? t('settings.saved_secret_placeholder') : t('settings.credentials_placeholder')"
            :auto-size="{ minRows: 4, maxRows: 8 }" />
        </a-form-item>
        <a-form-item :label="t('settings.concurrent_requests')">
          <a-input-number v-model:value="endpointForm.concurrent_requests" />
        </a-form-item>
      </a-form>
      <a-flex wrap justify="space-between" gap="small">
        <IconButton :text="t('settings.list_models')" @click="availableModelsState.list" :disabled="saving" :loading="availableModelsState.listing"><template #icon><Refresh /></template></IconButton>
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

<style scoped>
.endpoint-row {
  min-width: 0;
}

.endpoint-select {
  flex: 1;
  min-width: 0;
  text-align: left;
}

.endpoint-name {
  display: block;
  min-width: 0;
  width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.endpoint-delete {
  flex-shrink: 0;
}

.endpoint-select[aria-pressed="true"] {
  color: var(--color-primary);
  background: var(--more-hover-background);
}
</style>
