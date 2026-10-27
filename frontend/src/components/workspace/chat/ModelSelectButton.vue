<script setup>
import { computed, watch, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import ModelPicker from '@/components/ModelPicker.vue'
import { getChatModelOptions } from '@/utils/common'
import { conversationAPI } from '@/api/chat'

const props = defineProps({
  cid: { type: String, default: '' },
  model: { type: String, default: '' },
  modelProvider: { type: String, default: '' },
  settings: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['update:model', 'update:modelProvider', 'update:settings'])
const { t } = useI18n()
const options = computed(() => getChatModelOptions())
let generation = 0
watch(() => props.cid, () => { generation++ })
onBeforeUnmount(() => { generation++ })
const saveSelection = async selection => {
  const version = ++generation
  const settings = { ...props.settings, model_preference: selection.model_preference, reasoning_effort: selection.reasoning_effort }
  if (props.cid !== 'tmp') {
    const response = await conversationAPI('update', { cid: props.cid, model: selection.model, model_provider: selection.model_provider, settings })
    if (version !== generation) return false
    if (response.status !== 200) throw new Error('Model update failed')
    message.success(t('workspace.chatSpace.model_select_success'))
  }
  if (version !== generation) return false
  emit('update:settings', { ...props.settings, model_preference: selection.model_preference, reasoning_effort: selection.reasoning_effort })
  return true
}
</script>

<template>
  <ModelPicker :key="cid" :model="model" :model-provider="modelProvider" :options="options"
    :preference="settings.model_preference || 'custom'" :reasoning-effort="settings.reasoning_effort || 'default'"
    :save-selection="saveSelection" @update:model="emit('update:model', $event)"
    @update:model-provider="emit('update:modelProvider', $event)" />
</template>
