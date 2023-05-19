<template>
  <div class="dataspace-container">
    <a-row :gutter="[16, 16]">
      <a-col :span="24">
        <a-card :loading="loading">
          <template #title>
            <DatabaseOutlined />
            {{ databaseInfo.name }}
          </template>
          <template #extra>
            <a-button type="primary" @click="addNewDataModal.open = true">
              {{ t('workspace.databaseDetail.add_object') }}
            </a-button>
            <a-modal v-model:open="addNewDataModal.open" :title="t('workspace.databaseDetail.add_object')"
              @ok="addNewDataModal.create" :confirmLoading="addNewDataModal.creating">

              <a-form-item :label="t('workspace.databaseDetail.add_method')">
                <a-radio-group v-model:value="addNewDataModal.data.add_method">
                  <a-radio-button value="url">
                    {{ t('workspace.databaseDetail.add_method_url') }}
                  </a-radio-button>
                  <a-radio-button value="files">
                    {{ t('workspace.databaseDetail.add_method_files') }}
                  </a-radio-button>
                  <a-radio-button value="text">
                    {{ t('workspace.databaseDetail.add_method_text') }}
                  </a-radio-button>
                </a-radio-group>
              </a-form-item>

              <template v-if="addNewDataModal.data.add_method == 'url'">
                <a-form-item :label="t('workspace.databaseDetail.use_oversea_crawler')"
                  v-if="addNewDataModal.data.crawl_data_from_url">
                  <a-checkbox v-model:checked="addNewDataModal.data.use_oversea_crawler" />
                </a-form-item>
                <a-form-item :label="t('workspace.databaseDetail.object_source_url')">
                  <a-input v-model:value="addNewDataModal.data.source_url" />
                </a-form-item>
              </template>

              <template v-if="addNewDataModal.data.add_method == 'files'">
                <UploaderFieldUse v-model="addNewDataModal.data.files" :multiple="true" />
              </template>

              <template v-if="addNewDataModal.data.add_method == 'text'">
                <a-form-item :label="t('workspace.databaseDetail.object_title')">
                  <a-input v-model:value="addNewDataModal.data.title" />
                </a-form-item>
                <a-form-item :label="t('workspace.databaseDetail.object_content')">
                  <a-textarea v-model:value="addNewDataModal.data.content" :auto-size="true" />
                </a-form-item>
              </template>

            </a-modal>
          </template>

          <a-table :loading="databaseObjects.loading" :columns="databaseObjects.columns"
            :data-source="databaseObjects.data" :pagination="databaseObjects.pagination"
            @change="databaseObjects.handleTableChange">
            <template #headerCell="{ column }">
              <template v-if="column.key === 'title'">
                {{ t('workspace.databaseDetail.object_title') }}
              </template>
            </template>

            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'title'">
                <a-typography-text disabled v-if="record.status == 'PR'">
                  {{ record.title }}
                  <LoadingOutlined />
                </a-typography-text>
                <a-typography-text v-else>
                  {{ record.title }}
                </a-typography-text>
              </template>
              <template v-else-if="column.key === 'data_type'">
                <span>
                  <a-tag v-if="record.data_type.toUpperCase() == 'TEXT'" color="blue">
                    <EditOutlined />
                    {{ t(`workspace.databaseDetail.data_type_${record.data_type.toUpperCase()}`) }}
                  </a-tag>
                  <a-tag v-if="record.data_type.toUpperCase() == 'IMAGE'" color="green">
                    <PictureOutlined />
                    {{ t(`workspace.databaseDetail.data_type_${record.data_type.toUpperCase()}`) }}
                  </a-tag>
                  <a-tag v-if="record.data_type.toUpperCase() == 'AUDIO'" color="purple">
                    <AudioOutlined />
                    {{ t(`workspace.databaseDetail.data_type_${record.data_type.toUpperCase()}`) }}
                  </a-tag>
                </span>
              </template>
              <template v-else-if="column.key === 'source_url'">
                <a-typography-link :href="record.source_url" target="_blank" v-if="record.source_url?.length > 0">
                  {{ t('workspace.databaseDetail.source_url') }}
                </a-typography-link>
                <a-typography-text disabled v-else>
                  {{ t('workspace.databaseDetail.source_url') }}
                </a-typography-text>
              </template>
              <template v-else-if="column.key === 'action'">
                <template v-if="record.status != 'PR'">
                  <a-typography-link @click="objectDetailModal.load(record.oid)">
                    {{ t('workspace.databaseDetail.check_detail_data') }}
                  </a-typography-link>
                  <a-divider type="vertical" />
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

          <a-modal v-model:open="objectDetailModal.open" @ok="objectDetailModal.create" :footer="null">
            <template #title>
              {{ objectDetailModal.data.title }}
            </template>
            <a-spin :spinning="objectDetailModal.loading">
              <a-typography-link :href="objectDetailModal.data.source_url" target="_blank"
                v-if="objectDetailModal.data.source_url?.length > 0">
                {{ t('workspace.databaseDetail.source_url') }}
              </a-typography-link>
              <a-typography-paragraph>
                {{ objectDetailModal.data.raw_data?.text }}
              </a-typography-paragraph>
            </a-spin>
          </a-modal>

        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup>
