<script setup>
import { computed, ref, watch } from 'vue'
import { AddOne, Delete } from '@icon-park/vue-next'
import { useI18n } from 'vue-i18n'
import { useNodeMessagesStore } from '@/stores/nodeMessages'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import BaseFieldsCollapse from '@/components/nodes/BaseFieldsCollapse.vue'
import { createOutputField, createTemplateData, operatorOptions } from './Conditional'

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

const fieldTypeOptions = computed(() => [
  {
    value: 'string',
    label: t('components.nodes.controlFlows.Conditional.field_type_string'),
  },
  {
    value: 'number',
    label: t('components.nodes.controlFlows.Conditional.field_type_number'),
  },
])

const currentFieldType = computed(() => fieldsData.value.field_type.value || 'string')
const isNumberFieldType = computed(() => currentFieldType.value === 'number')

const branches = computed(() => {
  const branchList = fieldsData.value.branches?.value
  return Array.isArray(branchList) ? branchList : []
})

const defaultValueKey = computed(() => fieldsData.value.default_value_key?.value || 'default_value')
const defaultOutputHandle = computed(() => fieldsData.value.default_output_handle?.value || 'default_output')

const localizedOperatorOptions = computed(() => {
  return operatorOptions
    .filter(item => item.field_type.includes(currentFieldType.value))
    .map(item => ({
      ...item,
      label: t(`components.nodes.controlFlows.Conditional.operator_${item.value}`),
    }))
})

const cloneField = (fieldKey, fieldType = 'input', type = 'str') => {
  if (!fieldsData.value[fieldKey]) {
    fieldsData.value[fieldKey] = {
      required: true,
      placeholder: '',
      show: false,
      value: '',
      name: fieldKey,
      display_name: fieldKey,
      type,
      list: false,
      field_type: fieldType,
    }
  }

  fieldsData.value[fieldKey].name = fieldsData.value[fieldKey].name || fieldKey
  fieldsData.value[fieldKey].display_name = fieldsData.value[fieldKey].display_name || fieldKey
  fieldsData.value[fieldKey].field_type = fieldType
  fieldsData.value[fieldKey].type = type
}

const cloneLegacyValueField = (sourceFieldKey, targetFieldKey, displayName) => {
  if (!fieldsData.value[targetFieldKey]) {
    const sourceField = fieldsData.value[sourceFieldKey]
    fieldsData.value[targetFieldKey] = {
      required: true,
      placeholder: '',
      show: false,
      value: sourceField?.value ?? '',
      name: targetFieldKey,
      display_name: displayName,
      type: 'str',
      list: false,
      field_type: 'input',
    }
  }
}

const ensureOutputField = (fieldKey) => {
  if (!fieldsData.value[fieldKey]) {
    fieldsData.value[fieldKey] = createOutputField(fieldKey)
  }

  fieldsData.value[fieldKey].name = fieldsData.value[fieldKey].name || fieldKey
  fieldsData.value[fieldKey].display_name = fieldsData.value[fieldKey].display_name || fieldKey
  fieldsData.value[fieldKey].is_output = true
  fieldsData.value[fieldKey].field_type = ''
}

const nextCaseIndex = () => {
  const usedKeys = new Set()
  branches.value.forEach(branch => {
    usedKeys.add(branch.right_field_key)
    usedKeys.add(branch.output_value_key)
    usedKeys.add(branch.output_handle)
  })

  let index = 1
  while (usedKeys.has(`case_${index}_right_field`) || usedKeys.has(`case_${index}_value`) || usedKeys.has(`case_${index}_output`)) {
    index += 1
  }
  return index
}

const createBranch = (index = nextCaseIndex()) => {
  return {
    id: `case_${index}`,
    display_name: t('components.nodes.controlFlows.Conditional.case_label', { index }),
    operator: 'equal',
    collapsed: false,
    right_field_key: `case_${index}_right_field`,
    output_value_key: `case_${index}_value`,
    output_handle: `case_${index}_output`,
  }
}

