<script setup>
import { computed } from "vue"
import { useI18n } from 'vue-i18n'

const props = defineProps({
  author: {
    type: Object,
    required: true,
  },
  time: {
    type: [Boolean, Number],
    required: false,
    default: false,
  },
  fontColor: {
    type: String,
    required: false,
    default: '#0f0f0f',
  },
})

const { t } = useI18n()

const authorAvatarBackground = computed(() => {
  if (props.author.avatar) {
    return {
      backgroundImage: `url(${props.author.avatar})`
    }
  } else {
    return {
      backgroundColor: '#28c5e5'
    }
  }
})

const authorNickname = computed(() => {
  if (props.author.nickname) {
    return props.author.nickname
  } else {
    return t('common.vectorvein_user')
  }
})

const showTime = computed(() => {
  if (typeof props.time == 'boolean' && props.time == true) {
    return new Date().toLocaleString()
  } else if (typeof props.time == 'boolean' && props.time == false) {
    return false
  } else {
    return new Date(props.time).toLocaleString()
  }
})
</script>

<template>
  <a-space v-if="author.type == 'A'" class="author-main-container">
    <div class="author-container">
      <div class="author-avatar" :style="authorAvatarBackground">
        {{ 'backgroundImage' in authorAvatarBackground ? '' : authorNickname[0] }}
      </div>
      <div class="author-nickname" :style="{ color: fontColor }">
        {{ authorNickname }}
      </div>
    </div>
    <a-typography-text v-if="showTime" class="time-text" type="secondary">
      {{ showTime }}
    </a-typography-text>
  </a-space>
  <a-space v-else class="author-main-container">
    <a-typography-text v-if="showTime" class="time-text" type="secondary">
      {{ showTime }}
    </a-typography-text>
    <div class="author-container">
      <div class="author-nickname" :style="{ color: fontColor }">
        {{ authorNickname }}
      </div>
      <div class="author-avatar" :style="authorAvatarBackground">
        {{ 'backgroundImage' in authorAvatarBackground ? '' : authorNickname[0] }}
      </div>
    </div>
  </a-space>
</template>

<style scoped>
.author-container {
  display: flex;
  align-items: center;
  gap: 8px;
}

.author-container .author-avatar {
  width: 24px;
  height: 24px;
  border-radius: 100%;
  background-position: center center;
  background-size: cover;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 12px;
  color: #fff;
}

.author-container .author-nickname {
  font-size: 14px;
  font-weight: 600;
}

.author-main-container .time-text {
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s ease-in-out, visibility 0.3s ease-in-out;
}

.author-main-container:hover .time-text {
  opacity: 1;
  visibility: visible;
}
</style>