<script setup>
import { computed, reactive, ref, toRaw, watch } from "vue"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { Edit, Delete } from '@/icons'
import IconButton from '@/components/IconButton.vue'
import RetrievalModelTest from './RetrievalModelTest.vue'
import QuestionPopover from "@/components/QuestionPopover.vue"
import { deepCopy } from '@/utils/util'

const props = defineProps({
  kind: { type: String, default: 'embedding' },
  backend: { type: String, default: 'local' },
  endpoints: {
    type: Array,
    default: () => []
  }
})

const { t } = useI18n()
const backendSettings = defineModel()

const protocolOptions = computed(() => props.kind === 'rerank' ? [
  { label: 'Cohere Rerank v2', value: 'cohere_rerank_v2' },
  { label: 'Jina Rerank v1', value: 'jina_rerank_v1' },
  { label: 'Voyage Rerank v1', value: 'voyage_rerank_v1' },
  { label: 'SiliconFlow', value: 'siliconflow' },
  { label: t('settings.custom_http_protocol'), value: 'custom_json_http' },
] : [
  { label: 'OpenAI Embeddings', value: 'openai_embeddings' },
  { label: 'Cohere Embed v2', value: 'cohere_embed_v2' },
  { label: 'Voyage Embeddings v1', value: 'voyage_embeddings_v1' },
  { label: 'SiliconFlow', value: 'siliconflow' },
  { label: t('settings.custom_http_protocol'), value: 'custom_json_http' },
])

const ensureBackendSettings = () => {
  if (!backendSettings.value || typeof backendSettings.value !== 'object' || Array.isArray(backendSettings.value)) {
    backendSettings.value = { models: {}, default_endpoint: null }
    return
  }
  if (!backendSettings.value.models || typeof backendSettings.value.models !== 'object' || Array.isArray(backendSettings.value.models)) {
    backendSettings.value.models = {}
  }
  if (!Object.prototype.hasOwnProperty.call(backendSettings.value, 'default_endpoint')) {
    backendSettings.value.default_endpoint = null
  }
}

ensureBackendSettings()

watch(
  backendSettings,
  () => {
    ensureBackendSettings()
  },
  { immediate: true }
)

const endpointOptions = computed(() => {
  return props.endpoints.map((endpoint) => ({
    value: endpoint.id,
    label: endpoint.id
  }))
})

const modelFormModalOpen = ref(false)
const modelFormStatus = ref('')
const modelEditKey = ref('')
const endpointModelModalOpen = ref(false)
const endpointEditIndex = ref(null)

const modelForm = reactive({
  id: '',
  endpoints: [],
  enabled: true,
  protocol: '',
  dimensions: null,
  request_mapping_json: '',
  response_mapping_json: '',
})

const endpointModelForm = reactive({
  endpoint_id: '',
  model_id: ''
})

const formatOptionalJson = (value) => {
  if (!value) {
    return ''
  }
  return JSON.stringify(value, null, 2)
}

const resetModelForm = () => {
  endpointModelModalOpen.value = false
  endpointEditIndex.value = null
  Object.assign(modelForm, {
    id: '',
    endpoints: [],
    enabled: true,
    protocol: '',
    dimensions: null,
    request_mapping_json: '',
    response_mapping_json: '',
  })
}

const addNewModel = () => {
  modelFormStatus.value = 'add'
  modelEditKey.value = ''
  resetModelForm()
  modelFormModalOpen.value = true
}

const editModel = (model, modelKey) => {
  modelFormStatus.value = 'edit'
  modelEditKey.value = modelKey
  resetModelForm()
  Object.assign(modelForm, {
    ...deepCopy(toRaw(model)),
    request_mapping_json: formatOptionalJson(model.request_mapping),
    response_mapping_json: formatOptionalJson(model.response_mapping),
  })
  modelForm.endpoints = deepCopy(toRaw(model.endpoints || []))
  modelFormModalOpen.value = true
}

const removeModel = (modelKey) => {
  delete backendSettings.value.models[modelKey]
}

const parseOptionalJson = (value, errorMessage) => {
  if (!value.trim()) {
    return null
  }
  try {
    return JSON.parse(value)
  } catch (error) {
    message.error(errorMessage)
    return null
  }
}

