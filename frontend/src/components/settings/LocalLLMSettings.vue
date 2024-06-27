<script setup>
import { ref, reactive, toRaw } from "vue"
import { useI18n } from 'vue-i18n'
import { Delete } from '@icon-park/vue-next'
import { deepCopy } from '@/utils/util'

const { t } = useI18n()

const local_llms = defineModel()

const localLlmsFormStatus = ref()
const localLlmEditIndex = ref()
const localLlmForm = reactive({
  model_family: '',
  api_base: '',
  api_key: '',
  models: [],
})
const localLlmFormRemove = (index) => {
  local_llms.value.splice(index, 1)
}
const localLlmFormEdit = (llm, index) => {
  localLlmForm.model_family = llm.model_family
  localLlmForm.models = deepCopy(toRaw(llm.models))
  localLlmForm.api_base = llm.api_base
  localLlmForm.api_key = llm.api_key
  localLlmsFormStatus.value = 'edit'
  localLlmEditIndex.value = index
}
const localLlmFormSave = () => {
  if (localLlmsFormStatus.value === 'edit') {
    local_llms.value[localLlmEditIndex.value].model_family = localLlmForm.model_family
    local_llms.value[localLlmEditIndex.value].models = deepCopy(toRaw(localLlmForm.models))
    local_llms.value[localLlmEditIndex.value].api_base = localLlmForm.api_base
    local_llms.value[localLlmEditIndex.value].api_key = localLlmForm.api_key
  } else {
    local_llms.value.push(deepCopy(toRaw(localLlmForm)))
  }
  localLlmForm.model_family = ''
  localLlmForm.models = []
  localLlmForm.api_base = ''
  localLlmForm.api_key = ''
  localLlmsFormStatus.value = ''
}

const localLlmModelFormStatus = ref()
const localLlmModelEditIndex = ref()
const localLlmModelFormModalOpen = ref(false)
const localLlmModelForm = reactive({
  model_label: '',
  model_id: '',
  rpm: 60,
  concurrent: 1,
  max_tokens: 8192,
  function_calling: false,
})
const localLlmModelRemove = (index) => {
  localLlmForm.models.splice(index, 1)
}
const localLlmModelEdit = (model, index) => {
  localLlmModelForm.model_id = model.model_id
  localLlmModelForm.model_label = model.model_label
  localLlmModelForm.rpm = model.rpm
  localLlmModelForm.concurrent = model.concurrent
  localLlmModelForm.max_tokens = model.max_tokens
  localLlmModelForm.function_calling = model.function_calling
  localLlmModelFormStatus.value = 'edit'
  localLlmModelEditIndex.value = index
  localLlmModelFormModalOpen.value = true
}
const localLlmModelAdd = () => {
  localLlmModelFormStatus.value = 'add'
  localLlmModelFormModalOpen.value = true
}
const localLlmModelSave = () => {
  localLlmModelFormModalOpen.value = false
  if (localLlmModelFormStatus.value === 'edit') {
    localLlmForm.models[localLlmModelEditIndex.value].model_label = localLlmModelForm.model_label
    localLlmForm.models[localLlmModelEditIndex.value].model_id = localLlmModelForm.model_id
    localLlmForm.models[localLlmModelEditIndex.value].rpm = localLlmModelForm.rpm
    localLlmForm.models[localLlmModelEditIndex.value].concurrent = localLlmModelForm.concurrent
    localLlmForm.models[localLlmModelEditIndex.value].max_tokens = localLlmModelForm.max_tokens
    localLlmForm.models[localLlmModelEditIndex.value].function_calling = localLlmModelForm.function_calling
  } else {
    localLlmForm.models.push(deepCopy(toRaw(localLlmModelForm)))
  }
  localLlmModelForm.model_id = ''
  localLlmModelForm.model_label = ''
  localLlmModelForm.rpm = 60
  localLlmModelForm.concurrent = 1
  localLlmModelForm.max_tokens = 8192
  localLlmModelForm.function_calling = false
}
</script>

<template>
  <a-row :gutter="[12, 12]">
    <a-col :sm="24" :md="8">
      <a-flex vertical gap="small">
        <a-flex v-for="(llmFamily, index) in local_llms" gap="small" align="center">
          <a-button type="text" block @click="localLlmFormEdit(llmFamily, index)">
            {{ llmFamily.model_family }}
          </a-button>
          <a-button type="text" @click="localLlmFormRemove(index)">
            <template #icon>
              <Delete fill="#ff4d4f" />
            </template>
          </a-button>
        </a-flex>
        <a-button type="dashed" block @click="localLlmsFormStatus = 'add'">
          {{ t('settings.add_model_family') }}
        </a-button>
      </a-flex>
    </a-col>
    <a-col v-show="['edit', 'add'].includes(localLlmsFormStatus)" :sm="24" :md="16">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <a-form-item :label="t('settings.model_family')">
          <a-input v-model:value="localLlmForm.model_family" />
        </a-form-item>
        <a-form-item :label="t('settings.model_family_api_base')">
          <a-input v-model:value="localLlmForm.api_base" />
        </a-form-item>
        <a-form-item :label="t('settings.model_family_api_key')">
          <a-input v-model:value="localLlmForm.api_key" />
        </a-form-item>
        <a-form-item :label="t('settings.models')">
          <a-flex vertical gap="small">
            <a-flex v-for="(model, index) in localLlmForm.models" gap="small" align="center">
              <a-button type="text" block @click="localLlmModelEdit(model, index)">
                {{ model.model_label }}
              </a-button>
              <a-button type="text" @click="localLlmModelRemove(index)">
                <template #icon>
                  <Delete fill="#ff4d4f" />
                </template>
              </a-button>
            </a-flex>
            <a-button type="dashed" block @click="localLlmModelAdd">
              {{ t('settings.add_model') }}
            </a-button>
          </a-flex>
          <a-modal v-model:open="localLlmModelFormModalOpen" :title="t('settings.add_model')" @ok="localLlmModelSave">
            <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
              <a-form-item :label="t('settings.model_label')">
                <a-input v-model:value="localLlmModelForm.model_label" />
              </a-form-item>
              <a-form-item :label="t('settings.model_id')">
                <a-input v-model:value="localLlmModelForm.model_id" />
              </a-form-item>
              <a-form-item :label="t('settings.model_rpm')">
                <a-input-number v-model:value="localLlmModelForm.rpm" />
              </a-form-item>
              <a-form-item :label="t('settings.model_concurrent')">
                <a-input-number v-model:value="localLlmModelForm.concurrent" />
              </a-form-item>
              <a-form-item :label="t('settings.model_max_tokens')">
                <a-input-number v-model:value="localLlmModelForm.max_tokens" />
              </a-form-item>
              <a-form-item :label="t('settings.model_function_calling')">
                <a-checkbox v-model:checked="localLlmModelForm.function_calling" />
              </a-form-item>
            </a-form>
          </a-modal>
        </a-form-item>
      </a-form>
      <a-flex justify="flex-end">
        <a-button type="primary" block @click="localLlmFormSave">
          {{ t('settings.save_model_family') }}
        </a-button>
      </a-flex>
    </a-col>
  </a-row>
</template>