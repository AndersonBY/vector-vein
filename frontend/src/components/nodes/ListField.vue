<script setup>
import { defineComponent, defineEmits, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons-vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'ListField',
})

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
  value: {
    type: Array,
    required: true
  },
})

const { t } = useI18n()

const emit = defineEmits(['delete', 'update:value'])
let innerValue = props.value
const updateItemValue = (newValue, index) => {
  innerValue[index] = newValue
  emit('update:value', innerValue)
}
const deleteItem = (index) => {
  innerValue.splice(index, 1)
  emit('update:value', innerValue)
}
watch(() => props.value, (newValue) => {
  innerValue = newValue
})
</script>
<template>
  <BaseField :id="props.id" :name="props.name" :required="props.required" :type="props.type" :nameOnly="props.nameOnly"
    :deletable="props.deletable" :style="props.style" @delete="emit('delete', props.id)">
    <a-row type="flex" :gutter="[12, 12]">
      <a-col :span="24" :key="index" v-for="(item, index) in innerValue">
        <div style="display: flex; gap: 5px;">
          <a-input :value="item" @input="updateItemValue($event.target.value, index)" />
          <MinusCircleOutlined @click="deleteItem(index)" />
        </div>
      </a-col>
      <a-col :span="24">
        <a-button type="dashed" style="width: 100%;" @click="innerValue.push('')">
          <PlusOutlined />
          {{ t('components.nodes.listField.add_item') }}
        </a-button>
      </a-col>
    </a-row>
  </BaseField>
</template>