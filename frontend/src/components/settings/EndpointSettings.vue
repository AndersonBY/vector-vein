<script setup>
import { ref, reactive, toRaw, computed } from "vue"
import { useI18n } from 'vue-i18n'
import { message, Modal } from 'ant-design-vue'
import { Delete } from '@icon-park/vue-next'
import { deepCopy, hashObject } from '@/utils/util'
import { settingAPI } from "@/api/user"

const { t } = useI18n()

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

const endpointFormRemove = (index) => {
  endpoints.value.splice(index, 1)
}

const hasUnsavedChanges = () => {
  // 使用hashObject计算当前表单的哈希值，并与原始哈希值比较
  const currentHash = hashObject(toRaw(endpointForm), ['credentials'])
  return currentHash !== originalFormHash.value
}

const switchEndpoint = (endpoint, index) => {
  Object.assign(endpointForm, defaultParams)
  const copiedEndpoint = deepCopy(toRaw(endpoint))
  copiedEndpoint.credentials = copiedEndpoint.credentials ? JSON.stringify(copiedEndpoint.credentials, null, 2) : ''
  Object.assign(endpointForm, copiedEndpoint)
  endpointFormStatus.value = 'edit'
  endpointEditIndex.value = index

  // 保存初始状态的哈希值，用于后续比较
  originalFormHash.value = hashObject(toRaw(endpointForm), ['credentials'])
}

const endpointFormEdit = (endpoint, index) => {
  // 检查当前表单是否有未保存的更改
  if (endpointFormStatus.value !== '' && hasUnsavedChanges()) {
    Modal.confirm({
      title: t('settings.unsaved_changes'),
      content: t('settings.save_changes_confirm'),
      okText: t('settings.save'),
      cancelText: t('settings.discard'),
      onOk: () => {
        endpointFormSave()
        switchEndpoint(endpoint, index)
      },
      onCancel: () => {
        switchEndpoint(endpoint, index)
      }
    })
  } else {
    switchEndpoint(endpoint, index)
  }
}

const endpointFormSave = () => {
  const formData = deepCopy(toRaw(endpointForm))
  if (!formData.api_base) {
    message.error(t('settings.api_base_empty'))
    return ''
  }
  if (!formData.id) {
    message.error(t('settings.endpoint_id_empty'))
    return ''
  }
  try {
    formData.credentials = formData.credentials ? JSON.parse(formData.credentials) : {}
  } catch (error) {
    console.error('凭证 JSON 解析错误:', error)
    message.error(t('settings.credentials_parse_failed'))
    return ''
  }

  if (endpointFormStatus.value === 'edit') {
    Object.assign(endpoints.value[endpointEditIndex.value], formData)
  } else {
    endpoints.value.push(formData)
  }
  Object.keys(endpointForm).forEach(key => endpointForm[key] = '')
  endpointFormStatus.value = ''
  originalFormHash.value = 0
  return formData.id
}

const addNewEndpoint = () => {
  // 检查当前表单是否有未保存的更改
  if (endpointFormStatus.value !== '' && hasUnsavedChanges()) {
    Modal.confirm({
      title: t('settings.unsaved_changes'),
      content: t('settings.save_changes_confirm'),
      okText: t('settings.save'),
      cancelText: t('settings.discard'),
      onOk: () => {
        endpointFormSave()
        resetForm()
      },
      onCancel: () => {
        resetForm()
      }
    })
  } else {
    resetForm()
  }
}

const resetForm = () => {
  Object.assign(endpointForm, defaultParams)
  endpointForm.id = 'new-endpoint'
  endpointFormStatus.value = 'add'
  originalFormHash.value = hashObject(toRaw(endpointForm), ['credentials'])
}

const availableModelsState = reactive({
  listing: false,
  list: async () => {
    availableModelsState.listing = true
    try {
      const response = await settingAPI('list_models', { api_key: endpointForm.api_key, base_url: endpointForm.api_base })
      availableModelsState.availableModels = (response?.data?.models?.data || []).map(item => ({ key: item.id, ...item }))
      availableModelsState.total = response?.data?.models?.data?.length || 0
      availableModelsState.modalOpen = true
    } catch (error) {
      message.error(t('settings.list_models_failed') + ': ' + error.message)
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
  addToCustomModels: () => {
    const endpointId = endpointFormSave()
    if (endpointId) {
      availableModelsState.modalOpen = false
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
    }
  },
})
</script>

<template>
  <a-row :gutter="[12, 12]">
    <a-col :sm="24" :md="8">
      <a-flex vertical gap="small">
        <a-flex v-for="(endpoint, index) in endpoints" :key="endpoint.id" gap="small" align="center">
          <a-button type="text" block @click="endpointFormEdit(endpoint, index)">
            <a-typography-text ellipsis :content="endpoint.id" />
          </a-button>
          <a-button type="text" @click="endpointFormRemove(index)">
            <template #icon>
              <Delete fill="#ff4d4f" />
            </template>
          </a-button>
        </a-flex>
        <a-button type="dashed" block @click="addNewEndpoint">
          {{ t('settings.add_endpoint') }}
        </a-button>
      </a-flex>
    </a-col>
    <a-col v-show="['edit', 'add'].includes(endpointFormStatus)" :sm="24" :md="16">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
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
        <a-button block @click="availableModelsState.list" :loading="availableModelsState.listing">
          {{ t('settings.list_models') }}
        </a-button>
        <a-button type="primary" block @click="endpointFormSave" :disabled="!endpointForm.id">
          {{ t('settings.save_endpoint') }}
        </a-button>
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
                :disabled="!availableModelsState.selectedModel.length">
                {{ t('settings.add_to_custom_models') }}
              </a-button>
            </a-flex>
          </template>
        </a-modal>
      </a-flex>
    </a-col>
  </a-row>
</template>
