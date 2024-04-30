<script setup>
import { watch, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { AddOne, ReduceOne } from '@icon-park/vue-next'
import BaseField from '@/components/nodes/BaseField.vue'

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
  style: {
    type: Object,
    default: () => ({}),
  },
  data: {
    type: Object,
    default: () => ({}),
  },
})

const { t } = useI18n()

const emit = defineEmits(['delete', 'update:data'])

const innerData = ref(props.data)
const id = innerData.value.name
watch(() => props.data, (newValue) => {
  innerData.value = newValue
}, { deep: true })

const updateItemValue = (newValue, index) => {
  innerData.value.value[index] = newValue
  emit('update:data', innerData.value)
}
const deleteItem = (index) => {
  innerData.value.value.splice(index, 1)
  emit('update:data', innerData.value)
}
</script>
<template>
  <BaseField :name="props.name" :required="props.required" :type="props.type" :nameOnly="props.nameOnly"
    :deletable="props.deletable" :style="props.style" v-model:data="innerData" @delete="emit('delete', id)">
    <a-flex vertical gap="small">
      <a-flex :key="index" v-for="(item, index) in innerData.value" align="center" gap="small">
        <a-input :value="item" @input="updateItemValue($event.target.value, index)" />
        <a-button type="text" @click="deleteItem(index)">
          <template #icon>
            <ReduceOne />
          </template>
        </a-button>
      </a-flex>
      <a-button type="dashed" style="width: 100%;" @click="innerData.value.push('')">
        <AddOne />
        {{ t('components.nodes.listField.add_item') }}
      </a-button>
    </a-flex>
  </BaseField>
</template>