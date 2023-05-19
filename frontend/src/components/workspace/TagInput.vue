<script setup>
import { ref, defineComponent, onBeforeMount } from 'vue'
import { useI18n } from 'vue-i18n'
import { workflowTagAPI } from '@/api/workflow'

const { t } = useI18n()

defineComponent({
  name: 'TagInput',
})

const tags = defineModel()
const tagsOptions = ref([])

onBeforeMount(async () => {
  const { data } = await workflowTagAPI('list', {})
  tagsOptions.value = data.map(tag => {
    return {
      label: tag.title,
      value: tag.tid,
    }
  })
})
</script>

<template>
  <a-select v-model:value="tags" mode="tags" :placeholder="t('components.workspace.tagInput.select_tags')"
    style="min-width: 150px; width: 100%" :options="tagsOptions">
  </a-select>
</template>