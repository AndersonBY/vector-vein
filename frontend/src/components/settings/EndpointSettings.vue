<script setup>
import { ref, reactive, toRaw } from "vue"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { Delete } from '@icon-park/vue-next'
import { deepCopy } from '@/utils/util'

const { t } = useI18n()

const endpoints = defineModel()

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
  endpoint_name: '',
  is_azure: false,
  is_vertex: false,
  credentials: '',
}
const endpointForm = reactive(deepCopy(defaultParams))

const endpointFormRemove = (index) => {
  endpoints.value.splice(index, 1)
}

const endpointFormEdit = (endpoint, index) => {
  Object.assign(endpointForm, defaultParams)
  const copiedEndpoint = deepCopy(toRaw(endpoint))
  copiedEndpoint.is_azure = copiedEndpoint.is_azure
  copiedEndpoint.is_vertex = copiedEndpoint.is_vertex
  copiedEndpoint.credentials = copiedEndpoint.credentials ? JSON.stringify(copiedEndpoint.credentials, null, 2) : ''
  Object.assign(endpointForm, copiedEndpoint)
  endpointFormStatus.value = 'edit'
  endpointEditIndex.value = index
}

const endpointFormSave = () => {
  const formData = deepCopy(toRaw(endpointForm))
  if (!formData.api_base) {
    message.error(t('settings.api_base_empty'))
    return
  }
  try {
    formData.credentials = formData.credentials ? JSON.parse(formData.credentials) : {}
  } catch (error) {
    console.error('凭证 JSON 解析错误:', error)
    return
  }

  if (endpointFormStatus.value === 'edit') {
    Object.assign(endpoints.value[endpointEditIndex.value], formData)
  } else {
    endpoints.value.push(formData)
  }
  Object.keys(endpointForm).forEach(key => endpointForm[key] = '')
  endpointFormStatus.value = ''
}

const addNewEndpoint = () => {
  Object.assign(endpointForm, defaultParams)
  endpointForm.id = 'new-endpoint'
  endpointFormStatus.value = 'add'
}

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
        <a-form-item :label="t('settings.endpoint_id')">
          <a-input v-model:value="endpointForm.id" />
        </a-form-item>
        <a-form-item :label="t('settings.is_azure')">
          <a-switch v-model:checked="endpointForm.is_azure" />
        </a-form-item>
        <a-form-item :label="t('settings.is_vertex')">
          <a-switch v-model:checked="endpointForm.is_vertex" />
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
        <a-form-item :label="t('settings.region')">
          <a-input v-model:value="endpointForm.region" />
        </a-form-item>
        <a-form-item :label="t('settings.endpoint_name')">
          <a-input v-model:value="endpointForm.endpoint_name" />
        </a-form-item>
        <a-form-item :label="t('settings.credentials')">
          <a-textarea v-model:value="endpointForm.credentials" :placeholder="t('settings.credentials_placeholder')"
            :auto-size="{ minRows: 4, maxRows: 8 }" />
        </a-form-item>
        <a-form-item :label="t('settings.concurrent_requests')">
          <a-input-number v-model:value="endpointForm.concurrent_requests" />
        </a-form-item>
      </a-form>
      <a-flex justify="flex-end">
        <a-button type="primary" block @click="endpointFormSave">
          {{ t('settings.save_endpoint') }}
        </a-button>
      </a-flex>
    </a-col>
  </a-row>
</template>
