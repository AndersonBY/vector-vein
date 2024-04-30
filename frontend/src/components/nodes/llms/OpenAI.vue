<script setup>
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { AddOne, ReduceOne, Edit } from '@icon-park/vue-next'
import { message } from 'ant-design-vue'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import TemperatureInput from '@/components/nodes/TemperatureInput.vue'
import { createTemplateData } from './OpenAI'

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
        message.error(t('components.nodes.llms.common.array_items_manual_schema_error'))
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
      message.error(t('components.nodes.llms.common.object_items_manual_schema_error'))
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
</script>

<template>
  <BaseNode :nodeId="id" :fieldsData="fieldsData" translatePrefix="components.nodes.llms.OpenAI"
    :debug="props.data.debug" documentLink="https://vectorvein.com/help/docs/language-models#h2-0">
    <template #main>
      <a-flex vertical gap="small">
        <BaseField :name="t('components.nodes.llms.common.prompt')" required type="target"
          v-model:data="fieldsData.prompt">
          <a-textarea class="field-content" v-model:value="fieldsData.prompt.value"
            :autoSize="{ minRows: 2, maxRows: 20 }" :showCount="true" :placeholder="fieldsData.prompt.placeholder" />
        </BaseField>

        <BaseField :name="t('components.nodes.llms.common.llm_model')" required type="target"
          v-model:data="fieldsData.llm_model">
          <a-select style="width: 100%;" v-model:value="fieldsData.llm_model.value"
            :options="fieldsData.llm_model.options" />
        </BaseField>

        <BaseField :name="t('components.nodes.llms.common.temperature')" required type="target"
          v-model:data="fieldsData.temperature">
          <TemperatureInput v-model="fieldsData.temperature.value" />
        </BaseField>

        <BaseField :name="t('components.nodes.llms.common.response_format')" required type="target"
          v-model:data="fieldsData.response_format">
          <a-select style="width: 100%;" v-model:value="fieldsData.response_format.value"
            :options="fieldsData.response_format.options" />
        </BaseField>

        <BaseField :name="t('components.nodes.llms.common.use_function_call')" name-only type="target"
          v-model:data="fieldsData.use_function_call">
          <template #inline>
            <a-checkbox v-model:checked="fieldsData.use_function_call.value">
            </a-checkbox>
          </template>
        </BaseField>

        <BaseField v-show="fieldsData.use_function_call.value" :name="t('components.nodes.llms.common.functions')"
          type="target" v-model:data="fieldsData.functions">
          <a-flex vertical gap="small">
            <a-flex gap="small" align="center" :key="index" v-for="(func, index) in fieldsData.functions.value">
              <a-button block @click="openEditFunctionDataDrawer(index)">
                <Edit />
                {{ func.name }}
              </a-button>
              <a-button type="text" danger @click="removeFunction(index)">
                <template #icon>
                  <ReduceOne />
                </template>
              </a-button>
            </a-flex>
            <a-button type="dashed" block @click="openAddFunctionDataDrawer" class="add-field-button">
              <AddOne />
              {{ t('components.nodes.llms.common.add_function') }}
            </a-button>
          </a-flex>
          <a-drawer v-model:open="showFunctionDataDrawer" :title="t('components.nodes.llms.common.add_function')"
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
              <a-form-item :label="t('components.nodes.llms.common.function_name')">
                <a-input v-model:value="functionData.name" />
              </a-form-item>
              <a-form-item :label="t('components.nodes.llms.common.function_description')">
                <a-textarea v-model:value="functionData.description" :autoSize="{ minRows: 3, maxRows: 20 }"
                  :showCount="true" />
              </a-form-item>

              <a-form-item :label="t('components.nodes.llms.common.function_parameters')">
                <a-row type="flex" :gutter="[12, 12]">
                  <a-col :span="24" :key="index"
                    v-for="(propertyName, index) in Object.keys(functionData.parameters.properties)">
                    <a-flex align="center" gap="5">
                      <a-button block @click="openEditPropertyDrawer(propertyName)">
                        <Edit />
                        {{ propertyName }}: {{ functionData.parameters.properties[propertyName].type }}
                      </a-button>
                      <a-button type="text" danger @click="removeProperty(propertyName)">
                        <template #icon>
                          <ReduceOne />
                        </template>
                      </a-button>
                    </a-flex>
                  </a-col>
                  <a-col :span="24">
                    <a-button block type="dashed"
                      style="display: flex; gap: 6px; align-items: center; justify-content: center;"
                      @click="openAddPropertyDrawer">
                      <AddOne />
                      {{ t('components.nodes.llms.common.add_parameter') }}
                    </a-button>
                  </a-col>
                </a-row>
              </a-form-item>

              <a-form-item :label="t('components.nodes.llms.common.function_required_parameters')">
                <a-checkbox-group v-model:value="functionData.parameters.required" name="checkboxgroup"
                  :options="Object.keys(functionData.parameters.properties).map(property => ({ label: property, value: property }))" />
              </a-form-item>
            </a-form>
          </a-drawer>

          <a-drawer v-model:open="showPropertyDataDrawer" :title="t('components.nodes.llms.common.add_parameter')"
            placement="right" :width="450">
            <template #extra>
              <a-button type="primary" @click="editProperty" v-if="isEditingProperty">
                {{ t('common.edit') }}
              </a-button>
              <a-button type="primary" @click="addProperty" v-else>
                {{ t('common.add') }}
              </a-button>
            </template>
            <a-form>
              <a-form-item :label="t('components.nodes.llms.common.parameter_name')">
                <a-input v-model:value="propertyData.name" />
              </a-form-item>
              <a-form-item :label="t('components.nodes.llms.common.parameter_description')">
                <a-textarea v-model:value="propertyData.description" :autoSize="{ minRows: 3, maxRows: 20 }"
                  :showCount="true" />
              </a-form-item>
              <a-form-item :label="t('components.nodes.llms.common.parameter_type')">
                <a-select ref="select" v-model:value="propertyData.type" :options="propertyTypeOptions"
                  @change="propertyTypeChanged">
                </a-select>
              </a-form-item>
              <template v-if="propertyData.type == 'array'">
                <a-form-item :label="t('components.nodes.llms.common.array_configuration_mode')">
                  <a-select ref="select" v-model:value="arrayConfigurationMode">
                    <a-select-option value="simple">
                      {{ t('components.nodes.llms.common.array_configuration_mode_simple') }}
                    </a-select-option>
                    <a-select-option value="manual">
                      {{ t('components.nodes.llms.common.array_configuration_mode_manual') }}
                    </a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item :label="t('components.nodes.llms.common.array_items_type')"
                  v-if="arrayConfigurationMode == 'simple'">
                  <a-select ref="select" v-model:value="arrayItemsType" :options="propertyTypeOptions">
                  </a-select>
                </a-form-item>
                <a-form-item :label="t('components.nodes.llms.common.array_items_manual_schema')"
                  v-if="arrayConfigurationMode == 'manual'">
                  <a-textarea v-model:value="arrayItemsManualSchema" :autoSize="{ minRows: 3, maxRows: 20 }"
                    :showCount="true" />
                </a-form-item>
              </template>
              <template v-else-if="propertyData.type == 'object'">
                <a-form-item :label="t('components.nodes.llms.common.object_items_manual_schema')">
                  <a-textarea v-model:value="objectItemsManualSchema" :autoSize="{ minRows: 3, maxRows: 20 }"
                    :showCount="true" />
                </a-form-item>
              </template>
            </a-form>
          </a-drawer>
        </BaseField>

        <BaseField v-show="fieldsData.use_function_call.value"
          :name="t('components.nodes.llms.common.function_call_mode')" type="target"
          v-model:data="fieldsData.function_call_mode">
          <a-select style="width: 100%;" v-model:value="fieldsData.function_call_mode.value"
            :options="fieldsData.function_call_mode.options" />
        </BaseField>
      </a-flex>
    </template>
  </BaseNode>
</template>