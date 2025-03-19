<script setup>
import { watch, ref, computed } from 'vue'
import { Download } from '@icon-park/vue-next'
import xlsx from "json-as-xlsx"

const props = defineProps({
  data: {
    type: String,
    required: true,
    default: '',
  },
  bordered: {
    type: Boolean,
    default: false,
  },
})

const columns = computed(() => {
  if (parsedData.value.length === 0) {
    return []
  } else {
    return Object.keys(parsedData.value[0]).map((key) => ({
      title: key,
      dataIndex: key,
      key,
    }))
  }
})
const parseData = (data) => {
  let parsedData = data
  if (typeof data === 'string') {
    try {
      parsedData = JSON.parse(data)
    } catch (e) {
      console.error(e)
      parsedData = []
    }
  } else if (typeof data === 'object' && data !== null) {
    parsedData = data
  } else {
    parsedData = []
  }
  return parsedData
}
const parsedData = ref(parseData(props.data))

watch(() => props.data, () => {
  parsedData.value = parseData(props.data)
})

const exportTable = () => {
  const xlsxData = [
    {
      sheet: 'data',
      columns: columns.value.map((column) => ({ label: column.key, value: column.key })),
      content: parsedData.value,
    }
  ]
  const settings = {
    fileName: 'data',
    extraLength: 3,
    writeOptions: {},
  }
  xlsx(xlsxData, settings)
}
</script>

<template>
  <a-flex vertical gap="small">
    <div class="table-container custom-scrollbar">
      <a-table :dataSource="parsedData" :columns="columns" :bordered="bordered" />
    </div>
    <a-button type="text" @click="exportTable">
      <template #icon>
        <Download />
      </template>
    </a-button>
  </a-flex>
</template>

<style scoped>
.table-container {
  width: 100%;
  height: 100%;
  overflow: auto;
}
</style>