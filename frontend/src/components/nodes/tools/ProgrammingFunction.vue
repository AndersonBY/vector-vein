<script setup>
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { AddOne } from '@icon-park/vue-next'
import { message } from 'ant-design-vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import CodeEditorModal from '@/components/CodeEditorModal.vue'
import { createTemplateData } from './ProgrammingFunction'

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

const fieldsData = ref(props.data.template)
const templateData = createTemplateData()
Object.entries(templateData.template).forEach(([key, value]) => {
  fieldsData.value[key] = fieldsData.value[key] || value
  if (value.is_output) {
    fieldsData.value[key].is_output = true
  }
})

const reservedFieldNames = ['language', 'code', 'output', 'use_oversea_node', 'list_input', 'error_msg', 'console_msg', 'files']

const newFieldData = reactive({
  "required": true,
  "placeholder": "",
  "show": false,
  "value": "",
  "password": false,
  "name": "",
  "display_name": "",
  "type": "str",
  "list": false,
  "field_type": "input",
})
const newFieldDataTypeChange = (value) => {
  newFieldData.multiline = value == 'textarea' ? true : false
}
const showAddField = ref(false)
const openAddField = () => {
  showAddField.value = true
}
const addField = () => {
  if (reservedFieldNames.includes(newFieldData.display_name)) {
    message.error(t('components.nodes.tools.ProgrammingFunction.parameter_name_reserved'))
    return
  }
  newFieldData.name = newFieldData.display_name
  fieldsData.value[newFieldData.name] = JSON.parse(JSON.stringify(newFieldData))
  showAddField.value = false
}
const removeField = (field) => {
  delete fieldsData.value[field]
}

const editorModal = reactive({
  open: false,
  code: '',
})
</script>

<template>
  <BaseNode :nodeId="id" :fieldsData="fieldsData" :debug="props.data.debug"
    translatePrefix="components.nodes.tools.ProgrammingFunction"
    documentLink="https://vectorvein.com/help/docs/tools#h2-4">
    <template #main>
      <a-flex vertical gap="small">
        <BaseField :name="fieldsData.language.display_name" required type="target" @delete="removeField(field)"
          v-model:data="fieldsData.language">
          <a-select class="field-content" style="width: 100%;" v-model:value="fieldsData.language.value"
            :options="fieldsData.language.options" />
        </BaseField>

        <template v-for="(field, fieldIndex) in Object.keys(fieldsData)" :key="fieldIndex">
          <BaseField v-if="!reservedFieldNames.includes(field)"
            :name="`${fieldsData[field].display_name}: ${fieldsData[field].type}`" required type="target" deletable
            @delete="removeField(field)" v-model:data="fieldsData[field]">
            <a-select class="field-content" style="width: 100%;" v-model:value="fieldsData[field].value"
              :options="fieldsData[field].options" v-if="fieldsData[field].field_type == 'select'" />
            <a-textarea class="field-content" v-model:value="fieldsData[field].value"
              :autoSize="{ minRows: 1, maxRows: 10 }" :showCount="true" :placeholder="fieldsData[field].placeholder"
              v-else-if="fieldsData[field].field_type == 'textarea'" />
            <a-input class="field-content" v-model:value="fieldsData[field].value"
              :placeholder="fieldsData[field].placeholder" v-else-if="fieldsData[field].field_type == 'input'" />
          </BaseField>
        </template>

        <div style="padding: 10px;">
          <a-button type="dashed" block @click="openAddField" class="add-field-button">
            <AddOne />
            {{ t('components.nodes.tools.ProgrammingFunction.add_parameter') }}
          </a-button>
          <a-drawer v-model:open="showAddField" class="custom-class" style="color: red"
            :title="t('components.nodes.tools.ProgrammingFunction.add_parameter')" placement="right">
            <template #extra>
              <a-button type="primary" @click="addField">
                {{ t('common.add') }}
              </a-button>
            </template>
            <a-form>
              <a-form-item :label="t('components.nodes.tools.ProgrammingFunction.add_parameter_type')">
                <a-select v-model:value="newFieldData.type" style="width: 120px" @change="newFieldDataTypeChange">
                  <a-select-option value="str">
                    {{ t('components.nodes.tools.ProgrammingFunction.parameter_type_str') }}
                  </a-select-option>
                  <a-select-option value="int">
                    {{ t('components.nodes.tools.ProgrammingFunction.parameter_type_int') }}
                  </a-select-option>
                  <a-select-option value="float">
                    {{ t('components.nodes.tools.ProgrammingFunction.parameter_type_float') }}
                  </a-select-option>
                  <a-select-option value="bool">
                    {{ t('components.nodes.tools.ProgrammingFunction.parameter_type_bool') }}
                  </a-select-option>
                  <a-select-option value="list">
                    {{ t('components.nodes.tools.ProgrammingFunction.parameter_type_list') }}
                  </a-select-option>
                  <a-select-option value="dict">
                    {{ t('components.nodes.tools.ProgrammingFunction.parameter_type_dict') }}
                  </a-select-option>
                </a-select>
              </a-form-item>

              <a-form-item :label="t('components.nodes.tools.ProgrammingFunction.add_parameter_name')">
                <a-input v-model:value="newFieldData.display_name" />
              </a-form-item>

            </a-form>
          </a-drawer>
        </div>

        <BaseField :name="t('components.nodes.tools.ProgrammingFunction.code')" required type="target"
          v-model:data="fieldsData.code">
          <a-typography-paragraph :ellipsis="{ row: 1, expandable: false }"
            :content="fieldsData.code.value"></a-typography-paragraph>
          <a-button type="dashed" block @click="editorModal.open = true">
            {{ t('components.nodes.tools.ProgrammingFunction.open_editor') }}
          </a-button>
          <CodeEditorModal :language="fieldsData.language.value" v-model:open="editorModal.open"
            v-model:code="fieldsData.code.value" />
        </BaseField>

        <BaseField :name="t('components.nodes.tools.ProgrammingFunction.list_input')" name-only type="target"
          v-model:data="fieldsData.list_input">
          <template #inline>
            <a-checkbox v-model:checked="fieldsData.list_input.value">
            </a-checkbox>
          </template>
        </BaseField>
      </a-flex>
    </template>
  </BaseNode>
</template>