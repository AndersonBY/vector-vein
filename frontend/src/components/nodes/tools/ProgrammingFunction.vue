<script setup>
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { AddOne } from '@icon-park/vue-next'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import CodeEditorModal from '@/components/CodeEditorModal.vue'

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
    "task_name": "tools.programming_function",
    "has_inputs": true,
    "template": {
      "language": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "python",
        "password": false,
        "options": [
          {
            "value": "python",
            "label": "Python"
          },
        ],
        "name": "language",
        "display_name": "language",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "select"
      },
      "code": {
        "required": true,
        "placeholder": "some code...",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "code",
        "display_name": "code",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "list_input": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": false,
        "password": false,
        "name": "list_input",
        "display_name": "list_input",
        "type": "bool",
        "clear_after_run": true,
        "list": false,
        "field_type": "checkbox"
      },
      "output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "output",
        "display_name": "output",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      }
    }
  }
})

const { t } = useI18n()

const fieldsData = ref(props.data.template)
if (!fieldsData.value.list_input) {
  fieldsData.value.list_input = {
    "required": true,
    "placeholder": "",
    "show": true,
    "multiline": true,
    "value": false,
    "password": false,
    "name": "list_input",
    "display_name": "list_input",
    "type": "bool",
    "clear_after_run": true,
    "list": false,
    "field_type": "checkbox"
  }
}

const newFieldData = reactive({
  "required": true,
  "placeholder": "",
  "show": false,
  "multiline": false,
  "value": "",
  "password": false,
  "name": "",
  "display_name": "",
  "type": "str",
  "clear_after_run": false,
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
  newFieldData.name = newFieldData.display_name
  fieldsData.value[newFieldData.name] = JSON.parse(JSON.stringify(newFieldData))
  showAddField.value = false
}
const removeField = (field) => {
  delete fieldsData.value[field]
}

const codeEditorModal = reactive({
  open: false,
  code: '',
})
</script>

<template>
  <BaseNode :nodeId="id" :title="t('components.nodes.tools.ProgrammingFunction.title')"
    :description="props.data.description" documentLink="https://vectorvein.com/help/docs/tools#h2-4">
    <template #main>
      <a-row type="flex">

        <a-col :span="24">
          <BaseField id="language" :name="fieldsData.language.display_name" required type="target"
            @delete="removeField(field)" v-model:show="fieldsData.language.show">
            <a-select class="field-content" style="width: 100%;" v-model:value="fieldsData.language.value"
              :options="fieldsData.language.options" />
          </BaseField>
        </a-col>

        <template v-for="(field, fieldIndex) in Object.keys(fieldsData)" :key="fieldIndex">
          <a-col :span="24" v-if="!['language', 'code', 'output', 'list_input'].includes(field)">
            <BaseField :id="field" :name="`${fieldsData[field].display_name}: ${fieldsData[field].type}`" required
              type="target" deletable @delete="removeField(field)" v-model:show="fieldsData[field].show">
              <a-select class="field-content" style="width: 100%;" v-model:value="fieldsData[field].value"
                :options="fieldsData[field].options" v-if="fieldsData[field].field_type == 'select'" />
              <a-textarea class="field-content" v-model:value="fieldsData[field].value" :autoSize="true" :showCount="true"
                :placeholder="fieldsData[field].placeholder" v-else-if="fieldsData[field].field_type == 'textarea'" />
              <a-input class="field-content" v-model:value="fieldsData[field].value"
                :placeholder="fieldsData[field].placeholder" v-else-if="fieldsData[field].field_type == 'input'" />
            </BaseField>
          </a-col>
        </template>

        <a-col :span="24" style="padding: 10px">
          <a-button type="dashed" style="width: 100%;" @click="openAddField">
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
                </a-select>
              </a-form-item>

              <a-form-item :label="t('components.nodes.tools.ProgrammingFunction.add_parameter_name')">
                <a-input v-model:value="newFieldData.display_name" />
              </a-form-item>

            </a-form>
          </a-drawer>
        </a-col>

        <a-col :span="24">
          <BaseField id="code" :name="t('components.nodes.tools.ProgrammingFunction.code')" required type="target"
            v-model:show="fieldsData.code.show">
            <a-typography-paragraph :ellipsis="{ row: 1, expandable: false }"
              :content="fieldsData.code.value"></a-typography-paragraph>
            <a-button type="primary" @click="codeEditorModal.open = true">
              {{ t('components.nodes.tools.ProgrammingFunction.open_editor') }}
            </a-button>
            <CodeEditorModal :language="fieldsData.language.value" v-model:open="codeEditorModal.open"
              v-model:code="fieldsData.code.value" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="list_input" :name="t('components.nodes.tools.ProgrammingFunction.list_input')" required
            type="target" v-model:show="fieldsData.list_input.show">
            <template #inline>
              <a-checkbox v-model:checked="fieldsData.list_input.value">
              </a-checkbox>
            </template>
          </BaseField>
        </a-col>
      </a-row>

      <a-divider></a-divider>

    </template>
    <template #output>
      <BaseField id="output" :name="t('components.nodes.tools.ProgrammingFunction.output')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>