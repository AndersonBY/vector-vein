<script setup>
import { ref, watch } from 'vue'
import { PlayOne, Pause } from '@icon-park/vue-next'
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
  const { data: song } = await axios.get(props.audios[0], {
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
</script>

<template>
  <VueAudioPlayer :audio-list="audios" theme-color="#28c5e5" :isLoop="false" v-if="!isMidi" />
  <div v-if="isMidi">
    <a-button type="primary" shape="round" size="large" @click="stop" v-if="playing">
      <pause theme="filled" />
    </a-button>
    <a-button type="primary" shape="round" size="large" @click="play" v-else>
      <template #icon>
        <play-one theme="filled" />
      </template>
    </a-button>
  </div>
</template>