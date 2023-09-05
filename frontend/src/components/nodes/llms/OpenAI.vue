<script setup>
import { ref, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { AddOne, ReduceOne } from '@icon-park/vue-next'
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
        "value": "gpt-3.5-turbo",
        "password": false,
        "options": [
          {
            "value": "gpt-3.5-turbo",
            "label": "gpt-3.5-turbo"
          },
          {
            "value": "gpt-3.5-turbo-16k",
            "label": "gpt-3.5-turbo-16k"
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

const newFunctionData = reactive({
  "name": "",
  "description": "",
  "parameters": {
    "type": "object",
    "properties": {},
    "required": [],
  }
})
const showAddFunctionDrawer = ref(false)
const openAddFunctionDrawer = () => {
  showAddFunctionDrawer.value = true
}
const addFunction = () => {
  fieldsData.value.functions.value.push(JSON.parse(JSON.stringify(newFunctionData)))
  showAddFunctionDrawer.value = false
  newFunctionData.name = ''
  newFunctionData.description = ''
  newFunctionData.parameters = {
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

const newPropertyData = reactive({
  "name": "",
  "type": "string",
  "description": ""
})

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
const showAddPropertyDrawer = ref(false)
const openAddPropertyDrawer = () => {
  showAddPropertyDrawer.value = true
}
const addProperty = () => {
  newFunctionData.parameters.properties[newPropertyData.name] = {
    "type": newPropertyData.type,
    "description": newPropertyData.description
  }
  showAddPropertyDrawer.value = false
  newPropertyData.name = ''
  newPropertyData.type = 'string'
  newPropertyData.description = ''
}
const removeProperty = (property) => {
  delete newFunctionData.parameters.properties[property]
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
                  {{ func.name }}
                  <ReduceOne @click="removeFunction(index)" />
                </div>
              </a-col>
              <a-col :span="24">
                <a-button type="dashed" block @click="openAddFunctionDrawer" class="add-field-button">
                  <AddOne />
                  {{ t('components.nodes.llms.OpenAI.add_function') }}
                </a-button>
              </a-col>
            </a-row>
            <a-drawer v-model:open="showAddFunctionDrawer" :title="t('components.nodes.llms.OpenAI.add_function')"
              placement="right" :width="500">
              <template #extra>
                <a-button type="primary" @click="addFunction">
                  {{ t('common.add') }}
                </a-button>
              </template>
              <a-form>
                <a-form-item :label="t('components.nodes.llms.OpenAI.function_name')">
                  <a-input v-model:value="newFunctionData.name" />
                </a-form-item>
                <a-form-item :label="t('components.nodes.llms.OpenAI.function_description')">
                  <a-textarea v-model:value="newFunctionData.description" />
                </a-form-item>

                <a-form-item :label="t('components.nodes.llms.OpenAI.function_parameters')">
                  <a-row type="flex" :gutter="[12, 12]">
                    <a-col :span="24" :key="index"
                      v-for="(propertyName, index) in Object.keys(newFunctionData.parameters.properties)">
                      <div style="display: flex; gap: 5px; align-items: center;">
                        {{ propertyName }}
                        <ReduceOne @click="removeProperty(propertyName)" />
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
                  <a-checkbox-group v-model:value="newFunctionData.parameters.required" name="checkboxgroup"
                    :options="Object.keys(newFunctionData.parameters.properties).map(property => ({ label: property, value: property }))" />
                </a-form-item>
              </a-form>
            </a-drawer>

            <a-drawer v-model:open="showAddPropertyDrawer" :title="t('components.nodes.llms.OpenAI.add_parameter')"
              placement="right">
              <template #extra>
                <a-button type="primary" @click="addProperty">
                  {{ t('common.add') }}
                </a-button>
              </template>
              <a-form>
                <a-form-item :label="t('components.nodes.llms.OpenAI.parameter_name')">
                  <a-input v-model:value="newPropertyData.name" />
                </a-form-item>
                <a-form-item :label="t('components.nodes.llms.OpenAI.parameter_description')">
                  <a-textarea v-model:value="newPropertyData.description" />
                </a-form-item>
                <a-form-item :label="t('components.nodes.llms.OpenAI.parameter_type')">
                  <a-select ref="select" v-model:value="newPropertyData.type" :options="propertyTypeOptions">
                  </a-select>
                </a-form-item>
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
        <a-col :span="24">
          <BaseField id="function_call_output" :name="t('components.nodes.llms.OpenAI.function_call_output')"
            type="source" nameOnly>
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="function_call_arguments" :name="t('components.nodes.llms.OpenAI.function_call_arguments')"
            type="source" nameOnly>
          </BaseField>
        </a-col>
      </a-row>
    </template>
  </BaseNode>
</template>

<style></style>