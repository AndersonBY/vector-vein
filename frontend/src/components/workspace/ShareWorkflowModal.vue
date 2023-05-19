<template>
  <a-modal v-model:open="open" :title="t('components.workspace.shareWorkflowModal.share_workflow')" @ok="share"
    :confirmLoading="creatingShare" @cancel="clearShareData">
    <a-form ref="formRef" :model="shareData">
      <a-form-item :rules="[{ required: true }]" :label="t('components.workspace.shareWorkflowModal.title')" name="title">
        <a-input v-model:value="shareData.title">
        </a-input>
      </a-form-item>

      <a-form-item
        :rules="[{ required: true, min: 10, message: t('components.workspace.shareWorkflowModal.brief_min_require', { count: 10 }) }]"
        name="brief">
        <template #label>
          {{ t('components.workspace.shareWorkflowModal.brief') }}
          <QuestionPopover
            :contents="[t('components.workspace.shareWorkflowModal.brief_hint1'), t('components.workspace.shareWorkflowModal.brief_hint2')]" />
        </template>
        <MarkdownEditor v-model:markdown="shareData.brief" :key="templateWid" />
      </a-form-item>

      <a-form-item name="share_to_community">
        <template #label>
          {{ t('components.workspace.shareWorkflowModal.share_to_community') }}
          <QuestionPopover :contents="[t('components.workspace.shareWorkflowModal.share_to_community_brief')]" />
        </template>
        <a-checkbox v-model:checked="shareData.share_to_community">
        </a-checkbox>
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup>
import { ref, reactive, defineComponent, h } from 'vue'
import { useI18n } from 'vue-i18n'
import { Modal } from 'ant-design-vue'
import { TypographyLink } from 'ant-design-vue'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import QuestionPopover from "@/components/QuestionPopover.vue"
import { workflowTemplateAPI } from "@/api/workflow"
import MarkdownEditor from '@/components/MarkdownEditor.vue'

defineComponent({
  name: 'ShareWorkflowModal',
})

const { t } = useI18n()
const userSettingsStore = useUserSettingsStore()
const { language } = storeToRefs(userSettingsStore)

const open = ref(false)
const templateWid = ref()
const shareData = reactive({
  title: '',
  brief: '',
  share_to_community: false,
})
const showModal = ({ wid, title, brief }) => {
  templateWid.value = wid
  shareData.title = title
  shareData.brief = brief
  open.value = true
}
defineExpose({
  showModal,
})

const creatingShare = ref(false)
const formRef = ref()
const clearShareData = () => {
  shareData.title = ''
  shareData.brief = ''
  shareData.share_to_community = false
}
const share = async () => {
  try {
    await formRef.value.validate()
    creatingShare.value = true
    const shareResponse = await workflowTemplateAPI('create', {
      wid: templateWid.value,
      language: language.value,
      ...shareData
    })
    if (shareResponse.status == 200) {
      const link = `https://vectorvein.com/workspace/workflow/template/${shareResponse.data.tid}`
      Modal.success({
        title: t('components.workspace.shareWorkflowModal.share_success'),
        content: () => {
          return h(TypographyLink, { href: link, copyable: true }, [link])
        },
      })
    } else {
      message.error(shareResponse.msg)
    }
    creatingShare.value = false
    open.value = false
  } catch (error) {
    creatingShare.value = false
    console.log('error', error)
  }
}
</script>