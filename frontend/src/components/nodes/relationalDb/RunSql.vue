<script setup>
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useUserRelationalDatabasesStore } from "@/stores/userRelationalDatabase"
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './RunSql'

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
</script>

<template>
  <BaseNode :nodeId="id" :fieldsData="fieldsData" translatePrefix="components.nodes.relationalDb.RunSql"
    :debug="props.data.debug" documentLink="https://vectorvein.com/help/docs/relational-db#h2-8" />
</template>