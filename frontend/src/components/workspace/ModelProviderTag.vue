<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { modelProviderTagBgColorMap } from '@/utils/common'

const props = defineProps({
  modelProvider: {
    type: String,
    default: '',
  },
})

const { t, te } = useI18n()
const modelProvider = ref(props.modelProvider)
</script>

<template>
  <a-tag :color="modelProviderTagBgColorMap[modelProvider]">
    {{ te(`components.nodes.llms.${modelProvider}.title`) ? t(`components.nodes.llms.${modelProvider}.title`)
      : modelProvider }}
  </a-tag>
</template>