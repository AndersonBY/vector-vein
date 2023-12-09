<script setup>
import { computed } from "vue"
import { BranchTwo } from '@icon-park/vue-next'
import AuthorComponent from "@/components/AuthorComponent.vue"
import { getRandomInt } from '@/utils/util'
import { backgroundColors } from '@/utils/common'

const props = defineProps({
  id: {
    type: String,
    required: false,
    default: "",
  },
  title: {
    type: String,
    required: true,
  },
  tags: {
    type: Array,
    required: true,
    default: () => [],
  },
  images: {
    type: Array,
    required: false,
    default: () => [],
  },
  brief: {
    type: String,
    required: false,
    default: "",
  },
  author: {
    type: [Object, Boolean],
    required: false,
    default: () => ({}),
  },
  forks: {
    type: [Number, Boolean],
    required: false,
    default: 0,
  },
})

const background = computed(() => {
  if (props.images.length === 0) {
    return {
      backgroundColor: backgroundColors[getRandomInt(0, backgroundColors.length - 1)],
    }
  } else {
    return {
      backgroundImage: `url(${props.images[0]})`,
    }
  }
})
</script>

<template>
  <a-card :id="id" class="workflow-card" hoverable :style="background">
    <div class="gradient-layer">
      <div class="info-container">
        <div style="flex-grow: 1;">
          <a-tag v-for="(tag, index) in tags" :key="index" :color="tag.color" style="margin-bottom: 10px;">
            {{ tag.title }}
          </a-tag>
        </div>
        <a-typography-title :level="4" class="workflow-title">
          {{ title }}
        </a-typography-title>
        <div class="meta-info-container">
          <AuthorComponent :author="author" fontColor="#fff" v-if="author" />
          <div class="numbers-container">
            <div v-if="typeof forks == 'number'">
              <BranchTwo />
              {{ forks >= 10 ? forks : '<10' }} </div>
            </div>
          </div>
        </div>
      </div>
  </a-card>
</template>

<style scoped>
.workflow-card {
  height: 300px;
  background-size: cover;
  background-position: center;
}

.gradient-layer {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: linear-gradient(180deg, rgba(0, 0, 0, 0.3) 0%, rgba(0, 0, 0, 0.65) 100%);
  z-index: 1;
  padding: 20px;
  display: flex;
  border-radius: 8px;
}

.info-container {
  display: flex;
  flex-direction: column;
  flex-grow: 1;
  transform: translateZ(1px);
}

.info-container .workflow-title {
  font-size: 30px;
  font-weight: 600;
  color: rgb(255, 255, 255);
  -webkit-line-clamp: 2;
  overflow: hidden;
  display: -webkit-box;
  -webkit-box-orient: vertical;
}

.info-container .meta-info-container {
  margin-top: 16px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  transform: translateZ(1px);
}

.info-container .meta-info-container .numbers-container {
  display: flex;
  align-items: center;
  color: #fff;
  font-size: 14px;
}
</style>