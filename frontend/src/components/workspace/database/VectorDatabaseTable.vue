<script setup>
import { computed, ref, reactive, onBeforeMount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import { LoadingFour, Delete, Add } from '@icon-park/vue-next'
import { storeToRefs } from 'pinia'
import { useUserDatabasesStore } from "@/stores/userDatabase"
import { useModelCatalogStore } from '@/stores/modelCatalog'
import QuestionPopover from '@/components/QuestionPopover.vue'
import { statusColorMap } from '@/utils/common'
import { databaseAPI } from '@/api/database'

const { t } = useI18n()
const loading = ref(true)
const router = useRouter()

const userDatabasesStore = useUserDatabasesStore()
const modelCatalogStore = useModelCatalogStore()
const { userDatabases } = storeToRefs(userDatabasesStore)

const fallbackEmbeddingSelection = {
  embedding_provider: 'openai',
  embedding_model: 'text-embedding-3-small',
  embedding_size: 1536,
}

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
  hoverRowVid: null,
  customRow: (record) => {
    return {
      style: { cursor: 'pointer' },
      onClick: async (event) => {
        if (event.target.classList.contains('ant-table-cell') || event.target.classList.contains('database-title')) {
          await router.push({ name: 'VectorDatabaseDetail', params: { databaseId: record.vid } })
        }
      },
      onMouseenter: (event) => { databases.hoverRowVid = record.vid },
      onMouseleave: (event) => { databases.hoverRowVid = null }
    };
  },
})
const getDatabases = async () => {
  const response = await databaseAPI('list')
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
  await Promise.all([getDatabases(), modelCatalogStore.ensureLoaded()])
  syncEmbeddingSelection(true)
})

const createNewDatabaseModal = reactive({
  open: false,
  creating: false,
  form: {
    name: '',
    ...fallbackEmbeddingSelection,
  },
  create: async () => {
    createNewDatabaseModal.creating = true
    const response = await databaseAPI('create', createNewDatabaseModal.form)
    if (response.status === 200) {
      message.success(t('workspace.dataSpace.create_success'))
      let timer = setInterval(async () => {
        await getDatabases();
        const database = databases.data.find(db => db.vid === response.data.vid);
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

const embeddingProviderOptions = computed(() => {
  return modelCatalogStore.embeddingProviders.map((provider) => ({
    label: provider.label,
    value: provider.key,
  }))
})

const embeddingModelOptions = computed(() => {
  const optionGroup = modelCatalogStore.embeddingModelOptions.find(
    (item) => item.value === createNewDatabaseModal.form.embedding_provider
  )
  return optionGroup?.children || []
})

const syncEmbeddingSelection = (resetDimensions = false) => {
  const providerOptions = embeddingProviderOptions.value
  if (providerOptions.length === 0) {
    createNewDatabaseModal.form.embedding_provider = fallbackEmbeddingSelection.embedding_provider
    createNewDatabaseModal.form.embedding_model = fallbackEmbeddingSelection.embedding_model
    if (resetDimensions) {
      createNewDatabaseModal.form.embedding_size = fallbackEmbeddingSelection.embedding_size
    }
    return
  }

  const providerValid = providerOptions.some(
    (item) => item.value === createNewDatabaseModal.form.embedding_provider
  )
  if (!providerValid) {
    createNewDatabaseModal.form.embedding_provider = providerOptions[0].value
  }

  const modelOptions = embeddingModelOptions.value
  if (modelOptions.length === 0) {
    createNewDatabaseModal.form.embedding_model = ''
    if (resetDimensions) {
      createNewDatabaseModal.form.embedding_size = fallbackEmbeddingSelection.embedding_size
    }
    return
  }

  const modelValid = modelOptions.some(
    (item) => item.value === createNewDatabaseModal.form.embedding_model
  )
  if (!modelValid) {
    createNewDatabaseModal.form.embedding_model = modelOptions[0].value
  }

  if (resetDimensions) {
    const selectedModel = modelOptions.find(
      (item) => item.value === createNewDatabaseModal.form.embedding_model
    )
    if (selectedModel?.dimensions) {
      createNewDatabaseModal.form.embedding_size = selectedModel.dimensions
    }
  }
}

watch(embeddingProviderOptions, () => {
  syncEmbeddingSelection(true)
})

watch(
  () => createNewDatabaseModal.form.embedding_provider,
  () => {
    syncEmbeddingSelection(true)
  }
)

watch(
  () => createNewDatabaseModal.form.embedding_model,
  (model) => {
    const selectedModel = embeddingModelOptions.value.find((item) => item.value === model)
    if (selectedModel?.dimensions) {
      createNewDatabaseModal.form.embedding_size = selectedModel.dimensions
    }
  }
)

const deleteDatabase = async (vid) => {
  const response = await databaseAPI('delete', { vid: vid })
  if (response.status === 200) {
    message.success(t('workspace.dataSpace.delete_success'))
  } else {
    message.error(t('workspace.dataSpace.delete_failed'))
  }
  await getDatabases()
}

const embeddingProviderTips = [
  t('workspace.dataSpace.embedding_provider_settings_tip'),
  t('workspace.dataSpace.embedding_provider_custom_tip'),
  {
    type: 'link',
    url: 'https://github.com/huggingface/text-embeddings-inference',
    text: 'https://github.com/huggingface/text-embeddings-inference'
  },
]
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
            {{ userDatabases.length }}
          </a-typography-text>
        </a-space>
        <a-modal v-model:open="createNewDatabaseModal.open" :title="t('workspace.dataSpace.create')"
          @ok="createNewDatabaseModal.create" :confirmLoading="createNewDatabaseModal.creating">
          <a-form :label-col="{ span: 6 }" :wrapper-col="{ span: 18 }">
            <a-form-item :label="t('workspace.dataSpace.database_name')">
              <a-input v-model:value="createNewDatabaseModal.form.name" />
            </a-form-item>
            <a-form-item>
              <template #label>
                <a-flex align="center">
                  {{ t('workspace.dataSpace.embedding_provider') }}
                  <QuestionPopover :contents="embeddingProviderTips" />
                </a-flex>
              </template>
              <a-select v-model:value="createNewDatabaseModal.form.embedding_provider" :options="embeddingProviderOptions" />
            </a-form-item>
            <a-form-item :label="t('workspace.dataSpace.embedding_models')">
              <a-select v-model:value="createNewDatabaseModal.form.embedding_model" :options="embeddingModelOptions"
                :disabled="embeddingModelOptions.length === 0" />
            </a-form-item>
            <a-form-item :label="t('workspace.dataSpace.embedding_size')">
              <a-input-number v-model:value="createNewDatabaseModal.form.embedding_size" />
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
            {{ t(`status.${record.status}`) }}
          </a-tag>
        </span>
      </template>
      <template v-else-if="column.key === 'action'">
        <a-popconfirm :title="t('workspace.dataSpace.delete_confirm')" @confirm="deleteDatabase(record.vid)">
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
