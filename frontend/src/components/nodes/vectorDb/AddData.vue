<script setup>
import { ref } from 'vue'
import { storeToRefs } from 'pinia'
import { useUserDatabasesStore } from "@/stores/userDatabase"
import BaseNode from '@/components/nodes/BaseNode.vue'
import { createTemplateData } from './AddData'

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

const userDatabasesStore = useUserDatabasesStore()
const { userDatabases } = storeToRefs(userDatabasesStore)

const fieldsData = ref(props.data.template)
const templateData = createTemplateData()
Object.entries(templateData.template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) {
    fieldsData.value[key].is_output = true
  }
})
fieldsData.value.database.options = userDatabases.value.filter((database) => {
  return database.status == 'VALID'
}).map((item) => {
  return {
    value: item.vid,
    label: item.name,
  }
})
</script>

<template>
  <BaseNode :nodeId="id" :fieldsData="fieldsData" translatePrefix="components.nodes.vectorDb.AddData"
    :debug="props.data.debug" documentLink="https://vectorvein.com/help/docs/vector-db#h2-0" />
</template>