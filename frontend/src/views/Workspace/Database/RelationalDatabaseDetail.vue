<script setup>
import { ref, reactive, onBeforeMount, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import {
  Edit,
  DatabaseSetting,
  FileCabinet,
  LoadingFour,
  Delete,
  Upload,
} from '@icon-park/vue-next'
import SQLInteract from '@/components/workspace/database/SQLInteract.vue'
import { formatTime } from '@/utils/util'
import { statusColorMap } from '@/utils/common'
import { relationalDatabaseAPI, relationalDatabaseTableAPI } from '@/api/database'

const { t } = useI18n()
const loading = ref(true)
const activeKey = ref('table')
const route = useRoute()
const router = useRouter()
const databaseId = route.params.databaseId
const databaseInfo = ref({})

const databaseTables = reactive({
  columns: [
    {
      name: t('workspace.databaseDetail.table_name'),
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: t('workspace.databaseDetail.table_status'),
      key: 'status',
      dataIndex: 'status',
      width: '100px',
    },
    {
      title: t('workspace.databaseDetail.table_current_rows'),
      key: 'current_rows',
      dataIndex: 'current_rows',
      width: '120px',
    },
    {
      title: t('common.create_time'),
      key: 'create_time',
      dataIndex: 'create_time',
      sorter: true,
      sortDirections: ['descend', 'ascend'],
      width: '150px',
    },
    {
      title: t('common.action'),
      key: 'action',
      width: '80px',
    }
  ],
  data: [],
  loading: false,
  current: 1,
  pageSize: 10,
  total: 0,
  pagination: computed(() => ({
    total: databaseTables.total,
    current: databaseTables.current,
    pageSize: databaseTables.pageSize,
  })),
  handleTableChange: (page, filters, sorter) => {
    databaseTables.load({
      page_size: page.pageSize,
      page: page.current,
      sort_field: sorter.field,
      sort_order: sorter.order,
    })
  },
  hoverRowTid: null,
  customRow: (record) => {
    return {
      style: { cursor: record.status == 'VA' ? 'pointer' : 'not-allowed' },
      onClick: async (event) => {
        if (record.status != 'VA') return
        if (event.target.classList.contains('ant-table-cell') || event.target.classList.contains('table-name')) {
          await router.push(`/data/relational-db/${databaseId}/table/${record.tid}`)
        }
      },
      onMouseenter: (event) => { databaseTables.hoverRowTid = record.tid },
      onMouseleave: (event) => { databaseTables.hoverRowTid = null }
    };
  },
  load: async (params) => {
    databaseTables.loading = true
    const res = await relationalDatabaseTableAPI('list', {
      rid: databaseId,
      ...params,
    })
    if (res.status == 200) {
      databaseTables.data = res.data.tables.map(item => {
        item.create_time = formatTime(item.create_time)
        return item
      })
    } else {
      message.error(res.msg)
    }
    databaseTables.total = res.data.total
    databaseTables.pageSize = res.data.page_size
    databaseTables.current = res.data.page
    databaseTables.loading = false
  }
})
const getDatabase = async () => {
  databaseTables.load({})
  const getDatabaseResponse = await relationalDatabaseAPI('get', { rid: databaseId })
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

const deleteTable = async (tid) => {
  const response = await relationalDatabaseTableAPI('delete', { tid })
  if (response.status === 200) {
    message.success(t('workspace.databaseDetail.delete_success'))
  } else {
    message.error(t('workspace.databaseDetail.delete_failed'))
  }
  await databaseTables.load({})
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
    const response = await relationalDatabaseAPI('update', {
      'rid': databaseId,
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
      <a-col :xl="18" :lg="20" :md="22" :sm="24" :xs="24">
        <a-breadcrumb>
          <a-breadcrumb-item>
            <router-link :to="`/data?tab=relational-database`">
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
      <a-col :xl="18" :lg="20" :md="22" :sm="24" :xs="24">
        <a-card :loading="loading">
          <template #title>
            <a-flex vertical gap="small" class="card-title">
              <a-typography-title :level="2" class="black-text" style="margin-bottom: 0;"
                :content="databaseInfo.name" />
            </a-flex>
          </template>
          <template #extra>
            <a-flex gap="middle">
              <a-tooltip :title="t('workspace.databaseDetail.modify_database_info')">
                <a-button type="text" size="large" @click="infoEditorModal.show">
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
                <a-button type="text" size="large" @click="router.push(`/data/relational-db/${databaseId}/create`)">
                  <template #icon>
                    <Upload />
                  </template>
                </a-button>
              </a-tooltip>
            </a-flex>
          </template>
          <a-tabs v-model:activeKey="activeKey" tab-position="left">
            <a-tab-pane key="table" :tab="t('workspace.databaseDetail.table')">
              <a-table :loading="databaseTables.loading" :customRow="databaseTables.customRow"
                :columns="databaseTables.columns" :data-source="databaseTables.data"
                :pagination="databaseTables.pagination" @change="databaseTables.handleTableChange">
                <template #headerCell="{ column }">
                  <template v-if="column.key === 'name'">
                    {{ t('workspace.databaseDetail.table_name') }}
                  </template>
                </template>
                <template #bodyCell="{ column, record }">
                  <template v-if="column.key === 'name'">
                    <a-typography-text v-if="record.status == 'PR'" disabled class="table-name">
                      {{ record.name }}
                      <LoadingFour :spin="true" />
                    </a-typography-text>
                    <a-typography-text v-else class="table-name">
                      {{ record.name }}
                    </a-typography-text>
                  </template>
                  <template v-else-if="column.key === 'status'">
                    <a-tag :color="statusColorMap[record.status]" :bordered="false">
                      {{ t(`status.${record.status}`) }}
                    </a-tag>
                  </template>
                  <template v-else-if="column.key === 'action'">
                    <template v-if="record.status != 'PR'">
                      <a-popconfirm placement="leftTop" :title="t('workspace.databaseDetail.delete_confirm')"
                        @confirm="deleteTable(record.tid)">
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
            </a-tab-pane>
            <a-tab-pane key="run-sql" :tab="t('workspace.databaseDetail.run_sql')">
              <SQLInteract :database-id="databaseId" />
            </a-tab-pane>
          </a-tabs>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<style scoped>
.dataspace-container {
  padding: 16px;
}

.dataspace-container .card-title {
  padding: 10px 0;
}
</style>