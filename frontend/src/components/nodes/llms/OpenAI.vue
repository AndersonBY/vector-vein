<script setup>
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { AddOne, ReduceOne, Edit } from '@icon-park/vue-next'
import { message } from 'ant-design-vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import TemperatureInput from '@/components/nodes/TemperatureInput.vue'

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
    "task_name": "llms.open_ai",
    "has_inputs": true,
    "template": {
      "prompt": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "prompt",
        "display_name": "prompt",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "llm_model": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "gpt-3.5-turbo-1106",
        "password": false,
        "options": [
          {
            "value": "gpt-3.5-turbo-1106",
            "label": "gpt-3.5-turbo-1106"
          },
          {
            "value": "gpt-3.5-turbo",
            "label": "gpt-3.5-turbo"
          },
          {
            "value": "gpt-3.5-turbo-16k",
            "label": "gpt-3.5-turbo-16k"
          },
          {
            "value": "gpt-4-1106-preview",
            "label": "gpt-4-1106-preview"
          },
          {
            "value": "gpt-4",
            "label": "gpt-4"
          },
          {
            "value": "gpt-4-32k",
            "label": "gpt-4-32k"
          },
        ],
        "name": "llm_model",
        "display_name": "llm_model",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "temperature": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": 0.7,
        "password": false,
        "name": "temperature",
        "display_name": "temperature",
        "type": "float",
        "clear_after_run": true,
        "list": false,
        "field_type": "number"
      },
      "response_format": {
        "required": false,
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
            "value": "json_object",
            "label": "JSON"
          },
        ],
        "name": "response_format",
        "display_name": "response_format",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "use_function_call": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": false,
        "password": false,
        "name": "use_function_call",
        "display_name": "use_function_call",
        "type": "bool",
        "clear_after_run": true,
        "list": false,
        "field_type": "checkbox"
      },
      "functions": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": [],
        "password": false,
        "name": "functions",
        "display_name": "functions",
        "type": "list",
        "clear_after_run": true,
        "list": false,
        "field_type": "select"
      },
      "function_call_mode": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "auto",
        "password": false,
        "options": [
          {
            "value": "auto",
            "label": "auto"
          },
          {
            "value": "none",
            "label": "none"
          },
        ],
        "name": "function_call_mode",
        "display_name": "function_call_mode",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
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
        "field_type": ""
      },
      "function_call_output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "function_call_output",
        "display_name": "function_call_output",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": ""
      },
      "function_call_arguments": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "function_call_arguments",
        "display_name": "function_call_arguments",
        "type": "dict",
        "clear_after_run": true,
        "list": false,
        "field_type": ""
      },
    }
  },
})

const { t } = useI18n()

const fieldsData = ref(props.data.template)
if (!fieldsData.value.use_function_call) {
  fieldsData.value.use_function_call = {
    "required": true,
    "placeholder": "",
    "show": false,
    "multiline": true,
    "value": false,
    "password": false,
    "name": "use_function_call",
    "display_name": "use_function_call",
    "type": "bool",
    "clear_after_run": true,
    "list": false,
    "field_type": "checkbox"
  }
}
if (!fieldsData.value.functions) {
  fieldsData.value.functions = {
    "required": true,
    "placeholder": "",
    "show": false,
    "multiline": true,
    "value": [],
    "password": false,
    "name": "functions",
    "display_name": "functions",
    "type": "list",
    "clear_after_run": true,
    "list": false,
    "field_type": "select"
  }
}
if (!fieldsData.value.function_call_mode) {
  fieldsData.value.function_call_mode = {
    "required": false,
    "placeholder": "",
    "show": false,
    "multiline": false,
    "value": "auto",
    "password": false,
    "options": [
      {
        "value": "auto",
        "label": "auto"
      },
      {
        "value": "none",
        "label": "none"
      },
    ],
    "name": "function_call_mode",
    "display_name": "function_call_mode",
    "type": "str",
    "clear_after_run": false,
    "list": true,
    "field_type": "select"
  }
}
if (!fieldsData.value.response_format) {
  fieldsData.value.response_format = {
    "required": false,
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
        "value": "json_object",
        "label": "JSON"
      },
    ],
    "name": "response_format",
    "display_name": "response_format",
    "type": "str",
    "clear_after_run": false,
    "list": true,
    "field_type": "select"
  }
}

const updateFunctionCallModeOptions = () => {
  fieldsData.value.function_call_mode.options = [
    {
      "value": "auto",
      "label": "auto"
    },
    {
      "value": "none",
      "label": "none"
    },
  ]
  fieldsData.value.function_call_mode.options = fieldsData.value.function_call_mode.options.concat(
    fieldsData.value.functions.value.map(func => ({
      "value": func.name,
      "label": func.name
    }))
  )
}

