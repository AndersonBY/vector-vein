<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { Refresh } from '@icon-park/vue-next'
import { storeToRefs } from 'pinia'
import { useUserRelationalDatabasesStore } from "@/stores/userRelationalDatabase"
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import { relationalDatabaseTableAPI } from '@/api/database'
import { createTemplateData } from './GetTableInfo'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
})

const { t } = useI18n()
const userDatabasesStore = useUserRelationalDatabasesStore()
const { userRelationalDatabases } = storeToRefs(userDatabasesStore)

const fieldsData = ref(props.data.template)
const templateData = createTemplateData()
Object.entries(templateData.template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) {
    fieldsData.value[key].is_output = true
  }
})
fieldsData.value.database.options = userRelationalDatabases.value.filter((database) => {
  return database.status == 'VALID'
}).map((item) => {
  return {
    value: item.rid,
    label: item.name,
  }
})

const databaseChanged = (value) => {
  fieldsData.value.tables.options = []
  fieldsData.value.tables.value = []
  loadTables(value)
}

const loadingTables = ref(false)
const loadTables = async (rid) => {
  if (!rid) {
    message.error(t('components.nodes.relationalDb.GetTableInfo.select_database'))
    return
  }
  loadingTables.value = true
  const response = await relationalDatabaseTableAPI('list', {
    rid: rid,
    status: ['VA'],
    page_size: 100,
  })
  if (response.status != 200) {
    return
  }
  fieldsData.value.tables.options = response.data.tables.map((item) => {
    return {
      value: item.tid,
      label: item.name,
    }
  })
  loadingTables.value = false
}
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :fieldsData="fieldsData"
    translatePrefix="components.nodes.relationalDb.GetTableInfo"
    documentLink="https://vectorvein.com/help/docs/relational-db#h2-4">
    <template #main>
      <a-flex vertical gap="small">
        <BaseField :name="t('components.nodes.relationalDb.GetTableInfo.database')" required type="target"
          v-model:data="fieldsData.database">
          <a-select style="width: 100%;" class="field-content" v-model:value="fieldsData.database.value"
            :options="fieldsData.database.options" @change="databaseChanged" />
        </BaseField>
        <a-tooltip placement="left" :title="t('components.nodes.relationalDb.GetTableInfo.select_all_if_empty')">
          <BaseField :name="t('components.nodes.relationalDb.GetTableInfo.tables')" required type="target"
            v-model:data="fieldsData.tables">
            <a-spin :spinning="loadingTables">
              <a-flex gap="small" align="center">
                <a-select style="width: 100%;" class="field-content" v-model:value="fieldsData.tables.value"
                  :options="fieldsData.tables.options" mode="tags" />
                <a-tooltip :title="t('components.nodes.relationalDb.GetTableInfo.load_tables')">
                  <a-button type="text" @click="loadTables(fieldsData.database.value)">
                    <template #icon>
                      <Refresh />
                    </template>
                  </a-button>
                </a-tooltip>
              </a-flex>
            </a-spin>
          </BaseField>
        </a-tooltip>
      </a-flex>
    </template>
  </BaseNode>
</template>