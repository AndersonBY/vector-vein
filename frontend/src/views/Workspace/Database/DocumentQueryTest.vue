<script setup>
import { onBeforeMount, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import { message } from 'ant-design-vue'
import { Left, Search } from '@icon-park/vue-next'
import { databaseAPI } from '@/api/database'

const { t } = useI18n()
const router = useRouter()
const databases = ref([])
const selectedVid = ref(null)
const queryText = ref('')
const resultLimit = ref(10)
const searchResults = ref([])
const loading = ref(false)
const searched = ref(false)

onBeforeMount(async () => {
  const res = await databaseAPI('list', {})
  if (res.status === 200) {
    databases.value = res.data || []
  }
})

const doSearch = async () => {
  if (!selectedVid.value) {
    message.warning(t('workspace.dataSpace.vector_search_select_db'))
    return
  }
  if (!queryText.value.trim()) {
    message.warning(t('workspace.dataSpace.vector_search_enter_query'))
    return
  }
  loading.value = true
  searched.value = true
  const res = await databaseAPI('search', {
    vid: selectedVid.value,
    query: queryText.value,
    limit: resultLimit.value,
  })
  if (res.status === 200) {
    searchResults.value = res.data?.results || []
  } else {
    message.error(res.msg || t('workspace.dataSpace.vector_search_failed'))
  }
  loading.value = false
}

const goBack = () => {
  router.push({ name: 'DataSpaceMain' })
}
</script>

<template>
  <div class="vector-search-container">
    <a-flex align="center" gap="small" style="margin-bottom: 16px;">
      <a-button @click="goBack">
        <Left />
        {{ t('common.back') }}
      </a-button>
      <a-typography-title :level="3" style="margin: 0;">
        {{ t('workspace.dataSpace.vector_search_title') }}
      </a-typography-title>
    </a-flex>

    <a-card>
      <a-form layout="vertical">
        <a-form-item :label="t('workspace.dataSpace.vector_search_select_db')">
          <a-select
            v-model:value="selectedVid"
            :placeholder="t('workspace.dataSpace.vector_search_select_db')"
            style="width: 100%;"
            show-search
            :filter-option="(input, option) => option.label.toLowerCase().includes(input.toLowerCase())"
          >
            <a-select-option v-for="db in databases" :key="db.vid" :value="db.vid" :label="db.name">
              {{ db.name }}
            </a-select-option>
          </a-select>
        </a-form-item>
        <a-form-item :label="t('workspace.dataSpace.vector_search_query')">
          <a-textarea
            v-model:value="queryText"
            :placeholder="t('workspace.dataSpace.vector_search_query_placeholder')"
            :rows="3"
            @pressEnter.ctrl="doSearch"
          />
        </a-form-item>
        <a-flex gap="middle" align="center">
          <a-form-item :label="t('workspace.dataSpace.vector_search_limit')" style="margin-bottom: 0;">
            <a-select v-model:value="resultLimit" style="width: 100px;">
              <a-select-option :value="5">5</a-select-option>
              <a-select-option :value="10">10</a-select-option>
              <a-select-option :value="20">20</a-select-option>
            </a-select>
          </a-form-item>
          <a-button type="primary" :loading="loading" @click="doSearch" style="margin-top: 4px;">
            <Search />
            {{ t('workspace.dataSpace.vector_search_button') }}
          </a-button>
        </a-flex>
      </a-form>
    </a-card>

    <a-card style="margin-top: 16px;" :title="t('workspace.dataSpace.vector_search_results')">
      <a-empty v-if="searchResults.length === 0 && !loading"
        :description="searched ? t('workspace.dataSpace.vector_search_no_results') : t('workspace.dataSpace.vector_search_hint')" />
      <a-list v-else :data-source="searchResults" :loading="loading">
        <template #renderItem="{ item, index }">
          <a-list-item>
            <a-list-item-meta>
              <template #title>
                <a-flex justify="space-between" align="center">
                  <a-typography-text strong>#{{ index + 1 }}</a-typography-text>
                  <a-tag v-if="item.score != null" color="blue">
                    {{ (item.score * 100).toFixed(1) }}%
                  </a-tag>
                </a-flex>
              </template>
              <template #description>
                <a-typography-paragraph
                  :ellipsis="{ rows: 4, expandable: true, symbol: t('common.more_settings') }"
                  :content="item.text || ''"
                  style="margin-bottom: 4px;" />
                <a-typography-text v-if="item.object_id" type="secondary" style="font-size: 12px;">
                  Object: {{ item.object_id }}
                </a-typography-text>
              </template>
            </a-list-item-meta>
          </a-list-item>
        </template>
      </a-list>
    </a-card>
  </div>
</template>

<style scoped>
.vector-search-container {
  padding: 16px 16px 32px;
}
</style>
