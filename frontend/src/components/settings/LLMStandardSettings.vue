<script setup>
import { computed, reactive, ref, toRaw } from "vue"
import { useI18n } from 'vue-i18n'
import { Edit, Delete } from '@icon-park/vue-next'
import QuestionPopover from "@/components/QuestionPopover.vue"
import { deepCopy } from '@/utils/util'

const props = defineProps({
  endpoints: {
    type: Array,
    default: () => []
  },
  filterModels: {
    type: [Array, null],
    default: null
  }
})

const emit = defineEmits(['addModel'])

const { t } = useI18n()

const llmSettings = defineModel()
const endpointOptions = computed(() => {
  return props.endpoints.map((endpoint) => ({
    value: endpoint.id,
    label: endpoint.id
  }))
})

const modelFormModalOpen = ref(false)
const modelFormStatus = ref('')
const modelEditIndex = ref(null)
const modelForm = reactive({
  id: '',
  endpoints: [],
  function_call_available: false,
  response_format_available: false,
  native_multimodal: false,
  context_length: 32768,
  max_output_tokens: null
})

const endpointModelForm = reactive({
  endpoint_id: '',
  model_id: ''
})

const endpointModelModalOpen = ref(false)

const addNewModel = () => {
  modelFormStatus.value = 'add'
  modelFormModalOpen.value = true
}

const editModel = (model, index) => {
  modelFormStatus.value = 'edit'
  modelEditIndex.value = index
  Object.assign(modelForm, deepCopy(toRaw(model)))
  modelFormModalOpen.value = true
}

const removeModel = (index) => {
  delete llmSettings.value.models[index]
}

const saveModel = () => {
  if (modelFormStatus.value === 'add') {
    llmSettings.value.models[modelEditIndex.value] = deepCopy(toRaw(modelForm))
    emit('addModel', modelEditIndex.value)
  } else {
    Object.assign(llmSettings.value.models[modelEditIndex.value], deepCopy(toRaw(modelForm)))
  }
  modelFormModalOpen.value = false
  resetModelForm()
}

const resetModelForm = () => {
  Object.assign(modelForm, {
    id: '',
    endpoints: [],
    function_call_available: false,
    response_format_available: false,
    native_multimodal: false,
    context_length: 32768,
    max_output_tokens: null
  })
}

const cancelModel = () => {
  modelFormModalOpen.value = false
  resetModelForm()
}

const addEndpoint = () => {
  endpointModelForm.endpoint_id = ''
  endpointModelForm.model_id = modelEditIndex.value
  endpointModelModalOpen.value = true
}

const saveEndpoint = () => {
  if (endpointModelForm.model_id) {
    modelForm.endpoints.push({
      endpoint_id: endpointModelForm.endpoint_id,
      model_id: endpointModelForm.model_id
    })
  } else {
    modelForm.endpoints.push(endpointModelForm.endpoint_id)
  }
  endpointModelModalOpen.value = false
}

const removeEndpoint = (index) => {
  modelForm.endpoints.splice(index, 1)
}

const editEndpoint = (index) => {
  const endpoint = modelForm.endpoints[index]
  if (typeof endpoint === 'string') {
    endpointModelForm.endpoint_id = endpoint
    endpointModelForm.model_id = ''
  } else {
    endpointModelForm.endpoint_id = endpoint.endpoint_id
    endpointModelForm.model_id = endpoint.model_id
  }
  endpointModelModalOpen.value = true
}
</script>

<template>
  <a-flex vertical gap="small">
    <template v-for="(model, index) in llmSettings.models" :key="index">
      <a-flex
        v-if="filterModels === null || (filterModels.length !== null && (filterModels.length > 0 && filterModels.includes(model.id)))"
        gap="small" align="center">
        <a-button type="text" block @click="editModel(model, index)">
          {{ index }}: {{ model.id }}
        </a-button>
        <a-button type="text" @click="removeModel(index)">
          <template #icon>
            <Delete fill="#ff4d4f" />
          </template>
        </a-button>
      </a-flex>
    </template>
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
          <a-input :disabled="modelFormStatus === 'edit'" v-model:value="modelEditIndex" />
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
                    <a-tooltip :title="t('common.edit')">
                      <a-button type="text" size="small" @click="editEndpoint(index)">
                        <template #icon>
                          <Edit />
                        </template>
                      </a-button>
                    </a-tooltip>
                    <a-tooltip :title="t('common.delete')">
                      <a-button type="text" size="small" danger @click="removeEndpoint(index)">
                        <template #icon>
                          <Delete />
                        </template>
                      </a-button>
                    </a-tooltip>
                  </a-flex>
                </a-flex>
              </a-list-item>
            </a-list>
            <a-button type="dashed" block @click="addEndpoint">
              {{ t('settings.add_endpoint') }}
            </a-button>
          </a-flex>
        </a-form-item>
        <a-form-item :label="t('settings.model_function_calling')">
          <a-switch v-model:checked="modelForm.function_call_available" />
        </a-form-item>
        <a-form-item :label="t('settings.model_response_format_available')">
          <a-switch v-model:checked="modelForm.response_format_available" />
        </a-form-item>
        <a-form-item :label="t('settings.model_native_multimodal')">
          <a-switch v-model:checked="modelForm.native_multimodal" />
        </a-form-item>
        <a-form-item :label="t('settings.model_max_tokens')">
          <a-input-number v-model:value="modelForm.context_length" />
        </a-form-item>
        <a-form-item :label="t('settings.max_output_tokens')">
          <a-input-number v-model:value="modelForm.max_output_tokens" />
        </a-form-item>
      </a-form>
    </a-modal>
    <a-modal v-model:open="endpointModelModalOpen" :title="t('settings.endpoint_config')" @ok="saveEndpoint">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <a-form-item :label="t('settings.endpoint')">
          <a-select v-model:value="endpointModelForm.endpoint_id" :options="endpointOptions">
            <template #placeholder>
              <span>{{ t('settings.select_endpoint') }}</span>
            </template>
          </a-select>
        </a-form-item>
        <a-form-item>
          <template #label>
            {{ t('settings.model_id') }}
            <QuestionPopover :contents="[t('settings.endpoint_model_id_tip')]" />
          </template>
          <a-input v-model:value="endpointModelForm.model_id" placeholder="可选，留空则使用默认模型" />
        </a-form-item>

      </a-form>
    </a-modal>
  </a-flex>
</template>
