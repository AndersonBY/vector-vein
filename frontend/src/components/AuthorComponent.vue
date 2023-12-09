<script setup>
import { computed } from "vue"
import { useI18n } from 'vue-i18n'

const props = defineProps({
  author: {
    type: Object,
    required: false,
    default: () => ({}),
  },
  time: {
    type: [Boolean, Number],
    required: false,
    default: false,
  },
  fontColor: {
    type: String,
    required: false,
    default: '#fff',
  },
})

const { t } = useI18n()

const authorAvatarBackground = computed(() => {
  if (props.author.avatar) {
    return {
      backgroundImage: props.author.avatar
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
  <a-space>
    <div class="author-container">
      <div class="author-avatar" :style="authorAvatarBackground">
        {{ authorNickname[0] }}
      </div>
      <div class="author-nickname" :style="{ color: fontColor }">
        by {{ authorNickname }}
      </div>
    </div>
    <a-typography-text type="secondary" v-if="showTime">
      {{ showTime }}
    </a-typography-text>
  </a-space>
</template>

<style scoped>
.author-container {
  display: flex;
  align-items: center;
}

.author-container .author-avatar {
  width: 32px;
  height: 32px;
  border-radius: 100%;
  background-position: center center;
  background-size: cover;
  margin-right: 8px;
  display: flex;
  justify-content: center;
  align-items: center;
  font-size: 16px;
  color: #fff;
}

.author-container .author-nickname {
  font-size: 14px;
  font-weight: 600;
}
</style>