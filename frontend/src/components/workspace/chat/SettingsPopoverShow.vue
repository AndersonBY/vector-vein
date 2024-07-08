<script setup>
import { ref } from "vue"
import { useI18n } from 'vue-i18n'
import { Setting } from '@icon-park/vue-next'
import IconButton from '@/components/IconButton.vue'
import SimpleFormItem from '@/components/SimpleFormItem.vue'
import TextOutput from "@/components/TextOutput.vue"

const props = defineProps({
  settings: {
    type: Object,
    default: () => ({}),
  },
})

const { t } = useI18n()
const open = ref(false)
</script>

<template>
  <div>
    <a-popover :title="t('workspace.chatSpace.agent_settings')" placement="topLeft">
      <template #content>
      </template>
      <IconButton :text="t('workspace.chatSpace.agent_settings')" size="small" type="text" shape="round"
        @click="open = true">
        <template #icon>
          <Setting />
        </template>
      </IconButton>
    </a-popover>
    <a-modal :open="open" :title="t('workspace.chatSpace.agent_settings')" width="700px" :footer="null"
      @cancel="open = false">
      <a-row justify="space-between" align="middle" :gutter="[16, 16]">
        <a-col :span="24">
          <a-typography-title :level="4">
            {{ t('workspace.chatSpace.system_prompt') }}
          </a-typography-title>
          <TextOutput :text="settings.system_prompt" :showCopy="false" />
          <a-divider />
          <SimpleFormItem type="checkbox" :title="t('workspace.chatSpace.auto_run_workflow')"
            :description="t('workspace.chatSpace.auto_run_workflow_description')" v-model="settings.auto_run_workflow"
            :disabled="true" />
          <a-divider />
          <SimpleFormItem type="checkbox" :title="t('workspace.chatSpace.native_multimodal')"
            :description="t('workspace.chatSpace.native_multimodal_description')" v-model="settings.native_multimodal"
            :disabled="true" />
          <a-divider />
          <SimpleFormItem type="checkbox" :title="t('workspace.chatSpace.agent_audio_reply')"
            :description="t('workspace.chatSpace.agent_audio_reply_description')" v-model="settings.agent_audio_reply"
            :disabled="true" />
          <a-divider />
          <SimpleFormItem v-show="settings.agent_audio_reply" type="cascader"
            :title="t('workspace.chatSpace.agent_audio_voice')" v-model="settings.agent_audio_voice" :disabled="true" />
        </a-col>
      </a-row>
    </a-modal>
  </div>
</template>

<style scoped>
.markdown-body {
  padding: 8px;
  background-color: #f0f0f0;
  border-radius: 10px;
}
</style>