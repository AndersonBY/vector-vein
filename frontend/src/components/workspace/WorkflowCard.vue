<script setup>
import { computed } from "vue"
import { useI18n } from 'vue-i18n'
import { BranchTwo, More, Share, Copy, Delete, Star } from '@icon-park/vue-next'
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
    default: false
  },
  datetime: {
    type: [String, Boolean],
    required: false,
    default: false,
  },
  forks: {
    type: [Number, Boolean],
    required: false,
    default: 0,
  },
  extra: {
    type: [Object, Boolean],
    required: false,
    default: false,
  },
  starred: {
    type: [Boolean, undefined],
    required: false,
    default: undefined,
  },
  loading: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const emit = defineEmits(['star', 'clone', 'delete'])

const { t } = useI18n()
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
  <a-card :id="id" :loading="loading" class="workflow-card" hoverable :style="background">
    <div class="gradient-layer">
      <a-flex vertical class="info-container">
        <a-flex justify="space-between" style="flex-grow: 1;">
          <div>
            <a-tag v-for="(tag, index) in tags" :key="index" :color="tag.color" style="margin-bottom: 10px;">
              {{ tag.title }}
            </a-tag>
          </div>
          <div>
            <a-flex align="center">
              <a-button v-if="(typeof starred) !== 'undefined'" size="small" type="text" @click.prevent="emit('star')">
                <template #icon>
                  <a-tooltip
                    :title="starred ? t('workspace.workflowSpace.delete_from_fast_access') : t('workspace.workflowSpace.add_to_fast_access')">
                    <Star :theme="starred ? 'filled' : 'outline'" fill="#fff" />
                  </a-tooltip>
                </template>
              </a-button>
              <a-dropdown v-if="extra" placement="bottomRight">
                <template #overlay>
                  <a-menu>
                    <a-menu-item key="clone" @click="emit('clone', id)">
                      <Copy />
                      {{ t('workspace.workflowSpace.clone_workflow') }}
                    </a-menu-item>
                    <a-popconfirm :title="t('workspace.workflowSpace.delete_confirm')" @confirm="emit('delete', id)">
                      <a-menu-item key="delete">
                        <a-typography-text type="danger">
                          <Delete />
                          {{ t('common.delete') }}
                        </a-typography-text>
                      </a-menu-item>
                    </a-popconfirm>
                  </a-menu>
                </template>
                <a-button size="small" type="text">
                  <More theme="filled" size="24" fill="#fff" />
                </a-button>
              </a-dropdown>
            </a-flex>
          </div>
        </a-flex>
        <a-typography-title :level="4" class="workflow-title">
          {{ title }}
        </a-typography-title>
        <a-flex align="center" justify="space-between" class="meta-info-container">
          <AuthorComponent v-if="author" :author="author" fontColor="#fff" />
          <span v-if="datetime" class="meta-text">{{ datetime }}</span>
          <a-flex v-if="typeof forks == 'number'" align="center" class="meta-text">
            <BranchTwo />
            <span>{{ forks >= 10 ? forks : '<10' }}</span>
          </a-flex>
        </a-flex>
      </a-flex>
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
  transform: translateZ(1px);
}

.info-container .meta-info-container .meta-text {
  color: #fff;
  font-size: 14px;
}
</style>