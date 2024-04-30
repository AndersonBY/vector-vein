<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { Codemirror } from 'vue-codemirror'
import { sql } from '@codemirror/lang-sql'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView } from "@codemirror/view"
import { relationalDatabaseAPI } from '@/api/database'

const props = defineProps({
  databaseId: {
    type: String,
    required: true,
  },
})

const { t } = useI18n()
const sqlStatement = ref('')
const runningSQL = ref(false)
const results = ref([])
const resultTabKey = ref(1)
const runSQL = async () => {
  runningSQL.value = true
  const res = await relationalDatabaseAPI('run_sql', { rid: props.databaseId, sql: sqlStatement.value })
  if (res.status == 200) {
    message.success(t('workspace.databaseDetail.sql_success'))
    results.value = res.data
    results.value.forEach((result) => {
      if (result.type == 'SELECT') {
        result.records = result.records ?? []
        result.columns = (result.columns ?? []).map((c) => {
          return {
            title: c,
            key: c,
            dataIndex: c,
          }
        })
      }
    })
  } else {
    message.error(res.msg)
  }
  runningSQL.value = false
}
const FontSizeTheme = EditorView.theme({
  ".cm-content": {
    fontFamily: "Cascadia Code, Consolas, Monaco, Menlo, Ubuntu Mono, Liberation Mono, DejaVu Sans Mono, Courier New, monospace",
    fontSize: '24px',
  },
})
const extensions = [sql(), oneDark, FontSizeTheme]
</script>

<template>
  <a-flex gap="middle" vertical>
    <a-flex gap="middle" justify="flex-end">
      <a-button type="primary" @click="runSQL" :loading="runningSQL" :disabled="sqlStatement.length == 0">
        {{ t('workspace.databaseDetail.run_sql') }}
      </a-button>
    </a-flex>
    <a-spin :spinning="runningSQL">
      <codemirror class="code-editor" v-model="sqlStatement"
        :placeholder="t('workspace.databaseDetail.please_enter_sql')" :style="{ height: '400px' }" :autofocus="true"
        :indent-with-tab="true" :extensions="extensions" />
      <a-typography-text type="secondary">
        {{ t('workspace.databaseDetail.max_show_rows') }}
      </a-typography-text>
    </a-spin>
    <a-tabs v-model:activeKey="resultTabKey" type="card">
      <a-tab-pane v-for="(result, index) in results" :key="index + 1"
        :tab="t('workspace.databaseDetail.result_n', { n: index })">
        <template v-if="result.success">
          <a-table v-if="result.type == 'SELECT'" :columns="result.columns" :data-source="result.records"
            :pagination="{ hideonSinglePage: true }" :scroll="{ x: 970 }">
          </a-table>
          <a-alert v-else :message="t('workspace.databaseDetail.affected_rows', { rows: result.rows })" type="success"
            show-icon />
        </template>
        <template v-else>
          <a-alert :message="result.msg" type="error" show-icon />
        </template>
      </a-tab-pane>
    </a-tabs>
  </a-flex>
</template>

<style>
.code-editor .cm-scroller::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

.code-editor .cm-scroller::-webkit-scrollbar-thumb {
  background: #CCCCCC;
  border-radius: 6px;
}

.code-editor .cm-scroller::-webkit-scrollbar-track {
  background: transparent;
}
</style>