<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useUserDatabasesStore } from "@/stores/userDatabase"
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'DeleteData',
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
    "task_name": "vector_db.delete_data",
    "has_inputs": true,
    "template": {
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
      },
      "database": {
        "required": true,
        "placeholder": "",
        "show": false,
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
      "delete_success": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "delete_success",
        "display_name": "delete_success",
        "type": "list|bool",
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

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}
</script>

<template>
  <BaseNode :title="t('components.nodes.vectorDb.DeleteData.title')" :description="props.data.description"
    @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="object_id" :name="t('components.nodes.vectorDb.DeleteData.object_id')" required type="target"
            v-model:show="fieldsData.object_id.show">
            <a-input class="field-content" v-model:value="fieldsData.object_id.value"
              :placeholder="fieldsData.object_id.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="database" :name="t('components.nodes.vectorDb.DeleteData.database')" required type="target"
            v-model:show="fieldsData.database.show">
            <a-select style="width: 100%;" class="field-content" v-model:value="fieldsData.database.value"
              :options="fieldsData.database.options" />
          </BaseField>
        </a-col>
      </a-row>
    </template>

    <template #output>
      <BaseField id="delete_success" :name="t('components.nodes.vectorDb.DeleteData.delete_success')" type="source"
        nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>