const isEditingFunction = ref(false)
const editingFunctionIndex = ref(-1)
const functionData = reactive({
  "name": "",
  "description": "",
  "parameters": {
    "type": "object",
    "properties": {},
    "required": [],
  }
})
const showFunctionDataDrawer = ref(false)
const openAddFunctionDataDrawer = () => {
  isEditingFunction.value = false
  functionData.name = ''
  functionData.description = ''
  functionData.parameters = {
    "type": "object",
    "properties": {},
    "required": [],
  }
  showFunctionDataDrawer.value = true
}
const addFunction = () => {
  fieldsData.value.functions.value.push(JSON.parse(JSON.stringify(functionData)))
  showFunctionDataDrawer.value = false
  functionData.name = ''
  functionData.description = ''
  functionData.parameters = {
    "type": "object",
    "properties": {},
    "required": [],
  }
  updateFunctionCallModeOptions()
}
const removeFunction = (index) => {
  fieldsData.value.functions.value.splice(index, 1)
  updateFunctionCallModeOptions()
}
const openEditFunctionDataDrawer = (index) => {
  isEditingFunction.value = true
  editingFunctionIndex.value = index
  functionData.name = fieldsData.value.functions.value[index].name
  functionData.description = fieldsData.value.functions.value[index].description
  functionData.parameters = JSON.parse(JSON.stringify(fieldsData.value.functions.value[index].parameters))
  showFunctionDataDrawer.value = true
}
const editFunction = () => {
  fieldsData.value.functions.value[editingFunctionIndex.value].name = functionData.name
  fieldsData.value.functions.value[editingFunctionIndex.value].description = functionData.description
  fieldsData.value.functions.value[editingFunctionIndex.value].parameters = JSON.parse(JSON.stringify(functionData.parameters))
  showFunctionDataDrawer.value = false
  updateFunctionCallModeOptions()
}

const isEditingProperty = ref(false)
const editingProperty = ref('')
const propertyData = reactive({
  "name": "",
  "type": "string",
  "description": ""
})

const arrayConfigurationMode = ref('simple')
const arrayItemsType = ref('string')
const arrayItemsManualSchema = ref('{"items": {"type": "string"}}')

const objectItemsManualSchema = ref('{"properties": {}, "required": []}')

const propertyTypeChanged = (value) => {
  if (value == 'array') {
    arrayConfigurationMode.value = 'simple'
    arrayItemsType.value = 'string'
  }
}

const propertyTypeOptions = [
  {
    value: 'string',
    label: 'string'
  },
  {
    value: 'number',
    label: 'number'
  },
  {
    value: 'integer',
    label: 'integer'
  },
  {
    value: 'object',
    label: 'object'
  },
  {
    value: 'array',
    label: 'array'
  },
  {
    value: 'boolean',
    label: 'boolean'
  },
  {
    value: 'null',
    label: 'null'
  },
]
const showPropertyDataDrawer = ref(false)
const openAddPropertyDrawer = () => {
  isEditingProperty.value = false
  showPropertyDataDrawer.value = true
}
const setPropertyData = () => {
  functionData.parameters.properties[propertyData.name] = {
    "type": propertyData.type,
    "description": propertyData.description
  }
  if (propertyData.type == 'array') {
    if (arrayConfigurationMode.value == 'simple') {
      functionData.parameters.properties[propertyData.name].items = {
        "type": arrayItemsType.value
      }
    } else {
      try {
        JSON.parse(arrayItemsManualSchema.value)
      } catch (error) {
        message.error(t('components.nodes.llms.OpenAI.array_items_manual_schema_error'))
        return
      }
      functionData.parameters.properties[propertyData.name] = {
        ...functionData.parameters.properties[propertyData.name],
        ...JSON.parse(arrayItemsManualSchema.value)
      }
    }
  } else if (propertyData.type == 'object') {
    try {
      JSON.parse(objectItemsManualSchema.value)
    } catch (error) {
      message.error(t('components.nodes.llms.OpenAI.object_items_manual_schema_error'))
      return
    }
    functionData.parameters.properties[propertyData.name] = {
      ...functionData.parameters.properties[propertyData.name],
      ...JSON.parse(objectItemsManualSchema.value)
    }
  }
}
const addProperty = () => {
  setPropertyData()
  showPropertyDataDrawer.value = false
  propertyData.name = ''
  propertyData.type = 'string'
  propertyData.description = ''
}
const removeProperty = (property) => {
  delete functionData.parameters.properties[property]
}
const openEditPropertyDrawer = (property) => {
  isEditingProperty.value = true
  editingProperty.value = property
  propertyData.name = property
  propertyData.type = functionData.parameters.properties[property].type
  propertyData.description = functionData.parameters.properties[property].description
  showPropertyDataDrawer.value = true
}
const editProperty = () => {
  delete functionData.parameters.properties[editingProperty.value]
  setPropertyData()
  showPropertyDataDrawer.value = false
  propertyData.name = ''
  propertyData.type = 'string'
  propertyData.description = ''
}