import { AudioOutlined, DatabaseOutlined, EditOutlined, LoadingOutlined, PictureOutlined } from '@ant-design/icons-vue'
import { ref, reactive, defineComponent, onBeforeMount, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from "vue-router"
import { message } from 'ant-design-vue'
import UploaderFieldUse from '@/components/workspace/UploaderFieldUse.vue'
import { databaseAPI, databaseObjectAPI } from '@/api/database'

defineComponent({
  name: 'DataSpace',
})

const { t } = useI18n()
const loading = ref(true)
const route = useRoute()
const databaseId = route.params.databaseId

const databaseInfo = ref({})

const databaseObjects = reactive({
  columns: [{
    name: t('workspace.databaseDetail.object_title'),
    dataIndex: 'title',
    key: 'title',
  }, {
    title: t('workspace.databaseDetail.data_type'),
    key: 'data_type',
    dataIndex: 'data_type',
  }, {
    title: t('workspace.databaseDetail.source_url'),
    key: 'source_url',
    dataIndex: 'source_url',
  }, {
    title: t('common.create_time'),
    key: 'create_time',
    dataIndex: 'create_time',
    sorter: true,
    sortDirections: ['descend', 'ascend'],
  }, {
    title: t('common.action'),
    key: 'action',
  }],
  data: [],
  loading: false,
  current: 1,
  pageSize: 10,
  total: 0,
  pagination: computed(() => ({
    total: databaseObjects.total,
    current: databaseObjects.current,
    pageSize: databaseObjects.pageSize,
  })),
  handleTableChange: (page, filters, sorter) => {
    databaseObjects.load({
      page_size: page.pageSize,
      page: page.current,
      sort_field: sorter.field,
      sort_order: sorter.order,
    })
  },
  load: async (params) => {
    databaseObjects.loading = true
    const res = await databaseObjectAPI('list', {
      vid: databaseId,
      ...params,
    })
    if (res.status == 200) {
      databaseObjects.data = res.data.objects.map(item => {
        item.create_time = new Date(item.create_time).toLocaleString()
        return item
      })
    } else {
      message.error(res.msg)
    }
    databaseObjects.total = res.data.total
    databaseObjects.pageSize = res.data.page_size
    databaseObjects.current = res.data.page
    databaseObjects.loading = false
  }
})
const getDatabase = async () => {
  databaseObjects.load({})
  const getDatabaseResponse = await databaseAPI('get', { vid: databaseId })
  if (getDatabaseResponse.status == 200) {
    databaseInfo.value = getDatabaseResponse.data
    loading.value = false
  } else {
    message.error(getDatabaseResponse.msg)
  }
}

onBeforeMount(async () => {
  await getDatabase()
})

const addNewDataModal = reactive({
  open: ref(false),
  creating: ref(false),
  data: {
    add_method: 'url',
    title: '',
    source_url: '',
    use_oversea_crawler: false,
    files: [],
    content: '',
  },
  create: async () => {
    if (addNewDataModal.data.add_method == 'text' && addNewDataModal.data.content.length == 0) {
      message.error(t('workspace.databaseDetail.content_empty'))
      return
    }
    addNewDataModal.creating = true
    const response = await databaseObjectAPI('create', {
      vid: databaseId,
      ...addNewDataModal.data,
    })
    if (response.status === 200) {
      message.success(t('workspace.databaseDetail.create_success'))
    } else {
      message.error(t('workspace.databaseDetail.create_failed'))
    }
    databaseObjects.load({})
    addNewDataModal.creating = false
    addNewDataModal.open = false
  },
})

const objectDetailModal = reactive({
  open: false,
  loading: false,
  data: {},
  load: async (objectId) => {
    objectDetailModal.loading = true
    objectDetailModal.open = true
    const response = await databaseObjectAPI('get', { oid: objectId })
    if (response.status === 200) {
      objectDetailModal.data = response.data
    } else {
      message.error(t('workspace.databaseDetail.get_object_failed'))
    }
    objectDetailModal.loading = false
  },
})

const deleteObject = (objectId) => {
  databaseObjectAPI('delete', { oid: objectId }).then(response => {
    if (response.status === 200) {
      message.success(t('workspace.databaseDetail.delete_success'))
    } else {
      message.error(t('workspace.databaseDetail.delete_failed'))
    }
    databaseObjects.load({})
  })
}
</script>

<style></style>