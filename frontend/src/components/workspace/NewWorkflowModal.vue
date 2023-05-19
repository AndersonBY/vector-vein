<template>
  <a-modal v-model:open="open" width="50vw" :title="t('components.workspace.newWorkflowModal.create_new_workflow')"
    :footer="null">
    <a-row :gutter="[16, 16]">
      <a-col :xs="24" :md="12" :lg="6">
        <a-card class="template-card-small" hoverable style="width: 240px" @click="create('empty')">
          <div class="empty-workflow-template">
            <a-typography-text class="text-primary">
              <PlusOutlined style="font-size: 100px;" />
            </a-typography-text>
            <a-typography-text>
              {{ t('components.workspace.newWorkflowModal.empty_workflow') }}
            </a-typography-text>
          </div>
        </a-card>
      </a-col>
    </a-row>
  </a-modal>
</template>

<script setup>
import { PlusOutlined } from '@ant-design/icons-vue'
import { ref, defineComponent } from 'vue'
import { useI18n } from 'vue-i18n'

defineComponent({
  name: 'NewWorkflowModal',
})

const emit = defineEmits(['create'])

const { t } = useI18n()

const open = ref(false)
const showModal = () => {
  open.value = true
}
const create = (templateId) => {
  open.value = false
  emit('create', { id: templateId })
}
defineExpose({
  showModal,
})
</script>

<style>
.template-card {
  cursor: pointer;
  height: 256px;
}

.empty-workflow-template {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 180px;
}
</style>