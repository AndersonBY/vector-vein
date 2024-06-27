<script setup>
import { ref, watch, onMounted } from 'vue'

const props = defineProps({
  direction: {
    type: String,
    required: true,
    validator: (value) => ['top', 'bottom'].includes(value),
    default: 'bottom'
  },
  target: {
    type: [Object, null],
    required: true
  },
  top: {
    type: String,
    default: null,
  },
  bottom: {
    type: String,
    default: null,
  },
  left: {
    type: String,
    default: null,
  },
  right: {
    type: String,
    default: null,
  },
})

const isVisible = ref(false)
const style = {}
if (props.top !== null) {
  style.top = props.top
}
if (props.bottom !== null) {
  style.bottom = props.bottom
}
if (props.left !== null) {
  style.left = props.left
}
if (props.right !== null) {
  style.right = props.right
}

const scrollTo = () => {
  const element = props.target
  if (element) {
    let position = props.direction === 'top' ? 0 : element.scrollHeight
    element.scrollTo({ top: position, behavior: 'smooth' })
  }
}

const checkVisibility = () => {
  if (!props.target) return
  const threshold = 200
  if (props.direction === 'top') {
    isVisible.value = props.target.scrollTop > threshold
  } else {
    isVisible.value = props.target.scrollTop + props.target.clientHeight < props.target.scrollHeight - threshold
  }
}

const delayedCheckVisibility = () => {
  requestAnimationFrame(checkVisibility)
}

onMounted(() => {
  const element = props.target
  if (element) {
    element.addEventListener('scroll', delayedCheckVisibility)
  }
})

watch(() => props.target, (newTarget, oldTarget) => {
  if (oldTarget) {
    oldTarget.removeEventListener('scroll', delayedCheckVisibility)
  }
  if (newTarget) {
    newTarget.addEventListener('scroll', delayedCheckVisibility)
    delayedCheckVisibility()
  }
}, { immediate: true })
</script>

<template>
  <a-button v-if="isVisible" class="scroll-end-button" :style="style" shape="circle" @click="scrollTo">
    <template #icon>
      <slot name="icon">
        <span v-if="direction === 'top'">&#8593</span>
        <span v-else>&#8595;</span>
      </slot>
    </template>
  </a-button>
</template>

<style>
.scroll-end-button {
  position: sticky;
  z-index: 1000;
}
</style>