const sanitizeBranch = (branch, index) => {
  const fallbackIndex = index + 1
  const fallbackId = branch?.id || `case_${fallbackIndex}`
  const outputHandle = branch?.output_handle || `${fallbackId}_output`
  const outputFieldBase = outputHandle.endsWith('_output') ? outputHandle.slice(0, -7) : fallbackId

  return {
    id: branch?.id || outputFieldBase,
    display_name: branch?.display_name || t('components.nodes.controlFlows.Conditional.case_label', { index: fallbackIndex }),
    operator: branch?.operator || 'equal',
    collapsed: branch?.collapsed ?? false,
    right_field_key: branch?.right_field_key || `${outputFieldBase}_right_field`,
    output_value_key: branch?.output_value_key || `${outputFieldBase}_value`,
    output_handle: outputHandle,
  }
}

const initializeBranches = () => {
  let branchList = branches.value.map((branch, index) => sanitizeBranch(branch, index))

  if (branchList.length === 0) {
    const hasLegacyHandleSchema = fieldsData.value.true_value
      || fieldsData.value.false_value
      || fieldsData.value.true_output?.is_output
      || fieldsData.value.false_output?.is_output

    const hasLegacyValueSchema = fieldsData.value.operator || fieldsData.value.right_field || fieldsData.value.true_output || fieldsData.value.false_output

    if (hasLegacyHandleSchema) {
      branchList = [
        {
          id: 'legacy_true',
          display_name: t('components.nodes.controlFlows.Conditional.true_output'),
          operator: fieldsData.value.operator?.value || 'equal',
          collapsed: false,
          right_field_key: fieldsData.value.right_field?.name || 'right_field',
          output_value_key: fieldsData.value.true_value?.name || 'true_value',
          output_handle: fieldsData.value.true_output?.name || 'true_output',
        },
      ]
      fieldsData.value.default_value_key.value = fieldsData.value.false_value?.name || 'false_value'
      fieldsData.value.default_output_handle.value = fieldsData.value.false_output?.name || 'false_output'
    } else if (hasLegacyValueSchema) {
      cloneLegacyValueField('true_output', 'true_value', t('components.nodes.controlFlows.Conditional.true_value'))
      cloneLegacyValueField('false_output', 'false_value', t('components.nodes.controlFlows.Conditional.false_value'))
      branchList = [
        {
          id: 'legacy_true',
          display_name: t('components.nodes.controlFlows.Conditional.true_output'),
          operator: fieldsData.value.operator?.value || 'equal',
          collapsed: false,
          right_field_key: fieldsData.value.right_field?.name || 'right_field',
          output_value_key: 'true_value',
          output_handle: 'true_output_handle',
        },
      ]
      fieldsData.value.default_value_key.value = 'false_value'
      fieldsData.value.default_output_handle.value = 'false_output_handle'
    } else {
      branchList = [createBranch(1)]
    }
  }

  fieldsData.value.branches.value = branchList
  fieldsData.value.default_value_key.value = fieldsData.value.default_value_key.value || 'default_value'
  fieldsData.value.default_output_handle.value = fieldsData.value.default_output_handle.value || 'default_output'
  syncBranchFields()
}

const syncBranchFields = () => {
  fieldsData.value.left_field.field_type = isNumberFieldType.value ? 'number' : 'input'
  fieldsData.value.left_field.type = isNumberFieldType.value ? 'float|int' : 'str'

  cloneField(defaultValueKey.value, 'input', 'str')
  ensureOutputField(defaultOutputHandle.value)

  branches.value.forEach(branch => {
    cloneField(branch.right_field_key, isNumberFieldType.value ? 'number' : 'input', isNumberFieldType.value ? 'float|int' : 'str')
    cloneField(branch.output_value_key, 'input', 'str')
    ensureOutputField(branch.output_handle)

    if (!localizedOperatorOptions.value.some(item => item.value === branch.operator)) {
      branch.operator = localizedOperatorOptions.value[0]?.value || 'equal'
    }
  })
}

