<script setup>
import { ref, reactive, onBeforeMount, computed, watchEffect } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import { DocDetail, DatabaseSetting, FileCabinet, TableFile, Plus, Delete } from '@icon-park/vue-next'
import UploaderFieldUse from '@/components/workspace/UploaderFieldUse.vue'
import { databaseColumnTypes } from '@/utils/common'
import { relationalDatabaseAPI, relationalDatabaseTableAPI } from '@/api/database'

const { t } = useI18n()
const loading = ref(true)
const route = useRoute()
const router = useRouter()
const databaseId = route.params.databaseId

const database = ref({})
const tableInfo = reactive({
  add_method: 'table_file',
  files: [],
  sql_statement: '',
})

const currentStep = ref(0)
const steps = ref([
  {
    title: t('workspace.databaseTableCreate.add_table'),
  },
  {
    title: t('workspace.databaseTableCreate.table_schema'),
  },
  {
    title: t('common.finish'),
  },
])

const nextStepDisabled = computed(() => {
  if (currentStep.value == 0) {
    if (tableInfo.add_method == 'table_file') {
      return tableInfo.files.length == 0
    } else if (tableInfo.add_method == 'sql') {
      return tableInfo.sql_statement == ''
    }
  } else if (currentStep.value == 1) {
    if (tableInfo.add_method == 'table_file') {
      return Object.keys(tableSchema.value).length == 0
    }
  }
})

const getDatabase = async () => {
  const getDatabaseResponse = await relationalDatabaseAPI('get', { rid: databaseId })
  if (getDatabaseResponse.status == 200) {
    database.value = getDatabaseResponse.data

  } else {
    message.error(getDatabaseResponse.msg)
  }
}

onBeforeMount(async () => {
  loading.value = true
  await getDatabase()
  loading.value = false
})

const creating = ref(false)
const create = async () => {
  if (tableInfo.add_method == 'sql') {
    if (tableInfo.sql_statement.length == 0) {
      message.error(t('workspace.databaseTableCreate.sql_statement_empty'))
      return
    }
  } else if (tableSchema.value.length == 0) {
    message.error(t('workspace.databaseTableCreate.table_schema_empty'))
    return
  }
  creating.value = true
  const response = await relationalDatabaseTableAPI('create', {
    rid: databaseId,
    ...tableInfo,
    table_schema: tableSchema.value,
  })
  if (response.status === 200) {
    await router.push(`/data/relational-db/${databaseId}`)
  } else if (response.status === 400) {
    message.error(t('workspace.databaseTableCreate.table_name_already_exists'))
  } else if (response.status === 402) {
    message.error(t('workspace.databaseTableCreate.not_enough_quota'))
  } else {
    message.error(response.msg)
  }
  creating.value = false
}

const tableSchema = ref([])
const checkingTableSchema = ref(false)
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
const manualTableSchemaColumns = [
  ...tableSchemaColumns,
  {
    title: t('common.action'),
    key: 'action',
    dataIndex: 'action',
    width: '80px',
  },
]
const columnTypes = databaseColumnTypes.map(item => {
  return {
    label: t(`workspace.databaseTableCreate.type_${item}`) + `(${item})`,
    value: item,
  }
})
const getTableSchema = async () => {
  checkingTableSchema.value = true
  try {
    const response = await relationalDatabaseTableAPI('get_table_schema', {
      rid: databaseId,
      ...tableInfo
    })
    if (response.status == 200) {
      message.success(t('common.success'))
      tableSchema.value = response.data
    } else {
      message.error(response.msg)
    }
  } catch (error) {
    console.error(error)
  }
  checkingTableSchema.value = false
}
const manualTableName = ref('MyTable')
const addColumn = () => {
  if (tableSchema.value.length == 0) {
    tableSchema.value.push({
      table_name: manualTableName.value,
      columns: [],
    })
  }
  const maxIndex = tableSchema.value[0].columns.map(item => item.index).reduce((a, b) => Math.max(a, b), 0)
  tableSchema.value[0].columns.push({
    index: maxIndex + 1,
    name: `column_${maxIndex + 1}`,
    type: 'VARCHAR',
    max_length: 255,
  })
}
watchEffect(() => {
  if (tableInfo.add_method === 'manual' && tableSchema.value.length > 0) {
    tableSchema.value[0].table_name = manualTableName.value;
  }
})
const removeColumn = (index) => {
  tableSchema.value[0].columns.splice(index, 1)
}
</script>

