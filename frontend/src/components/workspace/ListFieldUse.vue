<script setup>
import { defineComponent } from 'vue'
import { useI18n } from 'vue-i18n'
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons-vue'

defineComponent({
  name: 'ListFieldUse',
})

const listValue = defineModel()

const { t } = useI18n()

const updateItemValue = (newValue, index) => {
  listValue.value[index] = newValue
}
const deleteItem = (index) => {
  listValue.value.splice(index, 1)
}
</script>
<template>
  <a-row type="flex" :gutter="[12, 12]">
    <a-col :span="24" :key="index" v-for="(item, index) in listValue">
      <div style="display: flex; gap: 5px;">
        <a-input :value="item" @input="updateItemValue($event.target.value, index)" />
        <MinusCircleOutlined @click="deleteItem(index)" />
      </div>
    </a-col>
    <a-col :span="24">
      <a-button type="dashed" style="width: 100%;" @click="listValue.push('')">
        <PlusOutlined />
        {{ t('components.nodes.listField.add_item') }}
      </a-button>
    </a-col>
  </a-row>
</template>