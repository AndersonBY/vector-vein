<script setup>
import { ref, reactive, onBeforeMount, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute } from "vue-router"
import { message } from 'ant-design-vue'
import {
  DocDetail,
  DatabaseSetting,
  FileCabinet,
  Delete,
  Edit,
  Close,
  Save,
  AddItem,
  Refresh,
} from '@icon-park/vue-next'
import UploaderFieldUse from '@/components/workspace/UploaderFieldUse.vue'
import { relationalDatabaseAPI, relationalDatabaseTableAPI, relationalDatabaseTableRecordAPI } from '@/api/database'

const { t } = useI18n()
const loading = ref(true)
const route = useRoute()
const databaseId = route.params.databaseId
const tableId = route.params.tableId

const database = ref({})
const table = ref({})
const tableLoaded = ref(false)

const getDatabase = async () => {
  const res = await relationalDatabaseAPI('get', { rid: databaseId })
  if (res.status == 200) {
    database.value = res.data
  } else {
    message.error(res.msg)
  }
}

const getTable = async (simple = true) => {
  const res = await relationalDatabaseTableAPI('get', { tid: tableId, simple })
  if (res.status == 200) {
    table.value = res.data
    tableRecords.schema = res.data.schema
  } else {
    message.error(res.msg)
  }
}

onBeforeMount(async () => {
  loading.value = true
  await Promise.all([getDatabase(), getTable()])
  loading.value = false
})

const activeKey = ref('sheet')

const tableSchemaColumns = [
  {
    title: t('workspace.databaseTableCreate.column_name'),
    key: 'name',
    dataIndex: 'name',
  },
  {
    title: t('workspace.databaseTableCreate.column_type'),
    key: 'type',
    dataIndex: 'type',
    width: '150px',
  },
  {
    title: t('workspace.databaseTableCreate.max_length'),
    key: 'max_length',
    dataIndex: 'max_length',
    width: '100px',
  },
]

const tableRecords = reactive({
  columns: [],
  data: [],
  schema: [],
  loading: false,
  current: 1,
  pageSize: 10,
  total: 0,
  pagination: computed(() => ({
    total: tableRecords.total,
    current: tableRecords.current,
    pageSize: tableRecords.pageSize,
  })),
  handleTableChange: (page, filters, sorter) => {
    tableRecords.load({
      page_size: page.pageSize,
      page: page.current,
      sort_field: sorter.field,
      sort_order: sorter.order,
    })
  },
  load: async (params) => {
    tableRecords.loading = true
    const res = await relationalDatabaseTableRecordAPI('list', {
      tid: tableId,
      ...params,
    })
    if (res.status == 200) {
      tableRecords.data = res.data.records
      tableRecords.columns = tableRecords.schema.columns.map((item) => ({
        title: item.name,
        dataIndex: item.name,
        key: item.name,
        sorter: item.type === 'int' || item.type === 'float',
        width: 150,
      }))
    } else if (res.status == 500) {
      message.error(t('workspace.databaseTableRecord.failed_to_load_database'))
    } else {
      message.error(res.msg)
    }
    tableRecords.total = res.data.total
    tableRecords.pageSize = res.data.page_size
    tableRecords.current = res.data.page
    tableRecords.loading = false
    tableLoaded.value = true
  },
  originalData: [],
  editable: false,
  startEdit: () => {
    tableRecords.editable = true
    tableRecords.originalData = JSON.parse(JSON.stringify(tableRecords.data))
  },
  cancelEdit: () => {
    tableRecords.editable = false
    tableRecords.data = tableRecords.originalData
  },
  save: async () => {
    tableRecords.loading = true
    const res = await relationalDatabaseTableRecordAPI('update', {
      tid: tableId,
      records: tableRecords.data,
    })
    if (res.status == 200) {
      message.success(t('common.save_success'))
      tableRecords.editable = false
    } else {
      message.error(res.msg)
    }
    tableRecords.loading = false
  },
  selectedRecords: [],
  rowSelection: computed(() => {
    if (!tableRecords.editable) {
      return null
    } else {
      return {
        preserveSelectedRowKeys: true,
        onChange: (selectedRowKeys, selectedRows) => {
          tableRecords.selectedRecords = selectedRowKeys
        },
      }
    }
  }),
  deleteRecords: async () => {
    tableRecords.loading = true
    const res = await relationalDatabaseTableRecordAPI('delete', {
      tid: tableId,
      records: tableRecords.selectedRecords,
    })
    if (res.status == 200) {
      message.success(t('common.save_success'))
      tableRecords.load()
      table.value.current_rows = res.data.current_rows
    } else {
      message.error(res.msg)
    }
    tableRecords.loading = false
  },
})

const addRecordModal = reactive({
  visible: false,
  loading: false,
  record: {},
  files: [],
  addMethod: 'manual', // 'manual' | 'file'
  open: () => {
    addRecordModal.visible = true
  },
  handleOk: async () => {
    addRecordModal.loading = true
    const res = await relationalDatabaseTableRecordAPI('add', {
      tid: tableId,
      add_method: addRecordModal.addMethod,
      record: addRecordModal.record,
      file: addRecordModal.files[0],
    })
    if (res.status == 200) {
      message.success(t('common.save_success'))
      addRecordModal.visible = false
      tableRecords.load()
      table.value.current_rows = res.data.current_rows
    } else {
      message.error(res.msg)
    }
    addRecordModal.loading = false
  },
  handleCancel: () => {
    addRecordModal.visible = false
  },
})
</script>

