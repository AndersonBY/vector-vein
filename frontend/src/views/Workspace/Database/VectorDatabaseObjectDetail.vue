<script setup>
import { ref, reactive, onBeforeMount, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from "vue-router"
import { message } from 'ant-design-vue'
import { DocDetail, DatabaseSetting, FileCabinet, Check, Close, Edit } from '@icon-park/vue-next'
import VueMarkdown from 'vue-markdown-render'
import { databaseAPI, databaseObjectAPI } from '@/api/database'

const { t } = useI18n()
const loading = ref(true)
const route = useRoute()
const databaseId = route.params.databaseId
const objectId = route.params.objectId

const database = ref({})
const databaseObject = ref({})

const getDatabase = async () => {
  const getDatabaseResponse = await databaseAPI('get', { vid: databaseId })
  if (getDatabaseResponse.status == 200) {
    database.value = getDatabaseResponse.data
  } else {
    message.error(getDatabaseResponse.msg)
  }
}

const getDatabaseObject = async () => {
  const getDatabaseObjectResponse = await databaseObjectAPI('get', { oid: objectId })
  if (getDatabaseObjectResponse.status == 200) {
    databaseObject.value = getDatabaseObjectResponse.data
  } else {
    message.error(getDatabaseObjectResponse.msg)
  }
}

onBeforeMount(async () => {
  loading.value = true
  await Promise.all([getDatabase(), getDatabaseObject()])
  databaseObjectSegments.data = databaseObject.value.raw_data.segments
  loading.value = false
})

const activeKey = ref('segments')
const databaseObjectSegments = reactive({
  columns: [
    {
      title: '#',
      key: 'index',
      dataIndex: 'index',
      width: '50px',
    },
    {
      title: t('workspace.databaseObjectDetail.segment_text'),
      key: 'text',
      dataIndex: 'text',
      ellipsis: true,
    },
    {
      title: t('workspace.databaseObjectDetail.segment_word_counts'),
      key: 'word_counts',
      dataIndex: 'word_counts',
      width: '100px',
    },
  ],
  data: [],
  loading: false,
  current: 1,
  pageSize: 10,
  total: 0,
  pagination: computed(() => ({
    total: databaseObjectSegments.total,
    current: databaseObjectSegments.current,
    pageSize: databaseObjectSegments.pageSize,
  })),
  handleTableChange: (page, filters, sorter) => {
    databaseObjectSegments.load({
      page_size: page.pageSize,
      page: page.current,
      sort_field: sorter.field,
      sort_order: sorter.order,
    })
  },
  hoverRowOid: null,
  customRow: (record) => {
    return {
      style: { cursor: 'pointer' },
      onClick: async (event) => {
        if (event.target.classList.contains('ant-table-cell') || event.target.classList.contains('object-title')) {
          segmentDetailModal.segmentIndex = record.index
          segmentDetailModal.text = record.text
          segmentDetailModal.keywords = record.keywords
          segmentDetailModal.open = true
        }
      },
      onMouseenter: (event) => { databaseObjectSegments.hoverRowOid = record.vid },
      onMouseleave: (event) => { databaseObjectSegments.hoverRowOid = null }
    };
  },
})

const segmentDetailModal = reactive({
  open: false,
  segmentIndex: 0,
  text: '',
  keywords: [],
})

const infoEditorModal = reactive({
  open: false,
  form: {
    title: databaseObject.value.title,
  },
  show: () => {
    infoEditorModal.open = true
    infoEditorModal.form.title = databaseObject.value.title
  },
  ok: async () => {
    const response = await databaseObjectAPI('update', {
      'oid': databaseObject.value.oid,
      ...infoEditorModal.form,
    })
    if (response.status == 200) {
      message.success(t('common.save_success'))
      databaseObject.value.title = infoEditorModal.form.title
      infoEditorModal.open = false
    } else {
      message.error(response.msg)
    }
  },
})
</script>

<template>
  <div class="loading-container" v-if="loading">
    <a-spin />
  </div>
  <div class=" dataspace-container" v-else>
    <a-row align="center" :gutter="[16, 16]">
      <a-col :xl="16" :lg="18" :md="20" :sm="22" :xs="24">
        <a-breadcrumb>
          <a-breadcrumb-item>
            <router-link :to="`/data`">
              <FileCabinet />
              {{ t('components.layout.basicHeader.data_space') }}
            </router-link>
          </a-breadcrumb-item>
          <a-breadcrumb-item>
            <router-link :to="`/data/vector-db/${database.vid}`">
              <DatabaseSetting />
              {{ database.name }}
            </router-link>
          </a-breadcrumb-item>
          <a-breadcrumb-item>{{ databaseObject.title }}</a-breadcrumb-item>
        </a-breadcrumb>
      </a-col>
      <a-col :xl="16" :lg="18" :md="20" :sm="22" :xs="24">
        <a-card :loading="loading">
          <template #title>
            <a-flex justify="space-between" align="center">
              <div>
                <DocDetail />
                {{ databaseObject.title }}
              </div>
              <a-tooltip :title="t('workspace.databaseObjectDetail.modify_object_info')">
                <a-button type="text" size="large" @click="infoEditorModal.show">
                  <template #icon>
                    <Edit />
                  </template>
                </a-button>
              </a-tooltip>
              <a-modal :title="t('workspace.databaseObjectDetail.modify_object_info')" @ok="infoEditorModal.ok"
                :confirm-loading="infoEditorModal.createLoading" v-model:open="infoEditorModal.open">
                <a-form :model="infoEditorModal.form" layout="vertical">
                  <a-form-item :label="t('workspace.databaseObjectDetail.object_title')" name="title"
                    :rules="[{ required: true }]">
                    <a-input v-model:value="infoEditorModal.form.title" />
                  </a-form-item>
                </a-form>
              </a-modal>
            </a-flex>
          </template>
          <a-tabs v-model:activeKey="activeKey" tab-position="left">
            <a-tab-pane key="segments" :tab="t('workspace.databaseObjectDetail.segments')">
              <a-table :customRow="databaseObjectSegments.customRow" :columns="databaseObjectSegments.columns"
                :data-source="databaseObjectSegments.data" :pagination="databaseObjectSegments.pagination">

                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'keywords'">
                    {{ record.keywords.join(', ') }}
                  </template>

                  <template v-else-if="column.key === 'action'">
                    <template v-if="record.status != 'PR'">
                      <a-popconfirm placement="leftTop" :title="t('workspace.databaseDetail.delete_confirm')"
                        @confirm="deleteObject(record.oid)">
                        <a-typography-link type="danger">
                          {{ t('workspace.databaseDetail.delete') }}
                        </a-typography-link>
                      </a-popconfirm>
                    </template>
                  </template>
                </template>
              </a-table>
            </a-tab-pane>

            <a-tab-pane key="full-document" :tab="t('workspace.databaseObjectDetail.full_document')">
              <a-typography-link :href="databaseObject.source_url" target="_blank"
                v-if="databaseObject.source_url?.length > 0">
                {{ t('workspace.databaseObjectDetail.source_url') }}
              </a-typography-link>
              <a-divider v-if="databaseObject.source_url?.length > 0"></a-divider>
              <VueMarkdown v-highlight :source="databaseObject.raw_data?.text || ''"
                class="custom-scrollbar markdown-body custom-hljs" />
            </a-tab-pane>

            <a-tab-pane key="params_info" :tab="t('workspace.databaseObjectDetail.params_info')">
              <a-descriptions bordered>

                <a-descriptions-item :label="t('workspace.databaseObjectCreate.split_method')">
                  {{
                    databaseObject.info?.process_rules?.split_method ?
                      t(`workspace.databaseObjectCreate.split_method_${databaseObject.info?.process_rules?.split_method}`) :
                      ''
                  }}
                </a-descriptions-item>
                <a-descriptions-item :label="t('workspace.databaseObjectCreate.chunk_length')"
                  v-if="databaseObject.info?.process_rules?.split_method != 'delimeter'">
                  {{ databaseObject.info?.process_rules?.chunk_length }}
                </a-descriptions-item>
                <a-descriptions-item :label="t('workspace.databaseObjectCreate.delimiter')"
                  v-if="databaseObject.info?.process_rules?.split_method == 'delimeter'">
                  {{ databaseObject.info?.process_rules?.delimiter }}
                </a-descriptions-item>
                <a-descriptions-item :label="t('workspace.databaseObjectCreate.remove_url_and_email')">
                  <Check v-if="databaseObject.info?.process_rules?.remove_url_and_email" />
                  <Close v-else />
                </a-descriptions-item>

                <a-descriptions-item :label="t('workspace.databaseObjectDetail.paragraph_counts')">
                  {{ databaseObject.info?.paragraph_counts }}
                </a-descriptions-item>
                <a-descriptions-item :label="t('workspace.databaseObjectDetail.word_counts')">
                  {{ databaseObject.info?.word_counts }}
                </a-descriptions-item>

              </a-descriptions>
            </a-tab-pane>
          </a-tabs>

          <a-modal v-model:open="segmentDetailModal.open" :title="`# ${segmentDetailModal.segmentIndex}`"
            @cancel="segmentDetailModal.open = false" :footer="null">
            <a-typography-paragraph :content="segmentDetailModal.text">
            </a-typography-paragraph>
          </a-modal>

        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<style scoped>
.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 80vh;
}

.dataspace-container {
  padding: 16px;
}
</style>