<script setup>
import IconButton from '@/components/IconButton.vue'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
import { ref, watch } from 'vue'
import { PlayOne, Pause, Download } from '@/icons'
import VueAudioPlayer from '@liripeng/vue-audio-player'
import axios from 'axios'

const props = defineProps({
  audios: {
    type: Array,
    required: true,
    default: () => [],
  },
  isMidi: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const context = new AudioContext()
let piano, player

const playing = ref(false)
const stop = () => {
  playing.value = false
  player && player.stop()
}
const play = async () => {
  playing.value = true
  const { data: song } = await axios.get(innerAudios.value[0], {
    responseType: 'arraybuffer'
  })
  player.loadArrayBuffer(song)
  player.play()
}

const loadMidiPlayer = async () => {
  const { default: MidiPlayer } = await import('midi-player-js')
  const { SplendidGrandPiano } = await import('smplr')

  piano = new SplendidGrandPiano(context)
  player = new MidiPlayer.Player((event) => {
    if (!playing.value) {
      player.stop()
    }

    if (event.name === 'Note on' && event.velocity > 0) {
      piano.start(event.noteName, context.currentTime, {
        gain: event.velocity / 100,
      })
    }
  })
}

if (props.isMidi) {
  loadMidiPlayer()
}

watch(() => props.isMidi, (newValue) => {
  if (newValue) {
    loadMidiPlayer()
  }
})

const innerAudios = ref(props.audios)
watch(() => props.audios, (newValue) => {
  if (typeof newValue === 'string') {
    innerAudios.value = [newValue]
  } else {
    innerAudios.value = newValue
  }
})

async function downloadAudio() {
  const currentPlayIndex = audioPlayerRef.value?.currentPlayIndex || 0
  try {
    const audioUrl = innerAudios.value[currentPlayIndex]
    const response = await axios.get(audioUrl, { responseType: 'blob' })
    const blob = new Blob([response.data])

    // 从URL中提取文件名和扩展名
    const urlObj = new URL(audioUrl)
    const pathName = decodeURIComponent(urlObj.pathname)
    const fileNameWithExt = pathName.split('/').pop()

    // 分离文件名和扩展名
    const lastDotIndex = fileNameWithExt.lastIndexOf('.')
    let fileName = fileNameWithExt
    let fileExt = ''

    if (lastDotIndex !== -1) {
      fileName = fileNameWithExt.substring(0, lastDotIndex)
      fileExt = fileNameWithExt.substring(lastDotIndex)
    }

    // 如果没有扩展名，则根据MIME类型添加
    if (!fileExt) {
      const mimeType = response.headers['content-type']
      fileExt = mimeType === 'audio/midi' || mimeType === 'audio/x-midi'
        ? '.midi'
        : mimeType === 'audio/mpeg'
          ? '.mp3'
          : mimeType === 'audio/wav'
            ? '.wav'
            : '.audio'
    }

    const fullFileName = `${fileName}${fileExt}`

    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', fullFileName)
    document.body.appendChild(link)
    link.click()
    link.remove()
    window.URL.revokeObjectURL(url)
  } catch (error) {
    console.error('下载音频文件时出错:', error)
  }
}

const audioPlayerRef = ref()
</script>

<template>
  <a-flex vertical>
    <VueAudioPlayer v-if="!isMidi" ref="audioPlayerRef" :audio-list="innerAudios" theme-color="#28c5e5"
      :isLoop="false" />
    <div v-else>
      <IconButton v-if="playing" :text="t('common.pause')" type="primary" shape="round" size="large" @click="stop">
        <template #icon><Pause theme="filled" /></template>
      </IconButton>
      <IconButton v-else :text="t('common.play')" type="primary" shape="round" size="large" @click="play">
        <template #icon>
          <play-one theme="filled" />
        </template>
      </IconButton>
    </div>
    <IconButton :text="t('common.download')" @click="downloadAudio">
      <template #icon>
        <Download />
      </template>
    </IconButton>
  </a-flex>
</template>