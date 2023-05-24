<script setup>
import { defineComponent, ref, reactive, onBeforeMount } from 'vue'
import { useI18n } from 'vue-i18n'

defineComponent({
  name: 'TemperatureInput',
})

const { t } = useI18n()
const temperatureNumber = defineModel()

const temperaturePresets = reactive([t('components.nodes.llms.OpenAI.creative'), t('components.nodes.llms.OpenAI.balanced'), t('components.nodes.llms.OpenAI.precise')])
const temperatureString = ref(t('components.nodes.llms.OpenAI.balanced'))
const temperaturePresetValues = reactive([0.8, 0.5, 0.2])
const temperaturePresetsChange = (value) => {
  temperatureString.value = value
  temperaturePresets.forEach((v, i) => {
    if (v === value) {
      temperatureNumber.value = temperaturePresetValues[i]
    }
  })
}
const temperatureInputValueChange = (value) => {
  if (value >= 0 && value <= 0.3) {
    temperatureString.value = t('components.nodes.llms.OpenAI.precise')
  } else if (value > 0.3 && value <= 0.7) {
    temperatureString.value = t('components.nodes.llms.OpenAI.balanced')
  } else if (value > 0.7 && value <= 1) {
    temperatureString.value = t('components.nodes.llms.OpenAI.creative')
  }
}

onBeforeMount(() => {
  temperatureInputValueChange(temperatureNumber.value)
})
</script>
<template>
  <div>
    <a-segmented v-model:value="temperatureString" :options="temperaturePresets" block
      @change="temperaturePresetsChange" />
    <a-input-number style="width: 100%;" v-model:value="temperatureNumber" :step="0.1" :max="1" :min="0" :keyboard="false"
      @change="temperatureInputValueChange" />
  </div>
</template>