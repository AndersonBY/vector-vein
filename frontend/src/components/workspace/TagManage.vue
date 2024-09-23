<script setup>
import { reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { Delete } from '@icon-park/vue-next'
import { workflowTagAPI } from "@/api/workflow"

const { t } = useI18n()

const tags = reactive({
  loading: false,
  data: [],
  columns: [
    {
      title: t('common.title'),
      dataIndex: 'title',
      key: 'title'
    },
    {
      title: t('components.workspace.tagManage.color'),
      dataIndex: 'color',
      key: 'color'
    },
    {
      title: t('common.action'),
      dataIndex: 'action',
      key: 'action',
    }
  ],
  delete: async (tid) => {
    await workflowTagAPI('delete', { tid })
    tags.data = tags.data.filter(tag => tag.tid !== tid)
  },
  save: async () => {
    tags.loading = true
    const data = tags.data.map(tag => {
      return {
        tid: tag.tid,
        title: tag.title,
        color: tag.color
      }
    })
    await workflowTagAPI('update', { data })
    tags.loading = false
    tagManageModal.visible = false
  },
})

const tagManageModal = reactive({
  visible: false,
  title: t('components.workspace.tagManage.title'),
  footer: null,
  onCancel: () => {
    tagManageModal.visible = false
  },
  open: async () => {
    tags.loading = true
    const res = await workflowTagAPI('list', { user_only: true })
    tags.data = res.data
    tags.loading = false
    tagManageModal.visible = true
  }
})
</script>

<template>
  <div>
    <a-typography-link @click="tagManageModal.open">
      {{ tagManageModal.title }}
    </a-typography-link>
    <a-modal v-model:open="tagManageModal.visible" :title="tagManageModal.title" @ok="tags.save"
      :okText="t('common.save')" :cancelText="t('common.cancel')" @cancel="tagManageModal.onCancel">
      <a-table :columns="tags.columns" :dataSource="tags.data" :loading="tags.loading" rowKey="tid">
        <template #bodyCell="{ column, record }">
          <template v-if="column.dataIndex === 'title'">
            <a-typography-text v-model:content="record.title" editable></a-typography-text>
          </template>
          <template v-else-if="column.dataIndex === 'color'">
            <a-tag :color="record.color">{{ record.title }}</a-tag>
            <a-typography-text v-model:content="record.color" editable></a-typography-text>
          </template>
          <template v-else-if="column.dataIndex === 'action'">
            <a-popconfirm :title="t('components.workspace.tagManage.delete_tag_confirm')"
              @confirm="tags.delete(record.tid)">
              <a-button type="text" danger>
                <template #icon>
                  <Delete />
                </template>
              </a-button>
            </a-popconfirm>
          </template>
        </template>
      </a-table>
    </a-modal>
  </div>
</template>