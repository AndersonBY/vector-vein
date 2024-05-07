<script setup>
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { AddOne, ReduceOne, Edit } from '@icon-park/vue-next'
import { useNodeMessagesStore } from '@/stores/nodeMessages'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import TemplateEditorModal from '@/components/nodes/TemplateEditorModal.vue'
import { createTemplateData } from './TemplateCompose'

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

const { t } = useI18n()

const useNodeMessages = useNodeMessagesStore()
const pushMessage = (action, data) => {
  useNodeMessages.push({
    action,
    data,
    nodeId: props.id,
  })
}

const fieldsData = ref(props.data.template)
const templateData = createTemplateData()
Object.entries(templateData.template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) {
    fieldsData.value[key].is_output = true
  }
})

const fieldsOrder = ref(Object.keys(fieldsData.value))

const reservedFieldNames = ['template', 'output']

const editFieldData = reactive({
  "required": true,
  "placeholder": "",
  "show": false,
  "value": "",
  "options": [],
  "name": "",
  "display_name": "",
  "type": "str",
  "list": false,
  "field_type": "input",
})

const showEditField = ref(false)
const addNewField = () => {
  isEditField.value = false
  editFieldData.display_name = ''
  editFieldData.options = []
  showEditField.value = true
}
const saveField = () => {
  if (reservedFieldNames.includes(editFieldData.display_name)) {
    message.error(t('components.nodes.textProcessing.TemplateCompose.name_reserved'))
    return
  }
  const index = fieldsOrder.value.indexOf(originalFieldName.value)
  editFieldData.name = editFieldData.display_name
  fieldsData.value[editFieldData.name] = JSON.parse(JSON.stringify(editFieldData))
  editFieldData.display_name = ''
  editFieldData.options = []
  if (isEditField.value && originalFieldName.value != editFieldData.name) {
    delete fieldsData.value[originalFieldName.value]
    fieldsOrder.value[index] = editFieldData.name
    // 把 fieldsData.value.template.value 中的原字段替换为新字段
    fieldsData.value.template.value = fieldsData.value.template.value.replace(`{{${originalFieldName.value}}}`, `{{${editFieldData.name}}}`)
    pushMessage('change', {
      event: 'editField',
      oldFieldName: originalFieldName.value,
      newFieldName: editFieldData.name,
    })
  } else if (isEditField.value && originalFieldType.value != editFieldData.field_type) {
    fieldsData.value[editFieldData.name].field_type = editFieldData.field_type
    pushMessage('change', {
      event: 'editFieldType',
      fieldName: editFieldData.name,
      fieldType: editFieldData.field_type,
    })
  } else {
    fieldsOrder.value.push(editFieldData.name)
  }
  showEditField.value = false
}
const removeField = (field) => {
  fieldsOrder.value = fieldsOrder.value.filter(item => item != field)
  delete fieldsData.value[field]
  pushMessage('change', { event: 'removeField', fieldName: field })
}

const isEditField = ref(false)
const originalFieldName = ref('')
const originalFieldType = ref('')
const editField = (field) => {
  originalFieldName.value = field
  originalFieldType.value = fieldsData.value[field].field_type
  editFieldData.display_name = field
  editFieldData.name = field
  editFieldData.value = fieldsData.value[field].value
  editFieldData.show = fieldsData.value[field].show
  editFieldData.options = fieldsData.value[field].options
  editFieldData.field_type = fieldsData.value[field].field_type
  showEditField.value = true
  isEditField.value = true
}

const addListOptionsItem = (newValue, index) => {
  editFieldData.options[index] = {
    "value": newValue,
    "label": newValue
  }
}
const deleteListOptionsItem = (index) => {
  editFieldData.options.splice(index, 1)
}

