<script setup>
import { defineComponent, ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { PlusOutlined } from '@ant-design/icons-vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

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
}
const removeField = (field) => {
  delete fieldsData.value[field]
  props.events.change({
    id: props.id,
    data: props.data,
  })
}

const insertFieldVariable = (field, event) => {
  const variable = `{{${field}}}`
  const templateElement = document.getElementById('template-textarea')
  const cursorPosition = templateElement.selectionStart
  if (!event.target.classList.contains('ant-checkbox-input') && !event.target.classList.contains('field-content')) {
    const newText = fieldsData.value.template.value.slice(0, cursorPosition) + variable + fieldsData.value.template.value.slice(cursorPosition);
    fieldsData.value.template.value = newText
  }
}

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}
</script>

<template>
  <BaseNode style="width: 400px" :title="t('components.nodes.textProcessing.TemplateCompose.title')"
    :description="props.data.description" @delete="deleteNode">
    <template #main>
      <a-row style="display:block;">
        <a-tooltip :title="t('components.nodes.textProcessing.TemplateCompose.click_to_add_to_template')">
          <template v-for="(field, fieldIndex) in Object.keys(fieldsData)" :key="fieldIndex">
            <a-col :span="24" @click="insertFieldVariable(field, $event)" v-if="!['template', 'output'].includes(field)">
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
        </a-tooltip>

        <a-col :span="24" style="padding: 10px">
          <a-button type="dashed" style="width: 100%;" @click="openAddField">
            <PlusOutlined />
            {{ t('components.nodes.textProcessing.TemplateCompose.add_field') }}
          </a-button>
          <a-drawer v-model:open="showAddField" class="custom-class" style="color: red"
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
                </a-select>
              </a-form-item>

              <a-form-item :label="t('components.nodes.textProcessing.TemplateCompose.add_field_display_name')">
                <a-input v-model:value="newFieldData.display_name" />
              </a-form-item>

            </a-form>
          </a-drawer>
        </a-col>
      </a-row>

      <BaseField id="template" :name="t('components.nodes.textProcessing.TemplateCompose.template')" required
        type="target" v-model:show="fieldsData.template.show">
        <a-textarea id="template-textarea" v-model:value="fieldsData.template.value"
          :autoSize="{ minRows: 1, maxRows: 10 }" :showCount="true" :placeholder="fieldsData.template.placeholder" />
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