<template>
  <div class="loading-container" v-if="loading">
    <a-spin />
  </div>
  <div class="dataspace-container" v-else>
    <a-breadcrumb>
      <a-breadcrumb-item>
        <router-link :to="`/data?tab=relational-database`">
          <FileCabinet />
          {{ t('components.layout.basicHeader.data_space') }}
        </router-link>
      </a-breadcrumb-item>
      <a-breadcrumb-item>
        <router-link :to="`/data/relational-db/${databaseId}`">
          <DatabaseSetting />
          {{ database.name }}
        </router-link>
      </a-breadcrumb-item>
      <a-breadcrumb-item>{{ table.name }}</a-breadcrumb-item>
    </a-breadcrumb>
    <a-card :loading="loading">
      <template #title>
        <DocDetail />
        {{ table.name }}
        <a-tooltip :title="t('workspace.databaseTableRecord.current_rows_max_rows')">
          <a-typography-text type="secondary">
            {{ table.current_rows }}
          </a-typography-text>
        </a-tooltip>
      </template>

      <a-tabs v-model:activeKey="activeKey" tab-position="left">
        <a-tab-pane key="sheet" :tab="t('workspace.databaseTableRecord.sheet')">
          <div>
            <div class="table-mask" v-if="!tableLoaded">
              <a-button type="primary" :loading="tableRecords.loading" @click="tableRecords.load">
                {{ t('workspace.databaseTableRecord.load_data') }}
              </a-button>
            </div>
            <a-table :loading="tableRecords.loading" :columns="tableRecords.columns" :data-source="tableRecords.data"
              :pagination="tableRecords.pagination" :row-selection="tableRecords.rowSelection" rowKey="rowid"
              :scroll="{ x: 970 }" @change="tableRecords.handleTableChange">
              <template #title>
                <a-flex gap="small" justify="space-between">
                  <div v-show="tableRecords.editable">
                    <a-popconfirm :disabled="tableRecords.selectedRecords.length == 0"
                      :title="t('workspace.databaseTableRecord.delete_records_confirm')"
                      @confirm="tableRecords.deleteRecords">
                      <a-button type="text" danger :disabled="tableRecords.selectedRecords.length == 0">
                        <template #icon>
                          <Delete />
                        </template>
                      </a-button>
                    </a-popconfirm>
                    <a-tooltip :title="t('workspace.databaseTableRecord.add_record')">
                      <a-button type="text" @click="addRecordModal.open">
                        <template #icon>
                          <AddItem />
                        </template>
                      </a-button>
                      <a-modal v-model:open="addRecordModal.visible" :confirm-loading="addRecordModal.loading"
                        :title="t('workspace.databaseTableRecord.add_record')" @ok="addRecordModal.handleOk"
                        @cancel="addRecordModal.handleCancel">
                        <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
                          <a-form-item :label="t('workspace.databaseTableCreate.add_method')">
                            <a-radio-group v-model:value="addRecordModal.addMethod">
                              <a-radio-button value="manual">
                                {{ t('workspace.databaseTableCreate.add_method_manual') }}
                              </a-radio-button>
                              <a-radio-button value="file">
                                {{ t('workspace.databaseTableCreate.add_method_table_file') }}
                              </a-radio-button>
                            </a-radio-group>
                          </a-form-item>
                        </a-form>
                        <a-form v-if="addRecordModal.addMethod == 'manual'" :label-col="{ span: 8 }"
                          :wrapper-col="{ span: 16 }">
                          <a-form-item v-for="column in tableRecords.columns" :label="column.title">
                            <a-input v-model:value="addRecordModal.record[column.title]" />
                          </a-form-item>
                        </a-form>
                        <UploaderFieldUse v-else-if="addRecordModal.addMethod == 'file'" v-model="addRecordModal.files"
                          :multiple="false" support-file-types=".xlsx, .xls, .csv" />
                      </a-modal>
                    </a-tooltip>
                  </div>
                  <a-space>
                    <a-tooltip :title="t('common.edit')">
                      <a-button v-show="!tableRecords.editable" type="text" @click="tableRecords.startEdit">
                        <template #icon>
                          <Edit />
                        </template>
                      </a-button>
                    </a-tooltip>
                    <a-tooltip :title="t('common.cancel')">
                      <a-button v-show="tableRecords.editable" type="text" @click="tableRecords.cancelEdit">
                        <template #icon>
                          <Close />
                        </template>
                      </a-button>
                    </a-tooltip>
                    <a-tooltip :title="t('common.save')">
                      <a-button v-show="tableRecords.editable" type="text" @click="tableRecords.save">
                        <template #icon>
                          <Save fill="#28c5e5" />
                        </template>
                      </a-button>
                    </a-tooltip>
                  </a-space>
                </a-flex>
              </template>
              <template #bodyCell="{ column, record }">
                <a-typography-paragraph v-model:content="record[column.key]" :editable="tableRecords.editable" />
              </template>
            </a-table>
          </div>
        </a-tab-pane>

        <a-tab-pane key="schema" :tab="t('workspace.databaseTableCreate.table_schema')">
          <a-table :columns="tableSchemaColumns" :data-source="tableRecords.schema.columns"
            :pagination="{ hideOnSinglePage: true }" style="width: 100%">
          </a-table>
        </a-tab-pane>
      </a-tabs>

    </a-card>
  </div>
</template>

<style scoped>
.dataspace-container {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.dataspace-container .card-title {
  padding: 10px 0;
}

.table-mask {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  z-index: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
  justify-content: center;
  align-items: center;
}
</style>