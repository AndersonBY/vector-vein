<script setup>
import { computed, ref, watch, watchEffect } from 'vue'
import { useVueFlow } from '@vue-flow/core'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import HttpRequestKeyValueEditor from './_HttpRequestKeyValueEditor.vue'
import { createTemplateData } from './HttpRequest'

const props = defineProps({
  id: { type: String, required: true },
  data: { type: Object, required: true },
})
const { t } = useI18n()
const fieldsData = ref(props.data.template)
const initialize = () => Object.entries(createTemplateData().template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) fieldsData.value[key].is_output = true
})
initialize()
watch(() => props.data.template, value => {
  fieldsData.value = value
  initialize()
})
const { edges, nodes } = useVueFlow()
const connected = field => edges.value.some(edge => !edge.ignored && edge.target === props.id && !nodes.value.some(node => node.id === edge.source && node.ignored)
  && [field, fieldsData.value[field].id, fieldsData.value[field].name].filter(Boolean).includes(edge.targetHandle))
const bodyKind = computed(() => connected('body_type') ? 'text' : fieldsData.value.body_type.value)
watchEffect(() => {
  fieldsData.value.body_type.options = ['none', 'json', 'text', 'form'].map(value => ({
    value, label: t(`components.nodes.tools.HttpRequest.body_type_${value}`),
  }))
})
</script>

<template>
  <BaseNode :nodeId="id" :fieldsData="fieldsData" :data="props.data" :debug="props.data.debug"
    translatePrefix="components.nodes.tools.HttpRequest" documentPath="/help/docs/tools#node-HttpRequest">
    <template v-for="field in ['headers', 'query_params', 'body']" :key="field" #[`field-${field}`]>
      <BaseField :name="t(`components.nodes.tools.HttpRequest.${field}`)" type="target" v-model:data="fieldsData[field]">
        <HttpRequestKeyValueEditor v-if="field !== 'body' || ['json', 'text', 'form'].includes(bodyKind)"
          v-model="fieldsData[field].value" :kind="field === 'headers' ? 'headers' : field === 'query_params' ? 'query' : bodyKind"
          :disabled="connected(field)" />
        <a-typography-text v-else type="secondary">{{ t('components.nodes.tools.HttpRequest.body_unused') }}</a-typography-text>
      </BaseField>
    </template>
  </BaseNode>
</template>
