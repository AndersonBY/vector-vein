<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import VectorDatabaseTable from "@/components/workspace/database/VectorDatabaseTable.vue"
import RelationalDatabaseTable from '@/components/workspace/database/RelationalDatabaseTable.vue'
import { getFullUrl } from "@/utils/util"

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const activeKey = ref(route.query.tab ? route.query.tab : 'vector-database')

const tabChange = async (key) => {
  await router.push(getFullUrl(route.path, { tab: key }))
}
</script>

<template>
  <div class="dataspace-container">
    <a-row align="center" :gutter="[16, 16]">
      <a-col :xl="16" :lg="18" :md="20" :sm="22" :xs="24">
        <a-tabs v-model:activeKey="activeKey" centered @change="tabChange">
          <a-tab-pane key="vector-database" :tab="t('workspace.dataSpace.vector_database')">
            <a-card>
              <VectorDatabaseTable />
            </a-card>
          </a-tab-pane>
          <a-tab-pane key="relational-database" :tab="t('workspace.dataSpace.relational_database')">
            <a-card>
              <RelationalDatabaseTable />
            </a-card>
          </a-tab-pane>
        </a-tabs>
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