<script setup>
import { AddOne, ReduceOne } from '@icon-park/vue-next'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const list = defineModel()
const deleteItem = (index) => {
  list.value.splice(index, 1)
}
const updateItem = (value, index) => {
  list.value[index] = value
}
</script>

<template>
  <a-flex vertical gap="small">
    <div :key="index" v-for="(item, index) in list">
      <a-flex gap="small" align="center">
        <a-input :value="item" @input="updateItem($event.target.value, index)" />
        <a-button type="text" size="small" @click="deleteItem(index)">
          <template #icon>
            <ReduceOne />
          </template>
        </a-button>
      </a-flex>
    </div>
    <div>
      <a-button type="dashed" style="width: 100%;" @click="list.push('')">
        <template #icon>
          <AddOne />
        </template>
        {{ t('common.add') }}
      </a-button>
    </div>
  </a-flex>
</template>