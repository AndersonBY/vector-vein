<script setup>
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { RobotOne } from '@/icons'
import ModelCapabilities from '@/components/ModelCapabilities.vue'
import ModelSelector from '@/components/ModelSelector.vue'
import IconButton from '@/components/IconButton.vue'
import { getChatModelOptions } from '@/utils/common'
import { hasModelOption, filterModelOption } from '@/utils/modelSelection'
import { conversationAPI } from '@/api/chat'

const props = defineProps({
  cid: { type: String, default: '' },
  model: { type: String, default: '' },
  modelProvider: { type: String, default: '' },
})
const emit = defineEmits(['update:model', 'update:modelProvider'])
const { t } = useI18n()
const open = ref(false)
const saving = ref(false)
const saveError = ref(false)
const draftProvider = ref(props.modelProvider)
const draftModel = ref(props.model)
const chatModelOptions = computed(() => getChatModelOptions())
const providerOptions = computed(() => chatModelOptions.value.map(item => ({ value: item.value, label: item.labelText || (typeof item.label === 'string' ? item.label : item.value) })))
const modelOptions = computed(() => chatModelOptions.value.find(item => item.value === draftProvider.value)?.children || [])
const providerUnavailable = computed(() => Boolean(draftProvider.value) && !hasModelOption(providerOptions.value, draftProvider.value))
const validSelection = computed(() => hasModelOption(providerOptions.value, draftProvider.value) && hasModelOption(modelOptions.value, draftModel.value))
let generation = 0

const resetDraft = () => {
  draftProvider.value = props.modelProvider
  draftModel.value = props.model
  saveError.value = false
}
const openModal = () => { resetDraft(); open.value = true }
const cancel = () => { if (!saving.value) { open.value = false; resetDraft() } }
const providerChanged = value => {
  if (value === draftProvider.value) return
  draftProvider.value = value ?? ''
  draftModel.value = ''
  saveError.value = false
}
watch(() => [props.modelProvider, props.model], () => { if (!saving.value) resetDraft() })
watch(() => props.cid, () => { generation++; saving.value = false; open.value = false; resetDraft() })
onBeforeUnmount(() => { generation++ })

const modelChanged = async () => {
  if (saving.value || !validSelection.value) return
  const version = ++generation
  const selection = { cid: props.cid, model: draftModel.value, model_provider: draftProvider.value }
  saving.value = true
  saveError.value = false
  try {
    if (selection.cid !== 'tmp') {
      const response = await conversationAPI('update', selection)
      if (version !== generation) return
      if (response.status !== 200) throw new Error('Model update failed')
    }
    if (version !== generation) return
    emit('update:modelProvider', selection.model_provider)
    emit('update:model', selection.model)
    open.value = false
    if (selection.cid !== 'tmp') message.success(t('workspace.chatSpace.model_select_success'))
  } catch {
    if (version === generation) saveError.value = true
  } finally {
    if (version === generation) saving.value = false
  }
}
</script>

<template>
  <div>
    <a-popover :title="t('workspace.chatSpace.model_select')" placement="topLeft">
      <IconButton :text="model || t('components.model_selector.select_model')" size="small" type="text" shape="round" @click="openModal">
        <template #icon><RobotOne :fill="'#389e0d'" /></template>
      </IconButton>
    </a-popover>
    <a-modal :open="open" :title="t('workspace.chatSpace.model_select')" :width="600" @cancel="cancel" @ok="modelChanged"
      :confirm-loading="saving" :ok-button-props="{ disabled: !validSelection }" :cancel-button-props="{ disabled: saving }"
      :closable="!saving" :mask-closable="!saving" :keyboard="!saving">
      <a-form layout="vertical">
        <a-form-item :label="t('components.model_selector.provider')">
          <a-select :value="draftProvider || undefined" :options="providerOptions" show-search :filter-option="filterModelOption"
            :disabled="saving" :status="providerUnavailable ? 'error' : undefined" @change="providerChanged" />
          <a-typography-text v-if="providerUnavailable" type="danger" role="status">{{ t('components.model_selector.provider_unavailable') }}</a-typography-text>
        </a-form-item>
        <a-form-item :label="t('components.nodes.llms.common.llm_model')">
          <ModelSelector v-model="draftModel" :options="modelOptions" :disabled="saving" />
        </a-form-item>
      </a-form>
      <ModelCapabilities v-if="validSelection" :provider="draftProvider" :model="draftModel" />
      <a-typography-text v-if="saveError" type="danger" role="alert">{{ t('components.model_selector.save_failed') }}</a-typography-text>
    </a-modal>
  </div>
</template>