const addBranch = () => {
  fieldsData.value.branches.value.push(createBranch())
  syncBranchFields()
}

const removeBranch = (index) => {
  if (branches.value.length <= 1) {
    return
  }

  const branch = branches.value[index]
  fieldsData.value.branches.value.splice(index, 1)

  ;[branch.right_field_key, branch.output_value_key, branch.output_handle].forEach(fieldKey => {
    if (!fieldKey) {
      return
    }
    pushMessage('change', {
      event: 'removeField',
      fieldName: fieldKey,
    })
    delete fieldsData.value[fieldKey]
  })
}

const getBranchTitle = (branch, index) => {
  return branch.display_name?.trim() || t('components.nodes.controlFlows.Conditional.case_label', { index: index + 1 })
}

const getBranchOperatorLabel = (branch) => {
  return localizedOperatorOptions.value.find(item => item.value === branch.operator)?.label || branch.operator
}

const getBranchCollapseTitle = (branch, index) => {
  const title = getBranchTitle(branch, index)
  const rightValue = fieldsData.value[branch.right_field_key]?.value

  if (rightValue === '' || rightValue === undefined || rightValue === null) {
    return `${title} · ${getBranchOperatorLabel(branch)}`
  }

  const preview = String(rightValue).length > 20 ? `${String(rightValue).slice(0, 20)}...` : String(rightValue)
  return `${title} · ${getBranchOperatorLabel(branch)} · ${preview}`
}

const onBranchCollapseChanged = (data) => {
  const branch = branches.value.find(item => item.id === data.id)
  if (!branch) {
    return
  }
  branch.collapsed = data.collpased
}

initializeBranches()

watch(() => fieldsData.value.field_type.value, () => {
  syncBranchFields()
})

watch(() => fieldsData.value.branches.value, () => {
  syncBranchFields()
}, { deep: true })
</script>

