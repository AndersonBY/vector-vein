<script setup>
import { computed, reactive, ref, toRaw } from "vue"
import { useI18n } from 'vue-i18n'
import { Delete } from '@icon-park/vue-next'
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
      :title="modelFormStatus === 'add' ? t('settings.add_model') : t('settings.edit_model')" @ok="saveModel">
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
        <a-form-item :label="t('settings.select_endpoint')">
          <a-select v-model:value="modelForm.endpoints" :options="endpointOptions" style="width: 100%;" mode="multiple">
            <template #placeholder>
              <span>{{ t('settings.select_endpoint') }}</span>
            </template>
          </a-select>
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
  </a-flex>
</template>
