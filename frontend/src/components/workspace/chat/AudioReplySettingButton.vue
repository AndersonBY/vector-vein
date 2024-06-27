<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { Acoustic, CloseRemind } from '@icon-park/vue-next'
import IconButton from '@/components/IconButton.vue'
import SimpleFormItem from '@/components/SimpleFormItem.vue'
import { agentVoiceOptions } from '@/utils/common'

const props = defineProps({
  audioReply: {
    type: Boolean,
    default: false,
  },
  audioVoice: {
    type: Array,
    default: ['openai', 'onyx'],
  },
})

const emit = defineEmits(['update:audioReply', 'update:audioVoice'])

const { t } = useI18n()
const innerAudioReply = ref(props.audioReply)
const innerAudioVoice = ref(props.audioVoice)

watch(() => innerAudioReply.value, (value) => {
  emit('update:audioReply', value)
})
watch(() => props.audioReply, (value) => {
  innerAudioReply.value = value
})

watch(() => innerAudioVoice.value, (value) => {
  emit('update:audioVoice', value)
}, { deep: true })
watch(() => props.audioVoice, (value) => {
  innerAudioVoice.value = value
}, { deep: true })
</script>

<template>
  <div>
    <a-popover :title="t('workspace.chatSpace.agent_audio_reply')" placement="topLeft" trigger="click">
      <template #content>
        <a-flex vertical gap="large">
          <SimpleFormItem type="checkbox" layout="vertical" :title="t('workspace.chatSpace.agent_audio_reply')"
            :description="t('workspace.chatSpace.agent_audio_reply_description')" v-model="innerAudioReply" />
          <SimpleFormItem v-show="innerAudioReply" type="cascader" layout="vertical"
            :title="t('workspace.chatSpace.agent_audio_voice')" v-model="innerAudioVoice"
            :options="agentVoiceOptions" />
        </a-flex>
      </template>
      <IconButton :text="t('workspace.chatSpace.agent_audio_reply')" size="small" type="text" shape="round">
        <template #icon>
          <Acoustic v-if="innerAudioReply" fill="#389e0d" />
          <CloseRemind v-else />
        </template>
      </IconButton>
    </a-popover>
  </div>
</template>

<style scoped>
.markdown-body {
  padding: 8px;
  background-color: #f0f0f0;
  border-radius: 10px;
}
</style>