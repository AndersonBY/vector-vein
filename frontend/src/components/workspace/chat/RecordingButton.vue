<script setup>
import { ref } from 'vue'
import { HandleSquare, Voice } from '@icon-park/vue-next'
import { message } from 'ant-design-vue'
import { useI18n } from 'vue-i18n'
import { hardwareAPI } from '@/api/user'
import { audioAPI } from '@/api/chat'

const props = defineProps({
  transcribe: {
    type: Boolean,
    default: false,
  },
  text: {
    type: String,
    default: '',
  },
})

const { t } = useI18n()
const recording = ref(false)
const transcribing = ref(false)

const emit = defineEmits(['finished', 'update:text'])

const audioFile = ref('')

const stopCheckTimer = ref()
const autoStop = ref(false)

const startRecording = async (payload = {}) => {
  recording.value = true
  autoStop.value = payload.auto_stop
  try {
    const res = await hardwareAPI('start_microphone', payload)
    if (res.status == 200) {
      message.success(t('workspace.chatSpace.recording_start'))
      if (autoStop.value) {
        stopCheckTimer.value = setInterval(async () => {
          const checkResp = await hardwareAPI('check_microphone')
          if (!recording.value) {
            clearInterval(stopCheckTimer.value)
            return
          }
          if (!checkResp.data?.is_recording) {
            clearInterval(stopCheckTimer.value)
            recording.value = false
            await postRecordingHandler(checkResp.data.audio_path)
          }
        }, 1000)
      }
    } else {
      message.error(t('workspace.chatSpace.recording_failed'))
    }
  } catch (error) {
    console.error(error)
    message.error(t('workspace.chatSpace.recording_failed'))
  }
}

const postRecordingHandler = async (audio_path) => {
  audioFile.value = audio_path
  if (props.transcribe) {
    transcribing.value = true
    const res = await audioAPI('transcribe', { audio_file: audioFile.value })
    if (res.status != 200) {
      message.success(t('workspace.chatSpace.transcribe_failed'))
    } else {
      emit('update:text', res.data.transcription)
      emit('finished', res.data.transcription)
    }
  } else {
    emit('finished', audioFile.value)
  }
  transcribing.value = false
}

const stopRecording = async () => {
  try {
    const res = await hardwareAPI('stop_microphone')
    if (res.status != 200) {
      message.error(t('common.failed'))
    } else {
      await postRecordingHandler(res.data.audio_path)
    }
  } catch (error) {
    console.error(error)
    message.error(t('common.failed'))
  }
  recording.value = false
}

const toggleRecording = async () => {
  if (recording.value) {
    await stopRecording()
  } else {
    await startRecording()
  }
}

// Expose for Python usage.
window.start_recording = startRecording
window.stop_recording = stopRecording
</script>

<template>
  <div>
    <a-tooltip :title="!recording ? t('workspace.chatSpace.recording') : t('workspace.chatSpace.stop_recording')">
      <a-button type="text" @click="toggleRecording" :loading="transcribing">
        <template #icon>
          <HandleSquare v-if="recording" fill="#ff4d4f" />
          <Voice v-else />
        </template>
      </a-button>
    </a-tooltip>
  </div>
</template>