const openTemplateEditor = ref(false)
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :width="300" :fieldsData="fieldsData"
    translatePrefix="components.nodes.textProcessing.TemplateCompose"
    documentLink="https://vectorvein.com/help/docs/text-processing#h2-8">
    <template #main>
      <a-flex vertical gap="small">
        <template v-for="(field, fieldIndex) in fieldsOrder" :key="fieldIndex">
          <BaseField v-if="!['template', 'output'].includes(field)" :name="fieldsData[field].display_name" required
            type="target" deletable editable @delete="removeField(field)" @edit="editField(field)"
            v-model:data="fieldsData[field]">
            <a-select class="field-content" style="width: 100%;" v-model:value="fieldsData[field].value"
              :options="fieldsData[field].options" :placeholder="fieldsData[field].placeholder"
              v-if="fieldsData[field].field_type == 'select'" />
            <a-textarea class="field-content" v-model:value="fieldsData[field].value"
              :autoSize="{ minRows: 2, maxRows: 10 }" :showCount="true" :placeholder="fieldsData[field].placeholder"
              v-else-if="fieldsData[field].field_type == 'textarea'" />
            <a-input class="field-content" v-model:value="fieldsData[field].value"
              :placeholder="fieldsData[field].placeholder" v-else-if="fieldsData[field].field_type == 'input'" />
          </BaseField>
        </template>

        <div class="add-field-button-container">
          <a-button type="dashed" block @click="addNewField" class="add-field-button">
            <template #icon>
              <AddOne />
            </template>
            {{ t('components.nodes.textProcessing.TemplateCompose.add_field') }}
          </a-button>
          <a-drawer v-model:open="showEditField"
            :title="t(`components.nodes.textProcessing.TemplateCompose.${isEditField ? 'edit' : 'add'}_field`)"
            placement="right">
            <template #extra>
              <a-button type="primary" @click="saveField">
                {{ t(isEditField ? 'common.save' : 'common.add') }}
              </a-button>
            </template>
            <a-form>
              <a-form-item :label="t('components.nodes.textProcessing.TemplateCompose.add_field_type')">
                <a-select ref="select" v-model:value="editFieldData.field_type" style="width: 100%">
                  <a-select-option value="input">
                    {{ t('components.nodes.textProcessing.TemplateCompose.field_type_input') }}
                  </a-select-option>
                  <a-select-option value="textarea">
                    {{ t('components.nodes.textProcessing.TemplateCompose.field_type_textarea') }}
                  </a-select-option>
                  <a-select-option value="select">
                    {{ t('components.nodes.textProcessing.TemplateCompose.field_type_select') }}
                  </a-select-option>
                </a-select>
              </a-form-item>

              <a-form-item :label="t('components.nodes.textProcessing.TemplateCompose.add_field_display_name')">
                <a-input v-model:value="editFieldData.display_name" />
              </a-form-item>

              <a-form-item :label="t('components.nodes.textProcessing.TemplateCompose.add_field_list_options')"
                v-if="editFieldData.field_type == 'select'">
                <a-row type="flex" :gutter="[12, 12]">
                  <a-col :span="24" :key="index" v-for="(item, index) in editFieldData.options">
                    <div style="display: flex; gap: 5px;">
                      <a-input :value="item.value" @input="addListOptionsItem($event.target.value, index)" />
                      <ReduceOne @click="deleteListOptionsItem(index)" />
                    </div>
                  </a-col>
                  <a-col :span="24">
                    <a-button type="dashed" style="width: 100%;"
                      @click="editFieldData.options.push({ value: '', label: '' })">
                      <AddOne />
                      {{ t('components.nodes.listField.add_item') }}
                    </a-button>
                  </a-col>
                </a-row>
              </a-form-item>

            </a-form>
          </a-drawer>
        </div>
      </a-flex>

      <BaseField :name="t('components.nodes.textProcessing.TemplateCompose.template')" required type="target"
        v-model:data="fieldsData.template">
        <a-typography-paragraph :ellipsis="{ row: 1, expandable: false }"
          :content="fieldsData.template.value"></a-typography-paragraph>
        <a-button block type="dashed" class="open-template-editor-button" @click="openTemplateEditor = true">
          <template #icon>
            <Edit />
          </template>
          {{ t('components.nodes.textProcessing.TemplateCompose.open_template_editor') }}
        </a-button>
        <TemplateEditorModal v-model:open="openTemplateEditor" v-model:template="fieldsData.template.value"
          :fields="fieldsData" />
      </BaseField>

    </template>
  </BaseNode>
</template>

<style scoped>
.add-field-button-container {
  padding: 10px;
}
</style>