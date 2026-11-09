<script setup>
import IconButton from '@/components/IconButton.vue'

import { useI18n } from 'vue-i18n'
import { AddOne, ReduceOne } from '@/icons'

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
  <a-flex vertical gap="small">
    <a-flex :key="index" v-for="(item, index) in listValue" align="center" gap="small">
      <a-input :value="item" @input="updateItem($event.target.value, index)" />
      <IconButton :text="t('common.delete')" @click="deleteItem(index)">
        <template #icon>
          <ReduceOne />
        </template>
      </IconButton>
    </a-flex>
    <IconButton type="dashed" :text="t('components.nodes.listField.add_item')" @click="addItem">
      <template #icon><AddOne /></template>
    </IconButton>
  </a-flex>
</template>