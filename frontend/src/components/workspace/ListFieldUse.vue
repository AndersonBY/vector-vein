<script setup>
import { useI18n } from 'vue-i18n'
import { AddOne, ReduceOne } from '@icon-park/vue-next'

const listValue = defineModel()

const { t } = useI18n()

const addItem = () => {
  listValue.value.push('')
}
const updateItem = (newValue, index) => {
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
        <a-input :value="item" @input="updateItem($event.target.value, index)" />
        <ReduceOne @click="deleteItem(index)" />
      </div>
    </a-col>
    <a-col :span="24">
      <a-button type="dashed" style="width: 100%;" @click="addItem">
        <AddOne />
        {{ t('components.nodes.listField.add_item') }}
      </a-button>
    </a-col>
  </a-row>
</template>