<script setup>
import { useI18n } from 'vue-i18n'
import { InboxOut, Delete, FileSuccess } from '@icon-park/vue-next'
import { message } from 'ant-design-vue'

const props = defineProps({
  multiple: {
    type: Boolean,
    required: false,
    default: false,
  },
})

const files = defineModel()

const { t } = useI18n()

const remove = file => {
  const index = files.value.indexOf(file)
  files.value.splice(index, 1)
}

const upload = async () => {
  try {
    const selectedFiles = await window.pywebview.api.open_file_dialog(props.multiple)
    selectedFiles.forEach(file => {
      message.success(t('components.workspace.uploaderFieldUse.upload_success', { file: file }))
      files.value.push(file)
      if (!props.multiple && files.value.length > 1) {
        files.value.splice(0, 1)
      }
    })
  } catch (error) {
    console.log(error)
    message.error(t('components.workspace.uploaderFieldUse.upload_failed'))
  }
}
</script>

<template>
  <a-flex vertical>
    <a-button type="dashed" block @click="upload">
      <template #icon>
        <InboxOut />
      </template>
      {{ t('components.workspace.uploaderFieldUse.upload') }}
    </a-button>
    <a-list :data-source="files">

      <template #renderItem="{ item }">
        <a-list-item>
          <template #actions>
            <a-button type="text" @click="remove(item)">
              <template #icon>
                <Delete fill="#ff4d4f" />
              </template>
            </a-button>
          </template>
          <a-list-item-meta>

            <template #title>
              <a-typography-text>{{ item }}</a-typography-text>
            </template>

            <template #avatar>
              <FileSuccess />
            </template>
          </a-list-item-meta>
        </a-list-item>
      </template>
    </a-list>
  </a-flex>
</template>