<template>
  <div class="loading-container" v-if="loading">
    <a-spin />
  </div>
  <div class=" dataspace-container" v-else>
    <a-row justify="center" :gutter="[16, 16]">
      <a-col :xl="16" :lg="18" :md="20" :sm="22" :xs="24">
        <a-breadcrumb>
          <a-breadcrumb-item>
            <router-link :to="`/data?tab=relational-database`">
              <FileCabinet />
              {{ t('components.layout.basicHeader.data_space') }}
            </router-link>
          </a-breadcrumb-item>
          <a-breadcrumb-item>
            <router-link :to="`/data/relational-db/${database.rid}`">
              <DatabaseSetting />
              {{ database.name }}
            </router-link>
          </a-breadcrumb-item>
          <a-breadcrumb-item>
            {{ t('workspace.databaseTableCreate.add_table') }}
          </a-breadcrumb-item>
        </a-breadcrumb>
      </a-col>
      <a-col :xl="16" :lg="18" :md="20" :sm="22" :xs="24">
        <a-card :loading="loading">
          <template #title>
            <DocDetail />
            {{ t('workspace.databaseTableCreate.add_table') }}
          </template>

          <a-steps :current="currentStep" :items="steps" style="margin-bottom: 30px;"></a-steps>

          <a-form v-if="currentStep == 0" :label-col="{ span: 6 }">
            <a-form-item :label="t('workspace.databaseTableCreate.add_method')">
              <a-radio-group v-model:value="tableInfo.add_method">
                <a-radio-button value="table_file">
                  {{ t('workspace.databaseTableCreate.add_method_table_file') }}
                </a-radio-button>
                <a-radio-button value="manual">
                  {{ t('workspace.databaseTableCreate.add_method_manual') }}
                </a-radio-button>
                <a-radio-button value="sql">
                  {{ t('workspace.databaseTableCreate.add_method_sql') }}
                </a-radio-button>
              </a-radio-group>
            </a-form-item>

            <template v-if="tableInfo.add_method == 'table_file'">
              <a-flex vertical gap="middle" style="margin-bottom: 30px;">
                <a-alert :message="t('workspace.databaseTableCreate.upload_file_alert_title')"
                  :description="t('workspace.databaseTableCreate.upload_file_alert_description')" type="info"
                  show-icon />
                <UploaderFieldUse v-model="tableInfo.files" :multiple="true"
                  support-file-types=".xlsx, .xls, .csv, .txt, .sql" />
              </a-flex vertical>
            </template>
            <template v-else-if="tableInfo.add_method == 'sql'">
              <a-form-item :label="t('workspace.databaseTableCreate.sql_statement')">
                <a-textarea v-model:value="tableInfo.sql_statement"
                  :status="tableInfo.sql_statement.length > 10000 ? 'error' : ''"
                  :auto-size="{ minRows: 2, maxRows: 30 }" :show-count="true" />
                <a-typography-text v-if="tableInfo.sql_statement.length > 10000" type="danger">
                  {{ t('workspace.databaseTableCreate.sql_statement_too_long') }}
                </a-typography-text>
              </a-form-item>
            </template>
          </a-form>

          <a-flex v-if="currentStep == 1" gap="middle" vertical>
            <template v-if="tableInfo.add_method != 'manual'">
              <a-card v-if="tableInfo.add_method == 'table_file'"
                :title="t('workspace.databaseTableCreate.uploaded_files')">
                <template #extra>
                  <a-button type="primary" @click="getTableSchema" :loading="checkingTableSchema">
                    {{ t('workspace.databaseTableCreate.get_table_schema') }}
                  </a-button>
                </template>
                <a-list size="small" :data-source="tableInfo.files">
                  <template #renderItem="{ item }">
                    <a-list-item>
                      <TableFile />
                      {{ item }}
                    </a-list-item>
                  </template>
                </a-list>
              </a-card>
              <a-button v-else-if="tableInfo.add_method == 'sql'" type="primary" @click="getTableSchema"
                :loading="checkingTableSchema">
                {{ t('workspace.databaseTableCreate.get_table_schema') }}
              </a-button>
              <a-table v-for="table in tableSchema" :columns="tableSchemaColumns" :data-source="table.columns"
                :pagination="{ hideOnSinglePage: true }" style="width: 100%">
                <template #title>
                  <a-flex gap="small" align="center">
                    <a-typography-text strong style="flex-shrink: 0;">
                      {{ t('workspace.databaseTableCreate.table_name') }}
                    </a-typography-text>
                    <a-input v-model:value="table.table_name" />
                  </a-flex>
                </template>
                <template #bodyCell="{ column, record }">
                  <template v-if="column.dataIndex == 'type'">
                    <a-select v-model:value="record.type" :options="columnTypes"></a-select>
                  </template>
                  <template v-else-if="column.dataIndex == 'max_length' && record.type == 'VARCHAR'">
                    <a-input-number v-model:value="record.max_length" :min="1" />
                  </template>
                </template>
              </a-table>
            </template>
            <template v-else-if="tableInfo.add_method == 'manual'">
              <a-table v-if="tableSchema.length > 0" :disabled="Object.keys(tableSchema).length == 0"
                :columns="manualTableSchemaColumns" :data-source="tableSchema[0].columns"
                :pagination="{ hideOnSinglePage: true }">
                <template #title>
                  <a-flex gap="small" align="center">
                    <a-typography-text strong style="flex-shrink: 0;">
                      {{ t('workspace.databaseTableCreate.table_name') }}
                    </a-typography-text>
                    <a-input v-model:value="manualTableName" />
                  </a-flex>
                </template>
                <template #bodyCell="{ column, index, record }">
                  <template v-if="column.dataIndex == 'name'">
                    <a-input v-model:value="record.name"></a-input>
                    <a-typography-text v-if="record.name.includes(' ')" type="danger">
                      {{ t('workspace.databaseTableCreate.no_space_in_column_name') }}
                    </a-typography-text>
                  </template>
                  <template v-else-if="column.dataIndex == 'type'">
                    <a-select v-model:value="record.type" :options="columnTypes" style="width: 100%;"></a-select>
                  </template>
                  <template v-else-if="column.dataIndex == 'max_length' && record.type == 'VARCHAR'">
                    <a-input-number v-model:value="record.max_length" :min="1" />
                  </template>
                  <template v-else-if="column.dataIndex == 'action'">
                    <a-button type="text" @click="removeColumn(index)">
                      <template #icon>
                        <Delete />
                      </template>
                    </a-button>
                  </template>
                </template>
              </a-table>
              <a-button @click="addColumn">
                <template #icon>
                  <Plus />
                </template>
                {{ t('workspace.databaseTableCreate.add_column') }}
              </a-button>
            </template>
            <a-flex vertical gap="middle" v-else-if="tableInfo.add_method == 'sql'">
              <a-button type="primary" @click="getTableSchema" :loading="checkingTableSchema">
                {{ t('workspace.databaseTableCreate.get_table_schema') }}
              </a-button>
              <a-table v-for="table in tableSchema" :columns="tableSchemaColumns" :data-source="table.columns"
                :pagination="{ hideOnSinglePage: true }" style="width: 100%">
                <template #title>
                  <a-flex gap="small" align="center">
                    <a-typography-text strong>
                      {{ table.table_name }}
                    </a-typography-text>
                  </a-flex>
                </template>
              </a-table>
            </a-flex>
          </a-flex>

          <a-flex v-if="currentStep == 2">
            <a-flex vertical gap="middle" style="width: 100%">
              <a-table v-for="table in tableSchema" :columns="tableSchemaColumns" :data-source="table.columns"
                :pagination="{ hideOnSinglePage: true }" style="width: 100%">
                <template #title>
                  <a-flex gap="small" align="center">
                    <a-typography-text strong>
                      {{ table.table_name }}
                    </a-typography-text>
                  </a-flex>
                </template>
              </a-table>
            </a-flex>
          </a-flex>

          <a-flex justify="flex-end" gap="small" style="margin-top: 16px;">
            <a-button :disabled="currentStep == 0" @click="currentStep -= 1">
              {{ t('common.previous_step') }}
            </a-button>
            <a-button v-if="currentStep < 2" type="primary" :disabled="nextStepDisabled" @click="currentStep += 1">
              {{ t('common.next_step') }}
            </a-button>
            <a-button v-else-if="currentStep == 2" type="primary" :loading="creating" @click="create">
              {{ t('common.finish') }}
            </a-button>
          </a-flex>

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