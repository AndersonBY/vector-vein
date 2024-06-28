<script setup>
import { ref, computed, watch } from "vue"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { RobotOne } from '@icon-park/vue-next'
import IconButton from '@/components/IconButton.vue'
import { getChatModelOptions } from '@/utils/common'
import { conversationAPI } from '@/api/chat'

const props = defineProps({
  cid: {
    type: String,
    default: ''
  },
  model: {
    type: String,
    default: ''
  },
  modelProvider: {
    type: String,
    default: ''
  },
})
const emit = defineEmits(['update:model', 'update:modelProvider'])

const { t } = useI18n()
const open = ref(false)
const chatModelOptions = ref(getChatModelOptions())

const model = ref(props.model)
const modelProvider = ref([props.modelProvider])
const modelProviders = computed(() => (chatModelOptions.value.map((item) => {
  return {
    key: item.value,
    label: item.label,
    _children: item.children,
  }
})))
const modelSelection = ref([props.model])
const modelSelections = computed(() => {
  const models = chatModelOptions.value.filter((item) => item.value === modelProvider.value[0])
  if (models.length === 0) return []
  return models[0].children.map((item) => {
    return {
      key: item.value,
      label: item.label,
    }
  })
})

watch(() => props.model, (value) => {
  model.value = value
  modelSelection.value = [model.value]
})
watch(() => props.modelProvider, (value) => {
  modelProvider.value = [value]
  modelSelection.value = [model.value]
})

const originalModelProvider = ref([])
const originalModelSelection = ref([])
const openModal = () => {
  originalModelProvider.value = modelProvider.value
  originalModelSelection.value = modelSelection.value
  open.value = true
}
const cancel = () => {
  open.value = false
  modelProvider.value = originalModelProvider.value
  modelSelection.value = originalModelSelection.value
}

const modelChanged = async () => {
  model.value = modelSelection.value[0]
  emit('update:model', model.value)
  emit('update:modelProvider', modelProvider.value[0])
  if (props.cid === 'tmp') {
    open.value = false
    return
  }
  const response = await conversationAPI('update', {
    cid: props.cid,
    model: model.value,
    model_provider: modelProvider.value[0]
  })
  if (response.status == 200) {
    message.success(t('workspace.chatSpace.model_select_success'))
  }
  open.value = false
}
</script>

<template>
  <div>
    <a-popover :title="t('workspace.chatSpace.model_select')" placement="topLeft">
      <IconButton :text="model" size="small" type="text" shape="round" @click="openModal">
        <template #icon>
          <RobotOne :fill="'#389e0d'" />
        </template>
      </IconButton>
    </a-popover>
    <a-modal :open="open" :title="t('workspace.chatSpace.model_select')" :width="650" @cancel="cancel"
      @ok="modelChanged" class="model-selection-modal">
      <a-row>
        <a-col :span="12">
          <a-menu v-model:selectedKeys="modelProvider" theme="light" mode="inline" :items="modelProviders"
            class="model-selection-menu">
          </a-menu>
        </a-col>
        <a-col :span="12">
          <a-menu v-model:selectedKeys="modelSelection" theme="light" mode="inline" :items="modelSelections"
            class="model-selection-menu">
          </a-menu>
        </a-col>
      </a-row>
    </a-modal>
  </div>
</template>

<style scoped>
.markdown-body {
  padding: 8px;
  background-color: #f0f0f0;
  border-radius: 10px;
}

.model-selection-modal .model-selection-menu {
  border-inline-end: none;
}
</style>