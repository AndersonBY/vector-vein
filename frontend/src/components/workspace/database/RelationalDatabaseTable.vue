<script setup>
import { ref, reactive, onBeforeMount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import { LoadingFour, Delete, Add } from '@icon-park/vue-next'
import { storeToRefs } from 'pinia'
import { useUserRelationalDatabasesStore } from "@/stores/userRelationalDatabase"
import { statusColorMap } from '@/utils/common'
import { relationalDatabaseAPI } from '@/api/database'

const { t } = useI18n()
const loading = ref(true)
const router = useRouter()

const userDatabasesStore = useUserRelationalDatabasesStore()
const { userRelationalDatabases } = storeToRefs(userDatabasesStore)

const databases = reactive({
  columns: [
    {
      name: t('workspace.dataSpace.database_name'),
      dataIndex: 'name',
      key: 'name',
    },
    {
      title: t('common.status'),
      dataIndex: 'status',
      key: 'status',
      width: '100px',
    },
    {
      title: t('common.action'),
      key: 'action',
      width: '80px',
    }
  ],
  data: [],
  hoverRowRid: null,
  customRow: (record) => {
    return {
      style: { cursor: record.status == 'VALID' ? 'pointer' : 'not-allowed' },
      onClick: async (event) => {
        if (record.status != 'VALID') return
        if (event.target.classList.contains('ant-table-cell') || event.target.classList.contains('database-title')) {
          await router.push(`/data/relational-db/${record.rid}`)
        }
      },
      onMouseenter: (event) => { databases.hoverRowRid = record.rid },
      onMouseleave: (event) => { databases.hoverRowRid = null }
    };
  },
})
const getDatabases = async () => {
  const response = await relationalDatabaseAPI('list')
  if (response.status == 200) {
    userDatabasesStore.setUserRelationalDatabases(response.data)
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
  open: false,
  creating: false,
  databaseName: '',
  create: async () => {
    createNewDatabaseModal.creating = true
    const response = await relationalDatabaseAPI('create', {
      name: createNewDatabaseModal.databaseName,
    })
    if (response.status === 200) {
      message.success(t('workspace.dataSpace.create_success'))
      let timer = setInterval(async () => {
        await getDatabases();
        const database = databases.data.find(db => db.rid === response.data.rid);
        if (database && database.status === 'VALID') {
          clearInterval(timer);
        }
      }, 5000);
    } else {
      message.error(t('workspace.dataSpace.create_failed'))
    }
    await getDatabases()
    createNewDatabaseModal.creating = false
    createNewDatabaseModal.open = false
  },
})

const deleteDatabase = async (rid) => {
  const response = await relationalDatabaseAPI('delete', { rid: rid })
  if (response.status === 200) {
    message.success(t('workspace.dataSpace.delete_success'))
  } else {
    message.error(t('workspace.dataSpace.delete_failed'))
  }
  await getDatabases()
}
</script>

<template>
  <a-table :columns="databases.columns" :customRow="databases.customRow" :data-source="databases.data"
    :pagination="{ hideOnSinglePage: true }" :loading="loading">
    <template #title>
      <a-flex justify="space-between">
        <a-space>
          <a-button type="primary" @click="createNewDatabaseModal.open = true">
            <template #icon>
              <Add />
            </template>
            {{ t('workspace.dataSpace.create') }}
          </a-button>
          <a-typography-text type="secondary">
            {{ userRelationalDatabases.length }}
          </a-typography-text>
        </a-space>
        <a-modal v-model:open="createNewDatabaseModal.open" :title="t('workspace.dataSpace.create')"
          @ok="createNewDatabaseModal.create" :confirmLoading="createNewDatabaseModal.creating">
          <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 18 }">
            <a-form-item :label="t('workspace.dataSpace.database_name')">
              <a-input v-model:value="createNewDatabaseModal.databaseName" />
            </a-form-item>
          </a-form>
        </a-modal>
      </a-flex>
    </template>
    <template #headerCell="{ column }">
      <template v-if="column.key === 'name'">
        {{ t('workspace.dataSpace.database_name') }}
      </template>
    </template>

    <template #bodyCell="{ column, record }">
      <template v-if="column.key === 'name'">
        <a-typography-text class="database-title">
          {{ record.name }}
        </a-typography-text>
      </template>
      <template v-else-if="column.key === 'status'">
        <span>
          <a-tag :color="record.color" :bordered="false">
            <LoadingFour :spin="true" v-if="record.status === 'CREATING'" />
            {{ t(`workspace.dataSpace.status_${record.status.toLowerCase()}`) }}
          </a-tag>
        </span>
      </template>
      <template v-else-if="column.key === 'action'">
        <a-popconfirm :title="t('workspace.dataSpace.delete_confirm')" @confirm="deleteDatabase(record.rid)">
          <a-button danger type="text">
            <template #icon>
              <Delete />
            </template>
          </a-button>
        </a-popconfirm>
      </template>
    </template>
  </a-table>
</template>

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