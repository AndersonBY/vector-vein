<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { InboxOut, LoadingFour } from '@icon-park/vue-next'
import { message } from 'ant-design-vue'

const props = defineProps({
  supportFileTypes: {
    type: String,
    required: false,
    default: '.jpg, .png, .jpeg, .gif, .webp, .svg',
  },
})

const loading = ref(false)
const fileList = ref([])
const imageUrl = defineModel()
const imageBase64 = ref('')
if (imageUrl.value.length > 0) {
  imageBase64.value = imageUrl.value
}

const selectFile = async () => {
  loading.value = true
  try {
    const selectedFiles = await window.pywebview.api.open_file_dialog(false)
    if (!selectedFiles) {
      return
    }
    const base64 = await window.pywebview.api.get_local_file_base64(selectedFiles[0])

    message.success(t('components.workspace.uploaderFieldUse.upload_success', { file: selectedFiles[0] }))

    imageBase64.value = base64
    imageUrl.value = selectedFiles[0]
  } catch (error) {
    console.error(error)
    message.error(t('components.workspace.uploaderFieldUse.upload_failed'))
  } finally {
    loading.value = false
  }
}

const { t } = useI18n()
</script>

<template>
  <a-upload-dragger class="avatar-uploader" v-model:fileList="fileList" name="file" :multiple="false"
    :accept="props.supportFileTypes" list-type="picture-card" @click="selectFile" :openFileDialogOnClick="false"
    :show-upload-list="false">
    <img v-if="imageBase64" :src="imageBase64" alt="avatar" />
    <div v-else>
      <LoadingFour v-if="loading" :spin="true" theme="outline" size="24" fill="#28c5e5" />
      <InboxOut v-else theme="outline" size="24" fill="#28c5e5" />
      <div class="ant-upload-text">{{ t('components.workspace.avatarUpload.uploader_text') }}</div>
    </div>
  </a-upload-dragger>
</template>

<style>
.avatar-uploader>.ant-upload {
  width: 80px;
  height: 80px;
}

.avatar-uploader>.ant-upload>.ant-upload-btn {
  width: 100%;
  height: 100%;
  padding: 8px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
}

.avatar-uploader>.ant-upload img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
</style>