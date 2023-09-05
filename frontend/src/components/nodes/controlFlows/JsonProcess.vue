<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
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
    "task_name": "control_flows.json_process",
    "has_inputs": true,
    "template": {
      "input": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "input",
        "display_name": "input",
        "type": "str|dict",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
      "process_mode": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "get_value",
        "password": false,
        "options": [
          {
            "value": "get_value",
            "label": "get_value"
          },
          {
            "value": "list_values",
            "label": "list_values"
          },
          {
            "value": "list_keys",
            "label": "list_keys"
          },
        ],
        "name": "process_mode",
        "display_name": "process_mode",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "key": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "key",
        "display_name": "key",
        "type": "str|list",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
      "default_value": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "default_value",
        "display_name": "default_value",
        "type": "str|list",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
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
      }
    }
  }
})

const { t } = useI18n()

const fieldsData = ref(props.data.template)
fieldsData.value.process_mode.options = fieldsData.value.process_mode.options.map(item => {
  item.label = t(`components.nodes.controlFlows.JsonProcess.process_mode_${item.value}`)
  return item
})
</script>

<template>
  <BaseNode :nodeId="id" :title="t('components.nodes.controlFlows.JsonProcess.title')"
    :description="props.data.description" documentLink="https://vectorvein.com/help/docs/control-flows#h2-6">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="input" :name="t('components.nodes.common.input')" required type="target"
            v-model:show="fieldsData.input.show">
            <a-textarea class="field-content" v-model:value="fieldsData.input.value" :autoSize="true" :showCount="true"
              :placeholder="fieldsData.input.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="input" :name="t('components.nodes.controlFlows.JsonProcess.process_mode')" required type="target"
            v-model:show="fieldsData.process_mode.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.process_mode.value"
              :options="fieldsData.process_mode.options" />
          </BaseField>
        </a-col>

        <template v-if="fieldsData.process_mode.value == 'get_value'">
          <a-col :span="24">
            <BaseField id="key" :name="t('components.nodes.controlFlows.JsonProcess.key')" required type="target"
              v-model:show="fieldsData.key.show">
              <a-input class="field-content" v-model:value="fieldsData.key.value"
                :placeholder="fieldsData.key.placeholder" />
            </BaseField>
          </a-col>

          <a-col :span="24">
            <BaseField id="default_value" :name="t('components.nodes.controlFlows.JsonProcess.default_value')"
              type="target" v-model:show="fieldsData.default_value.show">
              <a-input class="field-content" v-model:value="fieldsData.default_value.value"
                :placeholder="fieldsData.default_value.placeholder" />
            </BaseField>
          </a-col>
        </template>
      </a-row>
    </template>
    <template #output>
      <BaseField id="output" :name="t('components.nodes.common.output')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>