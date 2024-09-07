<script setup>
import { watch, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Handle, Position } from '@vue-flow/core'
import { CloseOne, Edit, PreviewOpen, PreviewCloseOne, Info } from '@icon-park/vue-next'
import TemperatureInput from '@/components/nodes/TemperatureInput.vue'

const props = defineProps({
  name: {
    type: String,
    required: true,
  },
  required: {
    type: Boolean,
    default: false,
  },
  type: {
    type: String,
    required: true,
  },
  nameOnly: {
    type: Boolean,
    default: false,
  },
  deletable: {
    type: Boolean,
    default: false,
  },
  editable: {
    type: Boolean,
    default: false,
  },
  style: {
    type: Object,
    default: () => ({}),
  },
  data: {
    type: Object,
    default: () => ({}),
  },
})

const emit = defineEmits(['delete', 'update:data', 'edit'])

const { t } = useI18n()

const innerData = ref(props.data)
const id = ref(innerData.value.id || innerData.value.name)

const debug = innerData.value.debug
const showDebugDetails = ref(false)
const toggleDebugDetails = () => {
  showDebugDetails.value = !showDebugDetails.value
}

const toggleShowValue = () => {
  innerData.value.show = !innerData.value.show
  emit('update:data', innerData.value)
}
watch(() => props.data, (newValue) => {
  innerData.value = newValue
  id.value = newValue.id || newValue.name
}, { deep: true })

const removeField = () => {
  emit('delete', id)
}

const editField = () => {
  emit('edit', id)
}
</script>
<template>
  <div :class="['template-item-field', props.type == 'source' ? 'template-item-output-field' : '']"
    :style="props.style">
    <div class="template-item-field-text">
      <a-tooltip v-if="debug" :title="t('components.nodes.baseField.show_field_info')">
        <a-button type="text" size="small" @click="toggleDebugDetails">
          <template #icon>
            <Info :fill="showDebugDetails ? '#1890ff' : '#8c8c8c'" />
          </template>
        </a-button>
        <a-modal v-model:open="showDebugDetails" :footer="null">
          <a-descriptions :title="t('components.nodes.baseField.field_info')" :column="1">
            <a-descriptions-item :label="t('components.nodes.baseField.data_type')">{{ typeof innerData.value
              }}</a-descriptions-item>
            <a-descriptions-item :label="t('components.nodes.baseField.field_value')">{{ innerData.value
              }}</a-descriptions-item>
          </a-descriptions>
        </a-modal>
      </a-tooltip>
      <a-typography-text class="field-name">
        {{ props.name }}
      </a-typography-text>
      <a-typography-text type="danger" v-if="props.required"> *</a-typography-text>
      <a-button v-if="editable" type="text" size="small" @click="editField">
        <template #icon>
          <Edit />
        </template>
      </a-button>
      <slot name="inline"></slot>
      <template v-if="!$slots.inline && !innerData.is_output">
        <a-checkbox v-if="innerData.field_type == 'checkbox'" v-model:checked="innerData.value">
        </a-checkbox>
      </template>
      <div v-if="props.type == 'target'" class="show-in-use-interface-checkbox"
        :class="{ 'always-show': innerData.show }">
        <a-tooltip :title="t('components.nodes.baseField.show_in_use_interface')">
          <a-button type="text" size="small" @click="toggleShowValue">
            <template #icon>
              <PreviewOpen v-if="innerData.show" fill="#28c5e5" />
              <PreviewCloseOne v-else fill="#28c5e5" />
            </template>
          </a-button>
        </a-tooltip>
      </div>
      <a-button type="text" size="small" class="delete-field-button" @click="removeField()" v-if="props.deletable">
        <template #icon>
          <CloseOne fill="#ff4d4f" />
        </template>
      </a-button>
    </div>
    <Handle v-if="nameOnly" :class="['handle', `${props.type}-handle`]" :id="id" :type="props.type"
      :position="props.type == 'target' ? Position.Left : Position.Right" :connectable-start="props.type != 'target'"
      :connectable-end="props.type == 'target'" />
    <div style="position: relative;">
      <div class="template-item-field-content">
        <slot>
        </slot>
        <template v-if="!$slots.default && !innerData.is_output">
          <a-select v-if="innerData.field_type == 'select'" v-model:value="innerData.value" class="nodrag"
            :options="innerData.options" style="width: 100%;" />
          <a-textarea v-model:value="innerData.value" class="nodrag" :autoSize="{ minRows: 2, maxRows: 30 }"
            :showCount="true" :placeholder="innerData.placeholder" :maxlength="innerData.max_length ?? null"
            v-else-if="innerData.field_type == 'textarea'" />
          <a-input v-model:value="innerData.value" class="nodrag" :placeholder="innerData.placeholder"
            :maxlength="innerData.max_length ?? null" v-else-if="innerData.field_type == 'input'" />
          <a-input-number v-model:value="innerData.value" class="nodrag" :placeholder="innerData.placeholder"
            :max="innerData.max ?? null" :min="innerData.min ?? null" v-else-if="innerData.field_type == 'number'"
            style="width: 100%;" />
          <a-radio-group class="nodrag" option-type="button" v-model:value="innerData.value"
            :options="innerData.options" v-else-if="innerData.field_type == 'radio'" />
          <TemperatureInput class="nodrag" v-else-if="innerData.field_type == 'temperature'"
            v-model="innerData.value" />
        </template>
      </div>
      <template v-if="props.type == 'target'">
        <Handle v-if="!nameOnly" :class="['handle', 'target-handle']" :id="id" type="target" :position="Position.Left"
          :connectable-start="false" :connectable-end="true" />
        <Handle v-if="!nameOnly" :class="['handle', 'source-handle']" :id="id" type="source" :position="Position.Right"
          :connectable-start="true" :connectable-end="false" />
      </template>
      <template v-else>
        <Handle v-if="!nameOnly" :class="['handle', `${props.type}-handle`]" :id="id" :type="props.type"
          :position="Position.Right" :connectable-start="true" :connectable-end="false" />
      </template>
    </div>
  </div>
</template>

<style scoped>
.template-item-field {
  padding: 10px 0;
  width: 100%;
  height: 100%;
  position: relative;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.template-item-field-text {
  position: relative;
  padding: 0 10px;
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: 5px;
}

.template-item-field .show-in-use-interface-checkbox {
  flex-grow: 1;
  display: flex;
  justify-content: flex-end;
  opacity: 0;
}

.template-item-field:hover .show-in-use-interface-checkbox {
  opacity: 1;
  transition: opacity .3s;
}

.template-item-field .show-in-use-interface-checkbox.always-show {
  opacity: 1;
}

.template-item-field-content {
  position: relative;
  padding: 0 10px;
}

.template-item-field .delete-field-button {
  opacity: 0;
  transition: opacity .2s ease-in-out;
}

.template-item-field:hover .delete-field-button {
  opacity: 1;
}

.field-name {
  font-weight: 600;
  transition: color .3s;
  color: var(--site-light-text-color)
}
</style>