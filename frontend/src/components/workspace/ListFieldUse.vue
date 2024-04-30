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
  <a-flex vertical gap="small">
    <a-flex :key="index" v-for="(item, index) in listValue" align="center" gap="small">
      <a-input :value="item" @input="updateItem($event.target.value, index)" />
      <a-button type="text" @click="deleteItem(index)">
        <template #icon>
          <ReduceOne />
        </template>
      </a-button>
    </a-flex>
    <a-button type="dashed" style="width: 100%;" @click="addItem">
      <AddOne />
      {{ t('components.nodes.listField.add_item') }}
    </a-button>
  </a-flex>
</template>