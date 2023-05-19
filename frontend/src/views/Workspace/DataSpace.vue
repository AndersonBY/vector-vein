<template>
  <div class="dataspace-container">
    <a-row :gutter="[16, 16]">
      <a-col :span="24">
        <a-card :loading="loading">
          <template #extra>
            <a-button type="primary" @click="createNewDatabaseModal.open = true">
              {{ t('workspace.dataSpace.create') }}
            </a-button>
            <a-modal v-model:open="createNewDatabaseModal.open" :title="t('workspace.dataSpace.create')"
              @ok="createNewDatabaseModal.create" :confirmLoading="createNewDatabaseModal.creating">
              <a-form-item :label="t('workspace.dataSpace.databaseName')">
                <a-input v-model:value="createNewDatabaseModal.databaseName" />
              </a-form-item>
            </a-modal>
          </template>
          <a-table :columns="databases.columns" :data-source="databases.data">
            <template #headerCell="{ column }">
              <template v-if="column.key === 'name'">
                {{ t('workspace.dataSpace.databaseName') }}
              </template>
            </template>

            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'name'">
                <RouterLink :to="`/data/${record.vid}`">
                  {{ record.name }}
                </RouterLink>
              </template>
              <template v-else-if="column.key === 'status'">
                <span>
                  <a-tag :color="record.color">
                    <LoadingOutlined v-if="record.status === 'CREATING'" />
                    {{ t(`workspace.dataSpace.status_${record.status.toLowerCase()}`) }}
                  </a-tag>
                </span>
              </template>
              <template v-else-if="column.key === 'tags'">
                <span>
                  <a-tag v-for="tag in record.tags" :key="tag">
                    {{ tag.toUpperCase() }}
                  </a-tag>
                </span>
              </template>
              <template v-else-if="column.key === 'action'">
                <span>
                  <a-popconfirm :title="t('workspace.dataSpace.delete_confirm')" @confirm="deleteDatabase(record.vid)">
                    <a-typography-link type="danger">
                      {{ t('workspace.databaseDetail.delete') }}
                    </a-typography-link>
                  </a-popconfirm>
                </span>
              </template>
            </template>
          </a-table>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup>
import { LoadingOutlined } from '@ant-design/icons-vue'
import { ref, reactive, defineComponent, onBeforeMount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useUserDatabasesStore } from "@/stores/userDatabase"
import { message } from 'ant-design-vue'
import { statusColorMap } from '@/utils/common'
import { databaseAPI } from '@/api/database'

defineComponent({
  name: 'DataSpace',
})

const { t } = useI18n()
const loading = ref(true)

const userDatabasesStore = useUserDatabasesStore()

const databases = reactive({
  columns: [{
    name: t('workspace.dataSpace.databaseName'),
    dataIndex: 'name',
    key: 'name',
  }, {
    title: t('common.status'),
    dataIndex: 'status',
    key: 'status',
  }, {
    title: t('common.tags'),
    key: 'tags',
    dataIndex: 'tags',
  }, {
    title: t('common.action'),
    key: 'action',
  }],
  data: []
})
const getDatabases = async () => {
  const response = await databaseAPI('list', {})
  if (response.status == 200) {
    userDatabasesStore.setUserDatabases(response.data)
    databases.data = response.data.map(database => {
      return {
        ...database,
        color: statusColorMap[database.status],
        tags: [],
      }
    })
    loading.value = false
  } else {
    message.error(response.msg)
  }
}

onBeforeMount(async () => {
  await getDatabases()
})

const createNewDatabaseModal = reactive({
  open: ref(false),
  creating: ref(false),
  create: async () => {
    createNewDatabaseModal.creating = true
    const response = await databaseAPI('create', {
      name: createNewDatabaseModal.databaseName
    })
    if (response.status === 200) {
      message.success(t('workspace.dataSpace.create_success'))
    } else {
      message.error(t('workspace.dataSpace.create_failed'))
    }
    await getDatabases()
    createNewDatabaseModal.creating = false
    createNewDatabaseModal.open = false
  },
})

const deleteDatabase = async (vid) => {
  const response = await databaseAPI('delete', { vid: vid })
  if (response.status === 200) {
    message.success(t('workspace.dataSpace.delete_success'))
  } else {
    message.error(t('workspace.dataSpace.delete_failed'))
  }
  await getDatabases()
}
</script>

<style>
.dataspace-container {
  padding: 16px;
}

.database-card {
  cursor: pointer;
  height: 256px;
}

.database-card-cover {
  height: 180px;
  object-fit: cover;
}

.empty-database {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 180px;
}
</style>