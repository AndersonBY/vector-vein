<script setup>
import { watch, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { Handle, Position } from '@vue-flow/core'
import { CloseOne } from '@icon-park/vue-next'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
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
  style: {
    type: Object,
    default: () => ({}),
  },
  show: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['delete', 'update:show'])

const { t } = useI18n()

const innerShow = ref(props.show)
const updateShowValue = (event) => {
  innerShow.value = event.target.checked
  emit('update:show', innerShow.value)
}
watch(() => props.show, (newValue) => {
  innerShow.value = newValue
})

const removeField = () => {
  emit('delete', props.id)
}

const getHandleStyle = (handleType) => ({
  borderColor: handleType == 'target' ? '#94d574' : '#e8de7f',
  borderWidth: '2px',
  backgroundColor: '#fff',
  width: '10px',
  height: '10px',
})
</script>
<template>
  <div :class="['template-item-field', props.type == 'source' ? 'template-item-output-field' : '']" :style="props.style">
    <div class="template-item-field-text">
      <a-typography-text>
        {{ props.name }}
      </a-typography-text>
      <a-typography-text type="danger" v-if="props.required"> *</a-typography-text>
      <slot name="inline"></slot>
      <div class="show-in-use-interface-checkbox" v-if="props.type == 'target'">
        <a-tooltip :title="t('components.nodes.baseField.show_in_use_interface')">
          <a-checkbox class="field-show-checkbox" :checked="innerShow" @change="updateShowValue">
            <a-typography-text type="secondary">
              {{ t('components.nodes.baseField.show') }}
            </a-typography-text>
          </a-checkbox>
        </a-tooltip>
      </div>
      <a-typography-link type="danger" class="delete-field-button" @click="removeField()" v-if="props.deletable">
        <CloseOne style="float: right;" />
      </a-typography-link>
    </div>
    <Handle :style="getHandleStyle(props.type)" :id="id" :type="props.type"
      :position="props.type == 'target' ? Position.Left : Position.Right" :connectable-start="props.type != 'target'"
      :connectable-end="props.type == 'target'" v-if="nameOnly" />
    <div style="position: relative;">
      <div class="template-item-field-content">
        <slot>
        </slot>
      </div>
      <template v-if="props.type == 'target'">
        <Handle :style="getHandleStyle('target')" :id="id" type="target" :position="Position.Left"
          :connectable-start="false" :connectable-end="true" v-if="!nameOnly" />
        <Handle :style="getHandleStyle('source')" :id="id" type="source" :position="Position.Right"
          :connectable-start="true" :connectable-end="false" v-if="!nameOnly" />
      </template>
      <template v-else>
        <Handle :style="getHandleStyle(props.type)" :id="id" :type="props.type" :position="Position.Right"
          :connectable-start="true" :connectable-end="false" v-if="!nameOnly" />
      </template>
    </div>
  </div>
</template>
<style scoped>
.template-item-field {
  background: #f8f8f8;
  padding: 10px 0;
  width: 100%;
  height: 100%;
  position: relative;
}

.template-item-output-field {
  background-color: #28c5e5 !important;
}

.template-item-field-text {
  position: relative;
  padding: 0 10px;
  display: flex;
  justify-content: flex-end;
  gap: 5px;
}

.template-item-field-text .show-in-use-interface-checkbox {
  flex-grow: 1;
  display: flex;
  justify-content: flex-end;
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
</style>