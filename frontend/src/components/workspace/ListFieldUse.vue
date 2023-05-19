<script setup>
import { defineComponent, defineEmits, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons-vue'

defineComponent({
  name: 'ListFieldUse',
})

const props = defineProps({
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
</template>