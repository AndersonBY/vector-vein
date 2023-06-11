<script setup>
import { defineComponent, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { EditOutlined } from '@ant-design/icons-vue'

defineComponent({
  name: 'TemplateEditorModal',
})

const props = defineProps({
  fields: {
    type: Object,
    required: true,
    default: {},
  },
  open: {
    type: Boolean,
    required: true,
    default: false,
  },
  template: {
    type: String,
    required: true,
    default: '',
  }
})

const { t } = useI18n()
const emit = defineEmits(['update:open', 'update:template'])
let innerOpen = ref(props.open)
let innerTemplate = ref(props.template)
const save = () => {
  innerOpen.value = false
  emit('update:open', innerOpen.value)
  emit('update:template', innerTemplate.value)
}
const cancel = () => {
  innerOpen.value = false
  emit('update:open', innerOpen.value)
}
watch(() => props.open, (newValue) => {
  innerOpen.value = newValue
})
watch(() => props.template, (newValue) => {
  innerTemplate.value = newValue
})

const handleDragStart = (event, field) => {
  event.dataTransfer.setData('text/plain', `{{${field}}}`)
}
</script>

<template>
  <a-modal :open="innerOpen" width="80vw" @ok="save" @cancel="cancel" style="max-width: 1280px; width: 80vw;">
    <template #title>
      <EditOutlined />
      {{ t('components.templateEditorModal.title') }}
    </template>
    <a-row :gutter="16">
      <a-col :span="6">
        <a-card>
          <template #title>
            {{ t('components.templateEditorModal.variable_fields') }}
            <a-typography-text type="secondary" style="font-size: 12px; font-weight: normal;">
              {{ t('components.templateEditorModal.drag_to_insert') }}
            </a-typography-text>
          </template>
          <a-space direction="vertical" style="width: 100%">
            <template v-for="field in Object.keys(props.fields)" :key="field">
              <a-button block draggable="true" @dragstart="handleDragStart($event, field)"
                v-if="!['template', 'output'].includes(field)">
                {{ field }}
              </a-button>
            </template>
          </a-space>
        </a-card>
      </a-col>
      <a-col :span="18">
        <a-card :title="t('components.templateEditorModal.template')">
          <a-textarea v-model:value="innerTemplate" :rows="20" />
        </a-card>
      </a-col>
    </a-row>
  </a-modal>
</template>