const saveModel = () => {
  const requestMapping = parseOptionalJson(
    modelForm.request_mapping_json,
    t('settings.request_mapping_parse_failed')
  )
  if (modelForm.request_mapping_json.trim() && requestMapping === null) {
    return
  }

  const responseMapping = parseOptionalJson(
    modelForm.response_mapping_json,
    t('settings.response_mapping_parse_failed')
  )
  if (modelForm.response_mapping_json.trim() && responseMapping === null) {
    return
  }

  const nextKey = modelFormStatus.value === 'edit' ? modelEditKey.value : modelEditKey.value.trim()
  if (!nextKey) {
    message.error(t('settings.model_key_empty'))
    return
  }
  if (modelFormStatus.value === 'add' && Object.hasOwn(backendSettings.value.models, nextKey)) {
    message.error(t('settings.embedding_model_duplicate'))
    return
  }

  backendSettings.value.models[nextKey] = {
    ...(backendSettings.value.models[nextKey] || {}),
    id: modelForm.id || nextKey,
    endpoints: deepCopy(toRaw(modelForm.endpoints)),
    enabled: modelForm.enabled,
    protocol: modelForm.protocol || null,
    ...(props.kind === 'embedding' ? { dimensions: modelForm.dimensions || null } : {}),
    request_mapping: requestMapping,
    response_mapping: responseMapping,
  }
  modelFormModalOpen.value = false
  resetModelForm()
}

const draftForTest = computed(() => {
  try {
    const { request_mapping_json, response_mapping_json, ...config } = modelForm
    return {
      ...config,
      id: modelForm.id || modelEditKey.value.trim(),
      protocol: modelForm.protocol || null,
      dimensions: props.kind === 'embedding' ? (modelForm.dimensions || null) : undefined,
      request_mapping: request_mapping_json.trim() ? JSON.parse(request_mapping_json) : null,
      response_mapping: response_mapping_json.trim() ? JSON.parse(response_mapping_json) : null,
    }
  } catch { return null }
})

const cancelModel = () => {
  modelFormModalOpen.value = false
  resetModelForm()
}

const addEndpoint = () => {
  endpointEditIndex.value = null
  endpointModelForm.endpoint_id = ''
  endpointModelForm.model_id = ''
  endpointModelModalOpen.value = true
}

const saveEndpoint = () => {
  if (!endpointModelForm.endpoint_id) {
    return
  }
  const endpoint = endpointModelForm.model_id ? {
      endpoint_id: endpointModelForm.endpoint_id,
      model_id: endpointModelForm.model_id,
    } : endpointModelForm.endpoint_id
  if (endpointEditIndex.value === null) modelForm.endpoints.push(endpoint)
  else modelForm.endpoints.splice(endpointEditIndex.value, 1, endpoint)
  endpointModelModalOpen.value = false
}

const editEndpoint = (index) => {
  endpointEditIndex.value = index
  const endpoint = modelForm.endpoints[index]
  if (typeof endpoint === 'string') {
    endpointModelForm.endpoint_id = endpoint
    endpointModelForm.model_id = ''
  } else {
    endpointModelForm.endpoint_id = endpoint.endpoint_id
    endpointModelForm.model_id = endpoint.model_id || ''
  }
  endpointModelModalOpen.value = true
}

const removeEndpoint = (index) => {
  modelForm.endpoints.splice(index, 1)
}
</script>

