<script setup>
import { ref, onMounted, onBeforeUnmount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  InboxOut,
  FilePdf,
  FileExcel,
  FileWord,
  FileTxt,
  FileZip,
  FileSuccess,
  ImageFiles,
} from '@icon-park/vue-next'
import { message } from 'ant-design-vue'
import { v4 as uuidv4 } from 'uuid'

const props = defineProps({
  multiple: {
    type: Boolean,
    required: false,
    default: false,
  },
  supportFileTypes: {
    type: String,
    required: false,
    default: '.docx, .pptx, .xlsx, .pdf, .txt, .md, .html, .json, .csv, .srt, .zip',
  },
  acceptPaste: {
    type: Boolean,
    required: false,
    default: false,
  },
  showUploadList: {
    type: Boolean,
    required: false,
    default: true,
  },
  addUuid: {
    type: Boolean,
    required: false,
    default: true,
  },
  singleButton: {
    type: Boolean,
    required: false,
    default: false,
  },
  singleButtonProps: {
    type: Object,
    required: false,
    default: () => {
      return {
        block: false,
        danger: false,
        disabled: false,
        ghost: false,
        loading: false,
        shape: 'default',
        size: 'middle',
        type: 'default',
      }
    },
  },
  firstFile: {
    type: String,
    required: false,
    default: '',
  },
})

const emit = defineEmits(['update:firstFile'])
const files = defineModel()
const fileList = ref([])
const uploading = ref(false)

watch(() => files.value, (newValue) => {
  if (typeof files.value === 'string') {
    fileList.value = [files.value].map(file => {
      return {
        uid: file,
        name: file,
        originalName: file,
        status: 'done',
        url: file,
      }
    })
    files.value = [files.value]
  } else if (typeof files.value === 'object') {
    fileList.value = files.value.map(file => {
      return {
        uid: file,
        name: file,
        originalName: file,
        status: 'done',
        url: file,
      }
    })
  } else {
    if (props.firstFile) {
      files.value = [props.firstFile]
      fileList.value = [props.firstFile].map(file => {
        return {
          uid: file,
          name: file,
          originalName: file,
          status: 'done',
          url: file,
        }
      })
    } else {
      files.value = []
      fileList.value = []
    }
  }
})

onMounted(async () => {
  if (props.acceptPaste) document.addEventListener('paste', pasteUpload)
})
onBeforeUnmount(() => {
  if (props.acceptPaste) document.removeEventListener('paste', pasteUpload)
})

const pasteUpload = (event) => {
  const items = event.clipboardData.items
  for (let i = 0; i < items.length; i++) {
    const item = items[i]
    if (item.kind === 'file' && item.type.startsWith('image/')) {
      const blob = item.getAsFile()
      const { name } = blob
      try {
        const reader = new FileReader()
        reader.onloadend = async () => {
          const base64data = reader.result
          const file = await window.pywebview.api.save_image(base64data)
          files.value.push(file)
          fileList.value.push({
            uid: uuidv4(),
            name: file,
            originalName: file,
            status: 'done',
            url: file,
          })
          emit('update:firstFile', files.value[0])
          message.success(t('components.workspace.uploaderFieldUse.upload_success', { file: name }))
        };
        reader.readAsDataURL(blob)
      } catch (e) {
        message.error(t('components.workspace.uploaderFieldUse.upload_failed', { file: name }))
      }
    }
  }
}

if (typeof files.value === 'string') {
  fileList.value = [files.value].map(file => {
    return {
      uid: file,
      name: file,
      originalName: file,
      status: 'done',
      url: file,
    }
  })
  files.value = [files.value]
} else if (typeof files.value === 'object') {
  fileList.value = files.value.map(file => {
    return {
      uid: file,
      name: file,
      originalName: file,
      status: 'done',
      url: file,
    }
  })
} else {
  if (props.firstFile) {
    files.value = [props.firstFile]
    fileList.value = [props.firstFile].map(file => {
      return {
        uid: file,
        name: file,
        originalName: file,
        status: 'done',
        url: file,
      }
    })
  } else {
    files.value = []
    fileList.value = []
  }
}

