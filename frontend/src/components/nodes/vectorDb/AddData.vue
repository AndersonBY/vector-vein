<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useUserDatabasesStore } from "@/stores/userDatabase"
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
  templateData: {
    "description": "description",
    "task_name": "vector_db.add_data",
    "has_inputs": true,
    "template": {
      "text": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "text",
        "display_name": "text",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "content_title": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "content_title",
        "display_name": "content_title",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
      "source_url": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "source_url",
        "display_name": "source_url",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
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
      "split_method": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "general",
        "password": false,
        "options": [
          {
            "value": "general",
            "label": "general"
          },
        ],
        "name": "split_method",
        "display_name": "split_method",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "select"
      },
      "chunk_length": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": 500,
        "password": false,
        "name": "chunk_length",
        "display_name": "chunk_length",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "number"
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
      "object_id": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "object_id",
        "display_name": "object_id",
        "type": "list|str",
        "clear_after_run": true,
        "list": false,
        "field_type": ""
      }
    }
  },
})

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
fieldsData.value.split_method.options = fieldsData.value.split_method.options.map(item => {
  item.label = t(`components.nodes.vectorDb.AddData.split_method_${item.value}`)
  return item
})
</script>

<template>
  <BaseNode :nodeId="id" :title="t('components.nodes.vectorDb.AddData.title')" :description="props.data.description"
    documentLink="https://vectorvein.com/help/docs/vector-db#h2-0">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="content_title" :name="t('components.nodes.vectorDb.AddData.content_title')" required
            type="target" v-model:show="fieldsData.content_title.show">
            <a-input class="field-content" v-model:value="fieldsData.content_title.value"
              :placeholder="fieldsData.content_title.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="text" :name="t('components.nodes.vectorDb.AddData.text')" required type="target"
            v-model:show="fieldsData.text.show">
            <a-input class="field-content" v-model:value="fieldsData.text.value"
              :placeholder="fieldsData.text.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="source_url" :name="t('components.nodes.vectorDb.AddData.source_url')" type="target"
            v-model:show="fieldsData.source_url.show">
            <a-input class="field-content" v-model:value="fieldsData.source_url.value"
              :placeholder="fieldsData.source_url.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24" v-if="fieldsData.data_type.value == 'text'">
          <BaseField id="split_method" :name="t('components.nodes.vectorDb.AddData.split_method')" required type="target"
            v-model:show="fieldsData.split_method.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.split_method.value"
              :options="fieldsData.split_method.options" />
          </BaseField>
        </a-col>

        <a-col :span="24" v-if="fieldsData.data_type.value == 'text'">
          <BaseField id="chunk_length" :name="t('components.nodes.vectorDb.AddData.chunk_length')" required type="target"
            v-model:show="fieldsData.chunk_length.show">
            <a-input-number style="width: 100%;" class="field-content" v-model:value="fieldsData.chunk_length.value"
              :placeholder="fieldsData.chunk_length.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="data_type" :name="t('components.nodes.vectorDb.AddData.data_type')" required type="target"
            v-model:show="fieldsData.data_type.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.data_type.value"
              :options="fieldsData.data_type.options" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="database" :name="t('components.nodes.vectorDb.AddData.database')" required type="target"
            v-model:show="fieldsData.database.show">
            <a-select style="width: 100%;" class="field-content" v-model:value="fieldsData.database.value"
              :options="fieldsData.database.options" />
          </BaseField>
        </a-col>
      </a-row>
    </template>

    <template #output>
      <BaseField id="object_id" :name="t('components.nodes.vectorDb.AddData.object_id')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>