<template>
  <a-flex v-if="backendSettings" vertical gap="small">
    <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
      <a-form-item>
        <template #label>
          {{ t('settings.embedding_default_endpoint') }}
          <QuestionPopover :contents="[t('settings.embedding_default_endpoint_tip')]" />
        </template>
        <a-select v-model:value="backendSettings.default_endpoint" :options="endpointOptions" allow-clear />
      </a-form-item>
    </a-form>

    <template v-for="(model, modelKey) in backendSettings.models" :key="modelKey">
      <a-flex gap="small" align="center">
        <span style="flex: 1; overflow-wrap: anywhere">{{ modelKey }}: {{ model.id }}</span>
        <RetrievalModelTest :kind="kind" :backend="backend" :model-key="modelKey" :model-config="model"
          :endpoints="endpoints" :default-endpoint="backendSettings.default_endpoint" />
        <IconButton :text="t('common.edit')" @click="editModel(model, modelKey)"><template #icon><Edit /></template></IconButton>
        <IconButton :text="t('common.delete')" danger @click="removeModel(modelKey)">
          <template #icon>
            <Delete />
          </template>
        </IconButton>
      </a-flex>
    </template>

    <a-typography-paragraph v-if="!Object.keys(backendSettings.models).length" type="secondary">
      {{ t(kind === 'rerank' ? 'settings.rerank_empty_hint' : 'settings.embedding_empty_hint') }}
    </a-typography-paragraph>

    <a-button type="dashed" block @click="addNewModel">
      {{ t('settings.add_model') }}
    </a-button>

    <a-modal v-model:open="modelFormModalOpen"
      :title="modelFormStatus === 'add' ? t('settings.add_model') : t('settings.edit_model')" @ok="saveModel"
      @cancel="cancelModel">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <a-form-item>
          <template #label>
            {{ t('settings.model_key') }}
            <QuestionPopover :contents="[t('settings.model_key_tip')]" />
          </template>
          <a-input v-model:value="modelEditKey" :disabled="modelFormStatus === 'edit'" />
        </a-form-item>

        <a-form-item>
          <template #label>
            {{ t('settings.model_id') }}
            <QuestionPopover :contents="[t('settings.model_id_tip')]" />
          </template>
          <a-input v-model:value="modelForm.id" />
        </a-form-item>

        <a-form-item>
          <template #label>
            {{ t('settings.select_endpoint') }}
            <QuestionPopover :contents="[t('settings.select_endpoint_tip')]" />
          </template>
          <a-flex vertical gap="small">
            <a-list bordered size="small">
              <a-list-item v-for="(endpoint, index) in modelForm.endpoints" :key="index">
                <a-flex justify="space-between" style="width: 100%">
                  <span>
                    {{ typeof endpoint === 'string' ? endpoint : `${endpoint.endpoint_id} (${endpoint.model_id})` }}
                  </span>
                  <a-flex gap="small">
                    <IconButton :text="t('common.edit')" @click="editEndpoint(index)">
                      <template #icon>
                        <Edit />
                      </template>
                    </IconButton>
                    <IconButton :text="t('common.delete')" danger @click="removeEndpoint(index)">
                      <template #icon>
                        <Delete />
                      </template>
                    </IconButton>
                  </a-flex>
                </a-flex>
              </a-list-item>
            </a-list>
            <a-button type="dashed" block @click="addEndpoint">
              {{ t('settings.add_endpoint') }}
            </a-button>
          </a-flex>
        </a-form-item>

        <a-form-item :label="t('common.status')">
          <a-switch v-model:checked="modelForm.enabled" />
        </a-form-item>

        <a-form-item>
          <template #label>
            {{ t(kind === 'rerank' ? 'settings.rerank_protocol' : 'settings.embedding_protocol') }}
            <QuestionPopover :contents="[t(kind === 'rerank' ? 'settings.rerank_protocol_tip' : 'settings.embedding_protocol_tip')]" />
          </template>
          <a-select v-model:value="modelForm.protocol" :options="protocolOptions" allow-clear />
        </a-form-item>

        <a-form-item v-if="kind === 'embedding'">
          <template #label>
            {{ t('settings.embedding_dimensions') }}
            <QuestionPopover :contents="[t('settings.embedding_dimensions_tip')]" />
          </template>
          <a-input-number v-model:value="modelForm.dimensions" :min="1" style="width: 100%" />
        </a-form-item>

        <a-form-item>
          <template #label>
            {{ t('settings.embedding_request_mapping') }}
            <QuestionPopover :contents="[t('settings.embedding_request_mapping_tip')]" />
          </template>
          <a-textarea v-model:value="modelForm.request_mapping_json" :rows="6"
            :placeholder="t('settings.json_object_optional')" />
        </a-form-item>

        <a-form-item>
          <template #label>
            {{ t('settings.embedding_response_mapping') }}
            <QuestionPopover :contents="[t(kind === 'rerank' ? 'settings.rerank_response_mapping_tip' : 'settings.embedding_response_mapping_tip')]" />
          </template>
          <a-textarea v-model:value="modelForm.response_mapping_json" :rows="6"
            :placeholder="t('settings.json_object_optional')" />
        </a-form-item>
      </a-form>
      <RetrievalModelTest v-if="modelFormModalOpen" :kind="kind" :backend="backend" :model-key="modelEditKey"
        :model-config="draftForTest" :endpoints="endpoints" :default-endpoint="backendSettings.default_endpoint" />
    </a-modal>

    <a-modal v-model:open="endpointModelModalOpen" :title="t('settings.endpoint_config')" @ok="saveEndpoint">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <a-form-item :label="t('settings.endpoint')">
          <a-select v-model:value="endpointModelForm.endpoint_id" :options="endpointOptions" />
        </a-form-item>
        <a-form-item>
          <template #label>
            {{ t('settings.model_id') }}
            <QuestionPopover :contents="[t('settings.endpoint_model_id_tip')]" />
          </template>
          <a-input v-model:value="endpointModelForm.model_id" />
        </a-form-item>
      </a-form>
    </a-modal>
  </a-flex>
</template>