const responseFormatChanged = (value) => {
  if (value == 'text') return
  // 如果fieldsData.llm_model.value不是gpt-3.5-turbo-1106或者gpt-4-1106-preview
  // 则强制设置为gpt-3.5-turbo-1106，通知提醒用户
  if (fieldsData.value.llm_model.value != 'gpt-3.5-turbo-1106' && fieldsData.value.llm_model.value != 'gpt-4-1106-preview') {
    fieldsData.value.llm_model.value = 'gpt-3.5-turbo-1106'
    message.warning(t('components.nodes.llms.OpenAI.response_format_warning'))
  }
}
</script>

<template>
  <BaseNode :nodeId="id" :title="t('components.nodes.llms.OpenAI.title')" :description="props.data.description"
    documentLink="https://vectorvein.com/help/docs/language-models#h2-0">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="prompt" :name="t('components.nodes.llms.OpenAI.prompt')" required type="target"
            v-model:show="fieldsData.prompt.show">
            <a-textarea class="field-content" v-model:value="fieldsData.prompt.value" :autoSize="true" :showCount="true"
              :placeholder="fieldsData.prompt.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="llm_model" :name="t('components.nodes.llms.OpenAI.llm_model')" required type="target"
            v-model:show="fieldsData.llm_model.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.llm_model.value"
              :options="fieldsData.llm_model.options" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="temperature" :name="t('components.nodes.llms.OpenAI.temperature')" required type="target"
            v-model:show="fieldsData.temperature.show">
            <TemperatureInput v-model="fieldsData.temperature.value" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="response_format" :name="t('components.nodes.llms.OpenAI.response_format')" required type="target"
            v-model:show="fieldsData.response_format.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.response_format.value"
              :options="fieldsData.response_format.options" @change="responseFormatChanged" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="use_function_call" :name="t('components.nodes.llms.OpenAI.use_function_call')" required
            type="target" v-model:show="fieldsData.use_function_call.show">
            <template #inline>
              <a-checkbox v-model:checked="fieldsData.use_function_call.value">
              </a-checkbox>
            </template>
          </BaseField>
        </a-col>

        <a-col :span="24" v-show="fieldsData.use_function_call.value">
          <BaseField id="functions" :name="t('components.nodes.llms.OpenAI.functions')" type="target"
            v-model:show="fieldsData.functions.show">
            <a-row type="flex" :gutter="[12, 12]">
              <a-col :span="24" :key="index" v-for="(func, index) in fieldsData.functions.value">
                <div style="display: flex; gap: 5px; align-items: center;">
                  <a-button block @click="openEditFunctionDataDrawer(index)">
                    <Edit />
                    {{ func.name }}
                  </a-button>
                  <ReduceOne class="clickable-icon" fill="#ff4d4f" @click="removeFunction(index)" />
                </div>
              </a-col>
              <a-col :span="24">
                <a-button type="dashed" block @click="openAddFunctionDataDrawer" class="add-field-button">
                  <AddOne />
                  {{ t('components.nodes.llms.OpenAI.add_function') }}
                </a-button>
              </a-col>
            </a-row>
            <a-drawer v-model:open="showFunctionDataDrawer" :title="t('components.nodes.llms.OpenAI.add_function')"
              placement="right" :width="500">
              <template #extra>
                <a-button type="primary" @click="editFunction(editingFunctionIndex)" v-if="isEditingFunction">
                  {{ t('common.edit') }}
                </a-button>
                <a-button type="primary" @click="addFunction" v-else>
                  {{ t('common.add') }}
                </a-button>
              </template>
              <a-form>
                <a-form-item :label="t('components.nodes.llms.OpenAI.function_name')">
                  <a-input v-model:value="functionData.name" />
                </a-form-item>
                <a-form-item :label="t('components.nodes.llms.OpenAI.function_description')">
                  <a-textarea v-model:value="functionData.description" />
                </a-form-item>

                <a-form-item :label="t('components.nodes.llms.OpenAI.function_parameters')">
                  <a-row type="flex" :gutter="[12, 12]">
                    <a-col :span="24" :key="index"
                      v-for="(propertyName, index) in Object.keys(functionData.parameters.properties)">
                      <div style="display: flex; gap: 5px; align-items: center;">
                        <a-button block @click="openEditPropertyDrawer(propertyName)">
                          <Edit />
                          {{ propertyName }}: {{ functionData.parameters.properties[propertyName].type }}
                        </a-button>
                        <ReduceOne class="clickable-icon" fill="#ff4d4f" @click="removeProperty(propertyName)" />
                      </div>
                    </a-col>
                    <a-col :span="24">
                      <a-button type="dashed" style="width: 100%;" @click="openAddPropertyDrawer">
                        <AddOne />
                        {{ t('components.nodes.llms.OpenAI.add_parameter') }}
                      </a-button>
                    </a-col>
                  </a-row>
                </a-form-item>

                <a-form-item :label="t('components.nodes.llms.OpenAI.function_required_parameters')">
                  <a-checkbox-group v-model:value="functionData.parameters.required" name="checkboxgroup"
                    :options="Object.keys(functionData.parameters.properties).map(property => ({ label: property, value: property }))" />
                </a-form-item>
              </a-form>
            </a-drawer>

            <a-drawer v-model:open="showPropertyDataDrawer" :title="t('components.nodes.llms.OpenAI.add_parameter')"
              placement="right">
              <template #extra>
                <a-button type="primary" @click="editProperty" v-if="isEditingProperty">
                  {{ t('common.edit') }}
                </a-button>
                <a-button type="primary" @click="addProperty" v-else>
                  {{ t('common.add') }}
                </a-button>
              </template>
              <a-form>
                <a-form-item :label="t('components.nodes.llms.OpenAI.parameter_name')">
                  <a-input v-model:value="propertyData.name" />
                </a-form-item>
                <a-form-item :label="t('components.nodes.llms.OpenAI.parameter_description')">
                  <a-textarea v-model:value="propertyData.description" />
                </a-form-item>
                <a-form-item :label="t('components.nodes.llms.OpenAI.parameter_type')">
                  <a-select ref="select" v-model:value="propertyData.type" :options="propertyTypeOptions"
                    @change="propertyTypeChanged">
                  </a-select>
                </a-form-item>
                <template v-if="propertyData.type == 'array'">
                  <a-form-item :label="t('components.nodes.llms.OpenAI.array_configuration_mode')">
                    <a-select ref="select" v-model:value="arrayConfigurationMode">
                      <a-select-option value="simple">
                        {{ t('components.nodes.llms.OpenAI.array_configuration_mode_simple') }}
                      </a-select-option>
                      <a-select-option value="manual">
                        {{ t('components.nodes.llms.OpenAI.array_configuration_mode_manual') }}
                      </a-select-option>
                    </a-select>
                  </a-form-item>
                  <a-form-item :label="t('components.nodes.llms.OpenAI.array_items_type')"
                    v-if="arrayConfigurationMode == 'simple'">
                    <a-select ref="select" v-model:value="arrayItemsType" :options="propertyTypeOptions">
                    </a-select>
                  </a-form-item>
                  <a-form-item :label="t('components.nodes.llms.OpenAI.array_items_manual_schema')"
                    v-if="arrayConfigurationMode == 'manual'">
                    <a-textarea v-model:value="arrayItemsManualSchema" :autoSize="{ minRows: 1, maxRows: 20 }"
                      :showCount="true" />
                  </a-form-item>
                </template>
                <template v-else-if="propertyData.type == 'object'">
                  <a-form-item :label="t('components.nodes.llms.OpenAI.object_items_manual_schema')">
                    <a-textarea v-model:value="objectItemsManualSchema" :autoSize="{ minRows: 1, maxRows: 20 }"
                      :showCount="true" />
                  </a-form-item>
                </template>
              </a-form>
            </a-drawer>
          </BaseField>
        </a-col>

        <a-col :span="24" v-show="fieldsData.use_function_call.value">
          <BaseField id="function_call_mode" :name="t('components.nodes.llms.OpenAI.function_call_mode')" type="target"
            v-model:show="fieldsData.function_call_mode.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.function_call_mode.value"
              :options="fieldsData.function_call_mode.options" />
          </BaseField>
        </a-col>
      </a-row>
    </template>
    <template #output>
      <a-row type="flex" style="width: 100%">
        <a-col :span="24">
          <BaseField id="output" :name="t('components.nodes.llms.OpenAI.output')" type="source" nameOnly>
          </BaseField>
        </a-col>
        <a-col :span="24" v-show="fieldsData.use_function_call.value">
          <BaseField id="function_call_output" :name="t('components.nodes.llms.OpenAI.function_call_output')"
            type="source" nameOnly>
          </BaseField>
        </a-col>
        <a-col :span="24" v-show="fieldsData.use_function_call.value">
          <BaseField id="function_call_arguments" :name="t('components.nodes.llms.OpenAI.function_call_arguments')"
            type="source" nameOnly>
          </BaseField>
        </a-col>
      </a-row>
    </template>
  </BaseNode>
</template>

<style>
.clickable-icon {
  cursor: pointer;
}
</style>