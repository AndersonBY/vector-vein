<script setup>
import { modelTagBackgroundColorMap } from '@/utils/common'

const props = defineProps({
  model: {
    type: String,
    default: '',
  },
})
</script>

<template>
  <a-tag :color="modelTagBackgroundColorMap[model]">
    {{ model }}
  </a-tag>
</template>