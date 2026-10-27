<script setup>
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { AddOne, ReduceOne } from '@/icons'
import { httpValueRows, parseHttpValue, serializeHttpRows } from './_httpRequestShared.js'

const props = defineProps({
  modelValue: { type: [String, Object, Array, Number, Boolean], default: '' },
  kind: { type: String, required: true },
  disabled: { type: Boolean, default: false },
})
const emit = defineEmits(['update:modelValue'])
const { t } = useI18n()
const prefix = 'components.nodes.tools.HttpRequest'
const mode = ref('rows')
const rows = ref([])
const source = ref('')
let lastEmitted
const sync = value => {
  source.value = typeof value === 'string' ? value : JSON.stringify(value)
  if (['json', 'text'].includes(props.kind)) {
    mode.value = 'json'
    return
  }
  const parsed = httpValueRows(value, props.kind)
  if (!parsed.error) rows.value = parsed.rows
  else mode.value = 'json'
}
sync(props.modelValue)
watch(() => props.modelValue, value => {
  if (value === lastEmitted && value === source.value) return
  lastEmitted = undefined
  sync(value)
}, { deep: true })
watch(() => props.kind, () => sync(props.modelValue))
const error = computed(() => props.disabled || props.kind === 'text' ? '' : parseHttpValue(source.value, props.kind).error)
const publish = value => {
  source.value = value
  lastEmitted = value
  emit('update:modelValue', value)
}
const updateRows = () => publish(serializeHttpRows(rows.value))
const addRow = () => {
  rows.value.push({ key: '', value: '', type: 'text' })
  updateRows()
}
const removeRow = index => {
  rows.value.splice(index, 1)
  updateRows()
}
const switchMode = value => {
  if (value === 'rows') {
    const parsed = httpValueRows(source.value, props.kind)
    if (parsed.error) return
    rows.value = parsed.rows
  }
  mode.value = value
}
</script>

<template>
  <div class="http-kv-editor nodrag nowheel">
    <a-typography-text v-if="disabled" type="secondary">{{ t(`${prefix}.connected_value`) }}</a-typography-text>
    <template v-else>
      <a-radio-group v-if="!['json', 'text'].includes(kind)" :value="mode" size="small" option-type="button"
        :options="[{ value: 'rows', label: t(`${prefix}.rows_mode`), disabled: Boolean(error) && mode !== 'rows' }, { value: 'json', label: 'JSON' }]"
        @update:value="switchMode" />
      <template v-if="mode === 'rows' && !['json', 'text'].includes(kind)">
        <div v-for="(row, index) in rows" :key="index" class="http-kv-row">
          <a-input v-model:value="row.key" :aria-label="t(`${prefix}.key_column`)" :placeholder="t(`${prefix}.key_column`)"
            @update:value="updateRows" />
          <a-input v-model:value="row.value" :aria-label="t(`${prefix}.value_column`)" :placeholder="t(`${prefix}.value_column`)"
            @update:value="updateRows" />
          <a-select v-if="kind !== 'headers'" v-model:value="row.type" :aria-label="t(`${prefix}.value_type`)"
            :options="[{ value: 'text', label: t(`${prefix}.text_value`) }, { value: 'json', label: 'JSON' }]"
            @update:value="updateRows" />
          <a-button type="text" :aria-label="t(`${prefix}.remove_pair`)" :title="t(`${prefix}.remove_pair`)" @click="removeRow(index)">
            <template #icon><ReduceOne /></template>
          </a-button>
        </div>
        <a-button type="dashed" block @click="addRow">
          <template #icon><AddOne /></template>{{ t(`${prefix}.add_pair`) }}
        </a-button>
        <a-typography-text v-if="kind !== 'headers'" type="secondary" class="http-kv-hint">{{ t(`${prefix}.typed_value_tip`) }}</a-typography-text>
      </template>
      <a-textarea v-else :value="source" :aria-label="kind === 'text' ? t(`${prefix}.body`) : 'JSON'"
        :auto-size="{ minRows: 2, maxRows: 12 }" @update:value="publish" />
      <a-typography-text v-if="error" type="danger" role="alert">{{ t(`${prefix}.${error}`) }}</a-typography-text>
    </template>
  </div>
</template>

<style scoped>
.http-kv-editor { display: flex; flex-direction: column; gap: 8px; }
.http-kv-row { display: flex; gap: 4px; align-items: center; }
.http-kv-row .ant-input { min-width: 0; flex: 1; }
.http-kv-row .ant-select { width: 76px; flex-shrink: 0; }
.http-kv-hint { font-size: 12px; }
</style>
