<script setup>
import { computed, reactive, ref, toRaw } from "vue"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { Edit, Delete, Up, Down } from '@/icons'
import QuestionPopover from "@/components/QuestionPopover.vue"
import { deepCopy } from '@/utils/util'
import ModelEndpointTest from '@/components/settings/ModelEndpointTest.vue'

const props = defineProps({
  backend: { type: String, default: 'local' },
  active: { type: Boolean, default: true },
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
  model_id: '',
  priority: 1,
})
const endpointEditIndex = ref(null)
const endpointError = ref('')
const endpointPriority = endpoint => typeof endpoint === 'string' ? 1 : endpoint.priority ?? 1
const sortEndpoints = () => modelForm.endpoints.sort((left, right) => endpointPriority(left) - endpointPriority(right))
const moveEndpoint = (index, direction) => {
  const next = index + direction
  if (!modelForm.endpoints[next] || endpointPriority(modelForm.endpoints[index]) !== endpointPriority(modelForm.endpoints[next])) return
  const moved = modelForm.endpoints.splice(index, 1)[0]
  modelForm.endpoints.splice(next, 0, moved)
}

const endpointModelModalOpen = ref(false)
const testEndpoint = computed(() => props.endpoints.find(endpoint => endpoint.id === endpointModelForm.endpoint_id) || null)

const addNewModel = () => {
  resetModelForm()
  modelEditIndex.value = null
  modelFormStatus.value = 'add'
  modelFormModalOpen.value = true
}

const editModel = (model, index) => {
  resetModelForm()
  modelFormStatus.value = 'edit'
  modelEditIndex.value = index
  Object.assign(modelForm, deepCopy(toRaw(model)))
  sortEndpoints()
  modelFormModalOpen.value = true
}

const removeModel = (index) => {
  delete llmSettings.value.models[index]
}

const saveModel = () => {
  if (!modelEditIndex.value?.trim() || !modelForm.id?.trim()) {
    message.error(t('settings.model_key_id_required'))
    return
  }
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
  Object.keys(modelForm).forEach(key => delete modelForm[key])
  endpointModelModalOpen.value = false
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

const cancelEndpoint = () => {
  endpointModelModalOpen.value = false
  endpointEditIndex.value = null
  endpointError.value = ''
  Object.assign(endpointModelForm, { endpoint_id: '', model_id: '', priority: 1 })
}

const addEndpoint = () => {
  cancelEndpoint()
  endpointModelModalOpen.value = true
}

const saveEndpoint = () => {
  if (!testEndpoint.value) {
    endpointError.value = t('settings.select_endpoint')
    return
  }
  if (!(endpointModelForm.model_id || modelForm.id)?.trim()) {
    endpointError.value = t('settings.model_test_input_required')
    return
  }
  if (!Number.isInteger(endpointModelForm.priority) || endpointModelForm.priority < 1) {
    endpointError.value = t('settings.endpoint_priority_invalid')
    return
  }
  const original = modelForm.endpoints[endpointEditIndex.value]
  const endpoint = {
    ...(typeof original === 'object' ? deepCopy(toRaw(original)) : {}),
    endpoint_id: endpointModelForm.endpoint_id,
    priority: endpointModelForm.priority,
  }
  if (endpointModelForm.model_id.trim()) endpoint.model_id = endpointModelForm.model_id.trim()
  else delete endpoint.model_id
  if (endpointEditIndex.value === null) modelForm.endpoints.push(endpoint)
  else modelForm.endpoints.splice(endpointEditIndex.value, 1, endpoint)
  sortEndpoints()
  cancelEndpoint()
}

const removeEndpoint = index => modelForm.endpoints.splice(index, 1)

const editEndpoint = index => {
  cancelEndpoint()
  endpointEditIndex.value = index
  const endpoint = modelForm.endpoints[index]
  Object.assign(endpointModelForm, {
    endpoint_id: typeof endpoint === 'string' ? endpoint : endpoint.endpoint_id,
    model_id: typeof endpoint === 'string' ? '' : endpoint.model_id || '',
    priority: endpointPriority(endpoint),
  })
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
                    {{ typeof endpoint === 'string' ? endpoint : `${endpoint.endpoint_id}${endpoint.model_id ? ` (${endpoint.model_id})` : ''}` }}
                    <span> · {{ t('settings.endpoint_priority') }}: {{ endpointPriority(endpoint) }}</span>
                  </span>
                  <a-flex gap="small">
                    <a-button type="text" size="small" :aria-label="t('settings.endpoint_move_up')"
                      :disabled="index === 0 || endpointPriority(endpoint) !== endpointPriority(modelForm.endpoints[index - 1])"
                      @click="moveEndpoint(index, -1)"><Up /></a-button>
                    <a-button type="text" size="small" :aria-label="t('settings.endpoint_move_down')"
                      :disabled="index === modelForm.endpoints.length - 1 || endpointPriority(endpoint) !== endpointPriority(modelForm.endpoints[index + 1])"
                      @click="moveEndpoint(index, 1)"><Down /></a-button>
                    <a-tooltip :title="t('common.edit')">
                      <a-button type="text" size="small" :aria-label="t('common.edit')" @click="editEndpoint(index)">
                        <template #icon>
                          <Edit />
                        </template>
                      </a-button>
                    </a-tooltip>
                    <a-tooltip :title="t('common.delete')">
                      <a-button type="text" size="small" danger :aria-label="t('common.delete')" @click="removeEndpoint(index)">
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
    <a-modal v-model:open="endpointModelModalOpen" :title="t('settings.endpoint_config')" @ok="saveEndpoint" @cancel="cancelEndpoint">
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
          <a-input v-model:value="endpointModelForm.model_id" :placeholder="modelForm.id" />
        </a-form-item>

        <a-form-item :label="t('settings.endpoint_priority')" :extra="t('settings.endpoint_priority_tip')">
          <a-input-number v-model:value="endpointModelForm.priority" :min="1" :precision="0" />
        </a-form-item>
        <p v-if="endpointError" role="alert">{{ endpointError }}</p>
      </a-form>
      <ModelEndpointTest compact :endpoint="testEndpoint" :backend="backend"
        :model-id="endpointModelForm.model_id || modelForm.id"
        :active="active && modelFormModalOpen && endpointModelModalOpen" />
    </a-modal>
  </a-flex>
</template>
