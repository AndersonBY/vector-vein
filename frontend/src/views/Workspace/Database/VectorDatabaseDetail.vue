<script setup>
import { ref, reactive, onBeforeMount, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import { Edit, DatabaseSetting, FileCabinet, LoadingFour, AudioFile, PictureOne, Delete, Upload } from '@icon-park/vue-next'
import { databaseAPI, databaseObjectAPI } from '@/api/database'
import { formatTime } from '@/utils/util'

const { t } = useI18n()
const loading = ref(true)
const route = useRoute()
const router = useRouter()
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
    width: '100px',
  }, {
    title: t('workspace.databaseDetail.source_url'),
    key: 'source_url',
    dataIndex: 'source_url',
    width: '100px',
  }, {
    title: t('common.create_time'),
    key: 'create_time',
    dataIndex: 'create_time',
    sorter: true,
    sortDirections: ['descend', 'ascend'],
    width: '150px',
  }, {
    title: t('common.action'),
    key: 'action',
    width: '80px',
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
  hoverRowOid: null,
  customRow: (record) => {
    return {
      style: { cursor: 'pointer' },
      onClick: async (event) => {
        if (event.target.classList.contains('ant-table-cell') || event.target.classList.contains('object-title')) {
          await router.push(`/data/vector-db/${databaseId}/object/${record.oid}`)
        }
      },
      onMouseenter: (event) => { databaseObjects.hoverRowOid = record.vid },
      onMouseleave: (event) => { databaseObjects.hoverRowOid = null }
    };
  },
  load: async (params) => {
    databaseObjects.loading = true
    const res = await databaseObjectAPI('list', {
      vid: databaseId,
      ...params,
    })
    if (res.status == 200) {
      databaseObjects.data = res.data.objects.map(item => {
        item.create_time = formatTime(item.create_time)
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
  await databaseObjects.load({})
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

const navigateToCreate = async () => {
  await router.push(`/data/${databaseId}/create`)
}

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

const infoEditorModal = reactive({
  open: false,
  form: {
    name: databaseInfo.value.name,
  },
  show: () => {
    infoEditorModal.open = true
    infoEditorModal.form.name = databaseInfo.value.name
  },
  ok: async () => {
    const response = await databaseAPI('update', {
      'vid': databaseId,
      ...infoEditorModal.form,
    })
    if (response.status == 200) {
      message.success(t('common.save_success'))
      databaseInfo.value.name = infoEditorModal.form.name
      infoEditorModal.open = false
    } else {
      message.error(response.msg)
    }
  },
})
</script>

<template>
  <div class="dataspace-container">
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
            <DatabaseSetting />
            {{ databaseInfo.name }}
          </a-breadcrumb-item>
        </a-breadcrumb>
      </a-col>
      <a-col :xl="16" :lg="18" :md="20" :sm="22" :xs="24">
        <a-card :loading="loading">
          <template #title>
            <a-typography-title :level="2" class="black-text" style="margin-bottom: 0;" :content="databaseInfo.name" />
          </template>
          <template #extra>
            <a-flex gap="middle">
              <a-tooltip :title="t('workspace.databaseDetail.modify_database_info')">
                <a-button type="text" size="large" class="title-edit-button" @click="infoEditorModal.show">
                  <template #icon>
                    <Edit />
                  </template>
                </a-button>
              </a-tooltip>
              <a-modal :title="t('workspace.databaseDetail.modify_database_info')" @ok="infoEditorModal.ok"
                :confirm-loading="infoEditorModal.createLoading" v-model:open="infoEditorModal.open">
                <a-form :model="databaseInfo" layout="vertical">
                  <a-form-item :label="t('workspace.dataSpace.database_name')" name="name"
                    :rules="[{ required: true }]">
                    <a-input v-model:value="infoEditorModal.form.name" />
                  </a-form-item>
                </a-form>
              </a-modal>
              <a-tooltip :title="t('workspace.databaseDetail.add_object')">
                <a-button type="text" size="large" @click="navigateToCreate">

                  <template #icon>
                    <Upload />
                  </template>
                </a-button>
              </a-tooltip>
            </a-flex>
          </template>

          <a-table :loading="databaseObjects.loading" :customRow="databaseObjects.customRow"
            :columns="databaseObjects.columns" :data-source="databaseObjects.data"
            :pagination="databaseObjects.pagination" @change="databaseObjects.handleTableChange">
            <template #headerCell="{ column }">
              <template v-if="column.key === 'title'">
                {{ t('workspace.databaseDetail.object_title') }}
              </template>
            </template>

            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'title'">
                <a-typography-text disabled v-if="record.status == 'PR'">
                  {{ record.title }}
                  <LoadingFour :spin="true" />
                </a-typography-text>
                <a-typography-text class="object-title" v-else>
                  {{ record.title }}
                </a-typography-text>
              </template>
              <template v-else-if="column.key === 'data_type'">
                <span>
                  <a-tag v-if="record.data_type.toUpperCase() == 'TEXT'" color="blue" :bordered="false">
                    <Edit />
                    {{ t(`workspace.databaseDetail.data_type_${record.data_type.toUpperCase()}`) }}
                  </a-tag>
                  <a-tag v-if="record.data_type.toUpperCase() == 'IMAGE'" color="green" :bordered="false">
                    <PictureOne />
                    {{ t(`workspace.databaseDetail.data_type_${record.data_type.toUpperCase()}`) }}
                  </a-tag>
                  <a-tag v-if="record.data_type.toUpperCase() == 'AUDIO'" color="purple" :bordered="false">
                    <AudioFile />
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
                  <a-popconfirm placement="leftTop" :title="t('workspace.databaseDetail.delete_confirm')"
                    @confirm="deleteObject(record.oid)">
                    <a-button type="text" danger>
                      <template #icon>
                        <Delete />
                      </template>
                    </a-button>
                  </a-popconfirm>
                </template>
              </template>
            </template>
          </a-table>

        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<style scoped>
.dataspace-container {
  padding: 16px;
}
</style>