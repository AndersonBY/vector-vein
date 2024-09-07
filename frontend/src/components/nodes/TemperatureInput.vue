<script setup>
import { ref, reactive, onBeforeMount } from 'vue'
import { useI18n } from 'vue-i18n'
import { Setting } from '@icon-park/vue-next'

const { t } = useI18n()
const temperatureNumber = defineModel()

const temperaturePresets = reactive([t('components.nodes.llms.common.creative'), t('components.nodes.llms.common.balanced'), t('components.nodes.llms.common.precise')])
const temperatureString = ref(t('components.nodes.llms.common.balanced'))
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
    temperatureString.value = t('components.nodes.llms.common.precise')
  } else if (value > 0.3 && value <= 0.7) {
    temperatureString.value = t('components.nodes.llms.common.balanced')
  } else if (value > 0.7 && value <= 1) {
    temperatureString.value = t('components.nodes.llms.common.creative')
  }
}

const popoverVisible = ref(false)

onBeforeMount(() => {
  temperatureInputValueChange(temperatureNumber.value)
})
</script>
<template>
  <a-flex align="center" justify="space-between" gap="small">
    <div style="flex-grow: 1;">
      <a-segmented style="width: 100%;" block v-model:value="temperatureString" :options="temperaturePresets"
        @change="temperaturePresetsChange" />
    </div>
    <a-popover v-model:open="popoverVisible" trigger="hover" placement="topRight">
      <template #content>
        <a-input-number v-model:value="temperatureNumber" :step="0.1" :max="1" :min="0" :keyboard="false"
          @change="temperatureInputValueChange" style="width: 100px" />
      </template>
      <a-button type="text">
        <template #icon>
          <Setting />
        </template>
      </a-button>
    </a-popover>
  </a-flex>
</template>