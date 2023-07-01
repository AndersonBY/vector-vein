<script setup>
import { defineComponent, ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { PlusOutlined, MinusCircleOutlined } from '@ant-design/icons-vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import TemplateEditorModal from '@/components/TemplateEditorModal.vue'

defineComponent({
  name: 'TemplateCompose',
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
    "task_name": "text_processing.template_compose",
    "has_inputs": true,
    "template": {
      "template": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "template",
        "display_name": "template",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
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
const emit = defineEmits(['change', 'delete'])

const { t } = useI18n()

const fieldsData = ref(props.data.template)

const newFieldData = reactive({
  "required": true,
  "placeholder": "",
  "show": false,
  "multiline": false,
  "value": "",
  "options": [],
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
  props.events.change({
    id: props.id,
    data: props.data,
  })
  newFieldData.display_name = ''
  newFieldData.options = []
}
const removeField = (field) => {
  delete fieldsData.value[field]
  props.events.change({
    id: props.id,
    data: props.data,
  })
}

const addListOptionsItem = (newValue, index) => {
  newFieldData.options[index] = {
    "value": newValue,
    "label": newValue
  }
}
const deleteListOptionsItem = (index) => {
  newFieldData.options.splice(index, 1)
}

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}

const openTemplateEditor = ref(false)
</script>

<template>
  <BaseNode style="width: 400px" :title="t('components.nodes.textProcessing.TemplateCompose.title')"
    :description="props.data.description" documentLink="https://vectorvein.com/help/docs/text-processing#h2-8"
    @delete="deleteNode">
    <template #main>
      <a-row style="display:block;">
        <template v-for="(field, fieldIndex) in Object.keys(fieldsData)" :key="fieldIndex">
          <a-col :span="24" v-if="!['template', 'output'].includes(field)">
            <BaseField :id="field" :name="fieldsData[field].display_name" required type="target" deletable
              @delete="removeField(field)" v-model:show="fieldsData[field].show">
              <a-select class="field-content" style="width: 100%;" v-model:value="fieldsData[field].value"
                :options="fieldsData[field].options" :placeholder="fieldsData[field].placeholder"
                v-if="fieldsData[field].field_type == 'select'" />
              <a-textarea class="field-content" v-model:value="fieldsData[field].value"
                :autoSize="{ minRows: 1, maxRows: 10 }" :showCount="true" :placeholder="fieldsData[field].placeholder"
                v-else-if="fieldsData[field].field_type == 'textarea'" />
              <a-input class="field-content" v-model:value="fieldsData[field].value"
                :placeholder="fieldsData[field].placeholder" v-else-if="fieldsData[field].field_type == 'input'" />
            </BaseField>
          </a-col>
        </template>

        <a-col :span="24" style="padding: 10px">
          <a-button type="dashed" block @click="openAddField" class="add-field-button">
            <PlusOutlined />
            {{ t('components.nodes.textProcessing.TemplateCompose.add_field') }}
          </a-button>
          <a-drawer v-model:open="showAddField" class="custom-class"
            :title="t('components.nodes.textProcessing.TemplateCompose.add_field')" placement="right">
            <template #extra>
              <a-button type="primary" @click="addField">
                {{ t('common.add') }}
              </a-button>
            </template>
            <a-form>
              <a-form-item :label="t('components.nodes.textProcessing.TemplateCompose.add_field_type')">
                <a-select ref="select" v-model:value="newFieldData.field_type" style="width: 120px"
                  @change="newFieldDataTypeChange">
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
                <a-input v-model:value="newFieldData.display_name" />
              </a-form-item>

              <a-form-item :label="t('components.nodes.textProcessing.TemplateCompose.add_field_list_options')"
                v-if="newFieldData.field_type == 'select'">
                <a-row type="flex" :gutter="[12, 12]">
                  <a-col :span="24" :key="index" v-for="(item, index) in newFieldData.options">
                    <div style="display: flex; gap: 5px;">
                      <a-input :value="item.value" @input="addListOptionsItem($event.target.value, index)" />
                      <MinusCircleOutlined @click="deleteListOptionsItem(index)" />
                    </div>
                  </a-col>
                  <a-col :span="24">
                    <a-button type="dashed" style="width: 100%;" @click="newFieldData.options.push('')">
                      <PlusOutlined />
                      {{ t('components.nodes.listField.add_item') }}
                    </a-button>
                  </a-col>
                </a-row>
              </a-form-item>

            </a-form>
          </a-drawer>
        </a-col>
      </a-row>

      <BaseField id="template" :name="t('components.nodes.textProcessing.TemplateCompose.template')" required
        type="target" v-model:show="fieldsData.template.show">
        <a-typography-paragraph :ellipsis="{ row: 1, expandable: false }"
          :content="fieldsData.template.value"></a-typography-paragraph>
        <a-button block type="primary" class="open-template-editor-button" @click="openTemplateEditor = true">
          {{ t('components.nodes.textProcessing.TemplateCompose.open_template_editor') }}
        </a-button>
        <TemplateEditorModal v-model:open="openTemplateEditor" v-model:template="fieldsData.template.value"
          :fields="fieldsData" />
      </BaseField>
      <a-divider></a-divider>

    </template>
    <template #output>
      <BaseField id="output" :name="t('components.nodes.textProcessing.TemplateCompose.output')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>