<script setup>
import { ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import TextOutput from "@/components/TextOutput.vue"
import { officialSiteAPI } from '@/api/remote'

const props = defineProps({
  slug: {
    type: String,
    required: true
  },
  nodeType: {
    type: String,
    required: true
  },
  title: {
    type: String,
    default: ''
  },
})

const open = defineModel('open', { default: false })

const { t, locale } = useI18n()
const loading = ref(false)
const error = ref(null)
const documentData = ref({})

const loadDocumentData = async () => {
  loading.value = true
  error.value = null
  try {
    const response = await officialSiteAPI('get_document', {
      slug: props.slug,
      node_type: props.nodeType
    })
    if (response.data.status === 200) {
      documentData.value = response.data.data
    } else {
      throw new Error('获取文档数据失败')
    }
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

watch(() => open.value, (newValue) => {
  if (newValue && !documentData.value[locale.value]) {
    loadDocumentData()
  }
})
</script>

<template>
  <a-modal v-model:open="open" :title="title" :footer="null" width="70%">
    <a-skeleton v-if="loading" active />
    <div v-else-if="error">{{ t('components.help.documentModal.load_error') }}</div>
    <div v-else class="document-modal-content custom-scrollbar">
      <TextOutput :text="documentData[locale]" />
    </div>
  </a-modal>
</template>

<style scoped>
.document-modal-content {
  max-height: 70vh;
  overflow-y: auto;
}
</style>