<template>
  <BaseNode :nodeId="id" :debug="props.data.debug" :data="props.data" :fieldsData="fieldsData"
    translatePrefix="components.nodes.controlFlows.Conditional"
    documentPath="/help/docs/control-flows#node-Conditional">
    <template #main>
      <a-flex vertical gap="small">
        <BaseField :name="t('components.nodes.controlFlows.Conditional.field_type')"
          :required="fieldsData.field_type.required" type="target" v-model:data="fieldsData.field_type">
          <a-select class="nodrag" style="width: 100%;" v-model:value="fieldsData.field_type.value"
            :options="fieldTypeOptions" />
        </BaseField>

        <BaseField :name="t('components.nodes.controlFlows.Conditional.left_field')"
          :required="fieldsData.left_field.required" type="target" v-model:data="fieldsData.left_field">
          <a-input-number v-if="isNumberFieldType" class="nodrag" v-model:value="fieldsData.left_field.value"
            style="width: 100%;" />
          <a-input v-else class="nodrag" v-model:value="fieldsData.left_field.value" />
        </BaseField>

        <div class="conditional-tip">
          <a-typography-text type="secondary">
            {{ t('components.nodes.controlFlows.Conditional.branch_order_tip') }}
          </a-typography-text>
        </div>

        <div v-for="(branch, index) in branches" :key="branch.output_handle" class="branch-card">
          <BaseFieldsCollapse :id="branch.id" :collapse="branch.collapsed"
            :name="getBranchCollapseTitle(branch, index)" @collapseChanged="onBranchCollapseChanged">
            <template #extra>
              <a-button v-if="branches.length > 1" type="text" danger @click.stop="removeBranch(index)">
                <template #icon>
                  <Delete />
                </template>
              </a-button>
            </template>

            <a-form layout="vertical" class="branch-form">
              <a-form-item :label="t('components.nodes.controlFlows.Conditional.case_name')" class="branch-form-item">
                <a-input class="nodrag" v-model:value="branch.display_name"
                  :placeholder="t('components.nodes.controlFlows.Conditional.case_name_placeholder', { index: index + 1 })" />
              </a-form-item>
              <a-form-item :label="t('components.nodes.controlFlows.Conditional.operator')" class="branch-form-item">
                <a-select class="nodrag" style="width: 100%;" v-model:value="branch.operator"
                  :options="localizedOperatorOptions" />
              </a-form-item>
            </a-form>

            <BaseField :name="t('components.nodes.controlFlows.Conditional.right_field')"
              :required="fieldsData[branch.right_field_key].required" type="target"
              v-model:data="fieldsData[branch.right_field_key]">
              <a-input-number v-if="isNumberFieldType" class="nodrag"
                v-model:value="fieldsData[branch.right_field_key].value" style="width: 100%;" />
              <a-input v-else class="nodrag" v-model:value="fieldsData[branch.right_field_key].value" />
            </BaseField>

            <BaseField :name="t('components.nodes.controlFlows.Conditional.case_output_value')"
              :required="fieldsData[branch.output_value_key].required" type="target"
              v-model:data="fieldsData[branch.output_value_key]">
              <a-input class="nodrag" v-model:value="fieldsData[branch.output_value_key].value" />
            </BaseField>
          </BaseFieldsCollapse>
        </div>

        <div class="branch-actions">
          <a-button type="dashed" block @click="addBranch">
            <template #icon>
              <AddOne />
            </template>
            {{ t('components.nodes.controlFlows.Conditional.add_case') }}
          </a-button>
        </div>

        <div class="branch-card default-branch-card">
          <a-typography-text strong>
            {{ t('components.nodes.controlFlows.Conditional.default_output') }}
          </a-typography-text>
          <a-typography-paragraph class="default-branch-tip" type="secondary">
            {{ t('components.nodes.controlFlows.Conditional.default_output_tip') }}
          </a-typography-paragraph>
          <BaseField :name="t('components.nodes.controlFlows.Conditional.default_value')"
            :required="fieldsData[defaultValueKey].required" type="target" v-model:data="fieldsData[defaultValueKey]">
            <a-input class="nodrag" v-model:value="fieldsData[defaultValueKey].value" />
          </BaseField>
        </div>
      </a-flex>
    </template>

    <template #output>
      <a-flex vertical gap="small" style="width: 100%;">
        <BaseField v-for="(branch, index) in branches" :key="branch.output_handle"
          :name="getBranchTitle(branch, index)" type="source" nameOnly v-model:data="fieldsData[branch.output_handle]" />
        <BaseField :name="t('components.nodes.controlFlows.Conditional.default_output')" type="source" nameOnly
          v-model:data="fieldsData[defaultOutputHandle]" />
        <BaseField :name="t('components.nodes.controlFlows.Conditional.output')" type="source" nameOnly
          v-model:data="fieldsData.output" />
      </a-flex>
    </template>
  </BaseNode>
</template>

<style scoped>
.conditional-tip {
  padding: 0 10px;
}

.branch-card {
  margin: 0 10px;
  border: 1px solid #28c5e533;
  border-radius: 10px;
  background: var(--gray-background);
}

.branch-card :deep(.ant-collapse) {
  background: transparent;
  border-radius: 10px;
}

.branch-card :deep(.ant-collapse > .ant-collapse-item) {
  border-bottom: none;
}

.branch-card :deep(.ant-collapse-header) {
  align-items: center !important;
}

.branch-card :deep(.ant-collapse-content-box) {
  padding-top: 4px;
}

.branch-form-item {
  margin-bottom: 12px;
}

.branch-actions {
  padding: 0 10px;
}

.default-branch-card {
  background: var(--component-background);
  border-style: dashed;
}

.default-branch-tip {
  margin: 4px 0 12px;
}
</style>
