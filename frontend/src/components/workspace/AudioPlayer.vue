<script setup>
import { defineComponent } from 'vue'
import AudioPlayer from '@liripeng/vue-audio-player'

defineComponent({
  name: 'AudioPlayer',
})

const props = defineProps({
  audios: {
    type: Array,
    required: true,
    default: () => [],
  },
})

</script>

<template>
  <audio-player :audio-list="props.audios" theme-color="#28c5e5" :isLoop="false" />
</template>