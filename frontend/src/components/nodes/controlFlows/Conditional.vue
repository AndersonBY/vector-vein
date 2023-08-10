<script setup>
import { defineComponent, ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'Conditional',
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
    "task_name": "control_flows.conditional",
    "has_inputs": true,
    "template": {
      "field_type": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "string",
        "password": false,
        "options": [
          {
            "value": "string",
            "label": "Str"
          },
          {
            "value": "number",
            "label": "Number"
          },
        ],
        "name": "field_type",
        "display_name": "field_type",
        "type": "str",
        "clear_after_run": true,
        "list": true,
        "field_type": "select"
      },
      "left_field": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "left_field",
        "display_name": "left_field",
        "type": "str|float|int",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
      "right_field": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "right_field",
        "display_name": "right_field",
        "type": "str|float|int",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
      "operator": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "equal",
        "password": false,
        "options": [
          {
            "value": "equal",
            "label": "equal",
            "field_type": ["string", "number"]
          },
          {
            "value": "not_equal",
            "label": "not_equal",
            "field_type": ["string", "number"]
          },
          {
            "value": "greater_than",
            "label": "greater_than",
            "field_type": ["number"]
          },
          {
            "value": "less_than",
            "label": "less_than",
            "field_type": ["number"]
          },
          {
            "value": "greater_than_or_equal",
            "label": "greater_than_or_equal",
            "field_type": ["number"]
          },
          {
            "value": "less_than_or_equal",
            "label": "less_than_or_equal",
            "field_type": ["number"]
          },
          {
            "value": "include",
            "label": "include",
            "field_type": ["string"]
          },
          {
            "value": "not_include",
            "label": "not_include",
            "field_type": ["string"]
          },
          {
            "value": "is_empty",
            "label": "is_empty",
            "field_type": ["string"]
          },
          {
            "value": "is_not_empty",
            "label": "is_not_empty",
            "field_type": ["string"]
          },
          {
            "value": "starts_with",
            "label": "starts_with",
            "field_type": ["string"]
          },
          {
            "value": "ends_with",
            "label": "ends_with",
            "field_type": ["string"]
          },
        ],
        "name": "operator",
        "display_name": "operator",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
      "true_output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "true_output",
        "display_name": "true_output",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": ""
      },
      "false_output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "false_output",
        "display_name": "false_output",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": ""
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
    }
  }
})
const emit = defineEmits(['change', 'delete'])

const { t } = useI18n()

const fieldsData = ref(props.data.template)
fieldsData.value.field_type.options = fieldsData.value.field_type.options.map(item => {
  item.label = t(`components.nodes.controlFlows.Conditional.field_type_${item.value}`)
  return item
})
fieldsData.value.operator.options = fieldsData.value.operator.options.map(item => {
  item.label = t(`components.nodes.controlFlows.Conditional.operator_${item.value}`)
  return item
})
const operatorOptions = computed(() => {
  if (fieldsData.value.field_type.value === 'number') {
    return fieldsData.value.operator.options.filter(item => item.field_type.includes('number'))
  } else if (fieldsData.value.field_type.value === 'string') {
    return fieldsData.value.operator.options.filter(item => item.field_type.includes('string'))
  } else {
    return fieldsData.value.operator.options
  }
})

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}
</script>

<template>
  <BaseNode :title="t('components.nodes.controlFlows.Conditional.title')" :description="props.data.description" documentLink="https://vectorvein.com/help/docs/control-flows#h2-0"
    @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="field_type" :name="t('components.nodes.controlFlows.Conditional.field_type')" required
            type="target" v-model:show="fieldsData.field_type.show">
            <a-select style="width: 100%;" class="field-content" v-model:value="fieldsData.field_type.value"
              :options="fieldsData.field_type.options" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="left_field" :name="t('components.nodes.controlFlows.Conditional.left_field')" required
            type="target" v-model:show="fieldsData.left_field.show">
            <a-input class="field-content" v-model:value="fieldsData.left_field.value"
              :placeholder="fieldsData.left_field.placeholder" v-if="fieldsData.field_type.value == 'string'" />
            <a-input-number style="width: 100%;" class="field-content" v-model:value="fieldsData.left_field.value"
              :placeholder="fieldsData.left_field.placeholder" v-if="fieldsData.field_type.value == 'number'" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="operator" :name="t('components.nodes.controlFlows.Conditional.operator')" required type="target"
            v-model:show="fieldsData.operator.show">
            <a-select style="width: 100%;" class="field-content" v-model:value="fieldsData.operator.value"
              :options="operatorOptions" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="right_field" :name="t('components.nodes.controlFlows.Conditional.right_field')" required
            type="target" v-model:show="fieldsData.right_field.show">
            <a-input class="field-content" v-model:value="fieldsData.right_field.value"
              :placeholder="fieldsData.right_field.placeholder" v-if="fieldsData.field_type.value == 'string'" />
            <a-input-number style="width: 100%;" class="field-content" v-model:value="fieldsData.right_field.value"
              :placeholder="fieldsData.right_field.placeholder" v-if="fieldsData.field_type.value == 'number'" />
          </BaseField>
        </a-col>

        <a-divider></a-divider>

        <a-col :span="24">
          <BaseField id="true_output" :name="t('components.nodes.controlFlows.Conditional.true_output')" required
            type="target" v-model:show="fieldsData.true_output.show">
            <a-input class="field-content" v-model:value="fieldsData.true_output.value"
              :placeholder="fieldsData.true_output.placeholder" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="false_output" :name="t('components.nodes.controlFlows.Conditional.false_output')" required
            type="target" v-model:show="fieldsData.false_output.show">
            <a-input class="field-content" v-model:value="fieldsData.false_output.value"
              :placeholder="fieldsData.false_output.placeholder" />
          </BaseField>
        </a-col>
      </a-row>
    </template>
    <template #output>
      <BaseField id="output" :name="t('components.nodes.controlFlows.Conditional.output')" type="source">
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>