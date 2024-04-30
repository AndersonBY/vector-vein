<script setup>
import { watch, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import "echarts"
import VChart from "vue-echarts"

const props = defineProps({
  option: {
    type: String,
    required: true,
    default: '',
  },
})

const { t } = useI18n()
const option = ref(props.option)
const parseOption = (option) => {
  let parsedOption = option
  if (typeof option === 'string') {
    try {
      parsedOption = JSON.parse(option)
    } catch (e) {
      console.error(e)
      parsedOption = {}
    }
  }
  parsedOption.toolbox = {
    show: true,
    feature: {
      saveAsImage: {
        show: true,
        title: t('components.workspace.echartsRenderer.download_image'),
        type: 'png',
        pixelRatio: 2,
      },
    },
  }
  return parsedOption
}
const parsedOption = ref(parseOption(option.value))

watch(() => props.option, () => {
  option.value = props.option
  parsedOption.value = parseOption(option.value)
})
</script>

<template>
  <a-row>
    <a-col :span="24">
      <v-chart class="chart" :option="parsedOption" :update-options="{ notMerge: true }"
        style="width: 100%; min-height: 50vh;" />
    </a-col>
  </a-row>
</template>