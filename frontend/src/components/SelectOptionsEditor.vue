<script setup>
import { ref, reactive, toRaw } from "vue"
import { Delete } from '@icon-park/vue-next'
import { useI18n } from 'vue-i18n'
import { deepCopy } from '@/utils/util'

const props = defineProps({
  labelName: {
    type: String,
    default: 'Label',
  },
  valueName: {
    type: String,
    default: 'Value',
  },
  labelKey: {
    type: String,
    default: 'label',
  },
  valueKey: {
    type: String,
    default: 'value',
  },
})

const { t } = useI18n()

const options = defineModel()

const editIndex = ref()
const formStatus = ref()
const formModalOpen = ref(false)
const form = reactive({
  [props.labelKey]: '',
  [props.valueKey]: '',
})

const remove = (index) => {
  options.value.splice(index, 1)
}

const edit = (option, index) => {
  form[props.labelKey] = option[props.labelKey]
  form[props.valueKey] = option[props.valueKey]
  formStatus.value = 'edit'
  editIndex.value = index
  formModalOpen.value = true
}

const add = () => {
  formStatus.value = 'add'
  formModalOpen.value = true
}

const save = () => {
  formModalOpen.value = false
  if (formStatus.value === 'edit') {
    options.value[editIndex.value][props.labelKey] = form[props.labelKey]
    options.value[editIndex.value][props.valueKey] = form[props.valueKey]
  } else {
    options.value.push(deepCopy(toRaw(form)))
  }
  form[props.labelKey] = ''
  form[props.valueKey] = ''
}
</script>

<template>
  <a-flex vertical gap="small">
    <a-flex v-for="(option, index) in options" gap="small" align="center">
      <a-button type="text" block @click="edit(option, index)">
        {{ option[labelKey] }}
      </a-button>
      <a-button type="text" @click="remove(index)">
        <template #icon>
          <Delete fill="#ff4d4f" />
        </template>
      </a-button>
    </a-flex>
    <a-button type="dashed" block @click="add">
      {{ t('common.add') }}
    </a-button>
  </a-flex>
  <a-modal v-model:open="formModalOpen" :title="t('common.add')" @ok="save">
    <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
      <a-form-item :label="labelName">
        <a-input v-model:value="form[labelKey]" />
      </a-form-item>
      <a-form-item :label="valueName">
        <a-input v-model:value="form[valueKey]" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>