const selectFile = async (e) => {
  if (!props.singleButton && e.target.closest('.ant-upload.ant-upload-drag') === null) return

  uploading.value = true
  try {
    const selectedFiles = await window.pywebview.api.open_file_dialog(props.multiple)
    if (!selectedFiles) {
      return
    }
    let _files = []
    if (typeof selectedFiles === 'string') {
      _files = [selectedFiles]
    } else {
      _files = selectedFiles
    }

    _files.forEach((file, index) => {
      files.value.push(file)
      fileList.value.push({
        uid: uuidv4(),
        name: file,
        originalName: file,
        status: 'done',
        url: file,
      })
    })

    if (!props.multiple && files.value.length > 1) {
      files.value.splice(0, files.value.length - 1)
      fileList.value.splice(0, fileList.value.length - 1)
    }

    emit('update:firstFile', files.value[0])
    message.success(t('components.workspace.uploaderFieldUse.upload_success'))
  } catch (error) {
    console.error(error)
    message.error(t('components.workspace.uploaderFieldUse.upload_failed'))
  } finally {
    uploading.value = false
  }
}

const { t } = useI18n()

const handleUploaderRemove = file => {
  const index = files.value.indexOf(file.originalName)
  files.value.splice(index, 1)
  fileList.value.splice(index, 1)
}

const imageExtensions = ['jpg', 'jpeg', 'png', 'gif', 'bmp', 'svg', 'webp', 'tif', 'apng'];

const customRequest = async (options) => {
  // Only drop event will trigger customRequest
  const { file, onSuccess } = options
  // droppedFiles are the full paths of the files
  const dropFilePath = await window.pywebview.api.get_drop_file_path(file.name)
  onSuccess({
    ...file,
    name: dropFilePath,
    originalName: dropFilePath,
    status: 'done',
    url: dropFilePath
  })
}

const handleUploaderChange = info => {
  if (info.file.status === 'done') {
    message.success(t('components.workspace.uploaderFieldUse.upload_success', { file: info.file.name }))
    files.value.push(info.file.response.name)
    if (!props.multiple && files.value.length > 1) {
      files.value.splice(0, 1)
    }
    fileList.value.forEach(file => {
      if (file.name === info.file.name) {
        file.originalName = info.file.response.name
        file.url = info.file.response.name
      }
    })
    emit('update:firstFile', files.value[0])
  } else if (info.file.status === 'error') {
    message.error(t('components.workspace.uploaderFieldUse.upload_failed', { file: info.file.name }))
  }
}
</script>

<template>
  <a-upload-dragger v-if="!singleButton" v-model:fileList="fileList" name="file" :multiple="props.multiple"
    :accept="props.supportFileTypes" list-type="picture" :max-count="props.multiple ? 100 : 1"
    :show-upload-list="showUploadList" :isImageUrl="() => false" :openFileDialogOnClick="false"
    :customRequest="customRequest" @click="selectFile($event)" @change="handleUploaderChange"
    @remove="handleUploaderRemove">
    <p class="ant-upload-drag-icon">
      <inbox-out theme="outline" size="32" fill="#28c5e5" />
    </p>
    <p class="ant-upload-text">
      {{ t('components.workspace.uploaderFieldUse.uploader_text') }}
    </p>
    <p class="ant-upload-hint" style="padding: 0 20px;">
      {{ t('components.workspace.uploaderFieldUse.uploader_hint', { fileTypes: props.supportFileTypes }) }}
    </p>
    <template #iconRender="{ file }">
      <FilePdf v-if="file.name.endsWith('.pdf')" theme="filled" size="24" />
      <ImageFiles v-else-if="imageExtensions.includes(file.name.split('.').pop().toLowerCase())" theme="filled"
        size="24" />
      <FileExcel v-else-if="file.name.endsWith('.xlsx')" theme="filled" size="24" />
      <FileWord v-else-if="file.name.endsWith('.docx')" theme="filled" size="24" />
      <FileTxt v-else-if="file.name.endsWith('.txt')" theme="filled" size="24" />
      <FileZip v-else-if="file.name.endsWith('.zip')" theme="filled" size="24" />
      <FileSuccess v-else theme="filled" size="24" />
    </template>
  </a-upload-dragger>
  <a-upload v-else v-model:file-list="fileList" name="file" :multiple="props.multiple" :accept="props.supportFileTypes"
    list-type="picture" :max-count="props.multiple ? 100 : 1" :show-upload-list="showUploadList"
    :openFileDialogOnClick="false" @remove="handleUploaderRemove">
    <a-button :block="singleButtonProps.block" :danger="singleButtonProps.danger" :disabled="singleButtonProps.disabled"
      :ghost="singleButtonProps.ghost" :loading="uploading || singleButton.loading" :shape="singleButtonProps.shape"
      :size="singleButtonProps.size" :type="singleButtonProps.type" @click="selectFile">
      <template #icon>
        <slot name="icon"></slot>
      </template>
    </a-button>
  </a-upload>
</template>