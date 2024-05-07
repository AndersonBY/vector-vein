<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  collapse: {
    type: Boolean,
    required: false,
    default: true,
  },
  name: {
    type: [String, undefined],
    required: false,
    default: undefined,
  },
})

const emit = defineEmits(['collapseChanged'])

const { t } = useI18n()
const name = props.name || t('common.more_settings')
const activeKey = ref(props.collapse ? [] : [name])

const onChange = (key) => {
  if (key.length > 0) {
    emit('collapseChanged', { id: props.id, collpased: false })
  } else {
    emit('collapseChanged', { id: props.id, collpased: true })
  }
}
</script>
<template>
  <a-collapse v-model:activeKey="activeKey" :bordered="false" @change="onChange">
    <a-collapse-panel :key="name" :header="name" class="base-fields-collapse-content">
      <slot></slot>
    </a-collapse-panel>
  </a-collapse>
</template>

<style>
.ant-collapse .base-fields-collapse-content .ant-collapse-content>.ant-collapse-content-box {
  padding-left: 0;
  padding-right: 0;
}
</style>