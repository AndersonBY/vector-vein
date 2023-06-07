<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useUserDatabasesStore } from "@/stores/userDatabase"
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'Search',
})

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
  events: {
    required: false,
  },
  templateData: {
    "description": "description",
    "task_name": "vector_db.search_data",
    "has_inputs": true,
    "template": {
      "search_text": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "search_text",
        "display_name": "search_text",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "data_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "text",
        "password": false,
        "options": [
          {
            "value": "text",
            "label": "Text"
          },
          // {
          //   "value": "image",
          //   "label": "Image"
          // },
        ],
        "name": "data_type",
        "display_name": "data_type",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "select"
      },
      "database": {
        "required": true,
        "placeholder": "",
        "show": true,
        "multiline": false,
        "value": "",
        "password": false,
        "options": [],
        "name": "database",
        "display_name": "database",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "select"
      },
      "count": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": 5,
        "password": false,
        "name": "count",
        "display_name": "count",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "number"
      },
      "output_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "text",
        "password": false,
        "options": [
          {
            "value": "text",
            "label": "Text"
          },
          {
            "value": "list",
            "label": "List"
          },
        ],
        "name": "output_type",
        "display_name": "output_type",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "select"
      },
      "output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": [],
        "password": false,
        "name": "output",
        "display_name": "output",
        "type": "list|str",
        "clear_after_run": true,
        "list": false,
        "field_type": ""
      }
    }
  },
})
const emit = defineEmits(['change', 'delete'])

const { t } = useI18n()
const userDatabasesStore = useUserDatabasesStore()
const { userDatabases } = storeToRefs(userDatabasesStore)

const fieldsData = ref(props.data.template)
fieldsData.value.database.options = userDatabases.value.filter((database) => {
  return database.status == 'VALID'
}).map((item) => {
  return {
    value: item.vid,
    label: item.name,
  }
})
fieldsData.value.output_type.options = fieldsData.value.output_type.options.map(item => {
  item.label = t(`components.nodes.vectorDb.Search.${item.value}`)
  return item
})
fieldsData.value.data_type.options = fieldsData.value.data_type.options.map(item => {
  item.label = t(`components.nodes.vectorDb.Search.${item.value}`)
  return item
})

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}
</script>

<template>
  <BaseNode :title="t('components.nodes.vectorDb.Search.title')" :description="props.data.description"
    documentLink="https://vectorvein.com/help/docs/vector-db#h2-8" @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="search_text" :name="t('components.nodes.vectorDb.Search.search_text')" required type="target"
            v-model:show="fieldsData.search_text.show">
            <a-input class="field-content" v-model:value="fieldsData.search_text.value"
              :placeholder="fieldsData.search_text.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="data_type" :name="t('components.nodes.vectorDb.Search.data_type')" required type="target"
            v-model:show="fieldsData.data_type.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.data_type.value"
              :options="fieldsData.data_type.options" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="database" :name="t('components.nodes.vectorDb.Search.database')" required type="target"
            v-model:show="fieldsData.database.show">
            <a-select style="width: 100%;" class="field-content" v-model:value="fieldsData.database.value"
              :options="fieldsData.database.options" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="count" :name="t('components.nodes.vectorDb.Search.count')" required type="target"
            v-model:show="fieldsData.count.show">
            <a-input-number style="width: 100%;" class="field-content" v-model:value="fieldsData.count.value"
              :placeholder="fieldsData.count.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="output_type" :name="t('components.nodes.vectorDb.Search.output_type')" required type="target"
            v-model:show="fieldsData.output_type.show">
            <a-select style="width: 100%;" class="field-content" v-model:value="fieldsData.output_type.value"
              :options="fieldsData.output_type.options" />
          </BaseField>
        </a-col>
      </a-row>
    </template>

    <template #output>
      <BaseField id="output" :name="t('components.nodes.vectorDb.Search.output')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>