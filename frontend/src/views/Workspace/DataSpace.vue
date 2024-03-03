<script setup>
import { LoadingFour, Delete } from '@icon-park/vue-next'
import { ref, reactive, onBeforeMount } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from "vue-router"
import { useUserDatabasesStore } from "@/stores/userDatabase"
import { message } from 'ant-design-vue'
import { statusColorMap } from '@/utils/common'
import { databaseAPI } from '@/api/database'

const { t } = useI18n()
const loading = ref(true)
const router = useRouter()

const userDatabasesStore = useUserDatabasesStore()

const databases = reactive({
  columns: [{
    name: t('workspace.dataSpace.database_name'),
    dataIndex: 'name',
    key: 'name',
  }, {
    title: t('common.status'),
    dataIndex: 'status',
    key: 'status',
    width: '200px',
  }, {
    title: t('common.tags'),
    key: 'tags',
    dataIndex: 'tags',
    width: '200px',
  }, {
    title: t('common.action'),
    key: 'action',
    width: '80px',
  }],
  data: [],
  hoverRowVid: null,
  customRow: (record) => {
    return {
      style: { cursor: 'pointer' },
      onClick: async (event) => {
        if (event.target.classList.contains('ant-table-cell') || event.target.classList.contains('database-title')) {
          await router.push(`/data/${record.vid}`)
        }
      },
      onMouseenter: (event) => { databases.hoverRowVid = record.vid },
      onMouseleave: (event) => { databases.hoverRowVid = null }
    };
  },
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

<template>
  <div class="dataspace-container">
    <a-row align="center" :gutter="[16, 16]">
      <a-col :xl="16" :lg="18" :md="20" :sm="22" :xs="24">
        <a-card :loading="loading">
          <template #extra>
            <a-button type="primary" @click="createNewDatabaseModal.open = true">
              {{ t('workspace.dataSpace.create') }}
            </a-button>
            <a-modal v-model:open="createNewDatabaseModal.open" :title="t('workspace.dataSpace.create')"
              @ok="createNewDatabaseModal.create" :confirmLoading="createNewDatabaseModal.creating">
              <a-form-item :label="t('workspace.dataSpace.database_name')">
                <a-input v-model:value="createNewDatabaseModal.databaseName" />
              </a-form-item>
            </a-modal>
          </template>
          <a-table :columns="databases.columns" :customRow="databases.customRow" :data-source="databases.data">

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
                  <a-tag :color="record.color">
                    <LoadingFour v-if="record.status === 'CREATING'" />
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
                    <a-button danger type="text">
                      <template #icon>
                        <Delete />
                      </template>
                    </a-button>
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