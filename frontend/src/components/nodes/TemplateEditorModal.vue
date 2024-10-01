<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Edit, BookmarkOne } from '@icon-park/vue-next'

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
    type: [String, Array],
    required: true,
    default: '',
  }
})

const { t } = useI18n()
const emit = defineEmits(['update:open', 'update:template'])
let innerOpen = ref(props.open)
let innerTemplate = ref(props.template)
const textareaRef = ref(null)

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

const insertVariable = (field) => {
  if (textareaRef.value) {
    const textarea = textareaRef.value.$el.querySelector('textarea');
    const startPos = textarea.selectionStart;
    const endPos = textarea.selectionEnd;
    const beforeInsert = innerTemplate.value.slice(0, startPos);
    const afterInsert = innerTemplate.value.slice(endPos);
    innerTemplate.value = `${beforeInsert}{{${field}}}${afterInsert}`;
    setTimeout(() => {
      textarea.setSelectionRange(startPos + `{{${field}}}`.length, startPos + `{{${field}}}`.length);
      textarea.focus();
    }, 0);
  }
}

const formatTemplate = () => {
  const formattedFields = Object.keys(props.fields)
    .filter(field => !['template', 'output'].includes(field))
    .map(field => `<${field}>\n{{${field}}}\n</${field}>`)
    .join('\n\n');

  if (typeof innerTemplate.value === 'string') {
    innerTemplate.value = formattedFields;
  } else if (Array.isArray(innerTemplate.value) && innerTemplate.value.length > 0) {
    innerTemplate.value[0] = formattedFields;
  }
}
</script>

<template>
  <a-modal class="template-editor" :open="innerOpen" width="80vw" @ok="save" @cancel="cancel"
    style="max-width: 1280px; width: 80vw;">
    <template #title>
      <Edit />
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
              <a-button v-if="!['template', 'output'].includes(field)" class="template-variable" block draggable="true"
                @dragstart="handleDragStart($event, field)" @click="insertVariable(field)">
                {{ field }}
              </a-button>
            </template>
          </a-space>
        </a-card>
      </a-col>
      <a-col :span="18">
        <a-card :title="t('components.templateEditorModal.template')">
          <template #extra>
            <a-tooltip :title="t('components.templateEditorModal.format_fields_tip')">
              <a-button @click="formatTemplate">
                {{ t('components.templateEditorModal.format_fields') }}
              </a-button>
            </a-tooltip>
          </template>
          <template v-if="typeof props.template === 'string'">
            <a-textarea ref="textareaRef" class="template-textarea" v-model:value="innerTemplate" :rows="20"
              showCount />
          </template>
          <template v-else>
            <a-tabs>
              <a-tab-pane v-for="(tab, index) in props.template" :key="index">
                <template #tab>
                  <BookmarkOne /> {{ index }}
                </template>
                <a-textarea class="template-textarea" v-model:value="innerTemplate[index]" :rows="20" showCount />
              </a-tab-pane>
            </a-tabs>
          </template>
        </a-card>
      </a-col>
    </a-row>
  </a-modal>
</template>