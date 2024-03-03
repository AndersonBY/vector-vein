<script setup>
import { ref, reactive, nextTick } from 'vue'
import { DirectionAdjustmentThree, Delete, Edit, Lightning } from '@icon-park/vue-next'
import { useI18n } from 'vue-i18n'
import { VueDraggable, useDraggable } from 'vue-draggable-plus'
import { getUIDesignFromWorkflow, nonFormItemsTypes } from '@/utils/workflow'
import ListFieldUse from "@/components/workspace/ListFieldUse.vue"
import UploaderFieldUse from "@/components/workspace/UploaderFieldUse.vue"
import TemperatureInput from '@/components/nodes/TemperatureInput.vue'
import TextOutput from "@/components/TextOutput.vue"

const currentWorkflow = defineModel()
const { t } = useI18n()

const uiDesign = getUIDesignFromWorkflow(currentWorkflow.value)
const reactiveUIDesign = reactive(uiDesign)
const inputFields = ref(reactiveUIDesign.inputFields)
const outputNodes = ref(reactiveUIDesign.outputNodes)
const triggerNodes = ref(reactiveUIDesign.triggerNodes)

const uiItems = ref([
  {
    id: 'typography-paragraph',
    required: true,
    placeholder: t('components.workspace.uiDesign.typography-paragraph.placeholder'),
    show: false,
    multiline: true,
    value: '',
    password: false,
    name: "typography-paragraph",
    display_name: "typography-paragraph",
    type: "str",
    clear_after_run: true,
    list: false,
    field_type: "typography-paragraph"
  }
])

const updateWorkflowUi = () => {
  currentWorkflow.value.data.ui = {
    inputFields: inputFields.value,
    outputNodes: outputNodes.value,
  }
}

const drag = ref(false)
const inputFieldsEl = ref()
const draggableInputOption = reactive({
  animation: 150,
  ghostClass: 'ghost',
  handle: ".handle",
  group: { name: 'fields', pull: false },
  onStart: () => {
    drag.value = true
  },
  onAdd: () => {
    updateWorkflowUi()
  },
  onEnd: () => {
    updateWorkflowUi()
    nextTick(() => {
      drag.value = false
    })
  },
})
useDraggable(inputFieldsEl, inputFields, draggableInputOption)

const outputNodesEl = ref()
const draggableOutputOption = reactive({
  animation: 150,
  ghostClass: 'ghost',
  handle: ".handle",
  group: { name: 'fields', pull: false },
  onStart: () => {
    drag.value = true
  },
  onAdd: () => {
    updateWorkflowUi()
  },
  onEnd: () => {
    updateWorkflowUi()
    nextTick(() => {
      drag.value = false
    })
  },
})
useDraggable(outputNodesEl, outputNodes, draggableOutputOption)

const deleteField = (list, index) => {
  list.splice(index, 1)
  updateWorkflowUi()
}
</script>

<template>
  <a-layout class="ui-design-layout" has-sider style="height: 100%; min-height: calc(100vh - 40px - 40px);">
    <a-layout-sider :style="{ overflow: 'auto', backgroundColor: '#fff' }" class="custom-scrollbar">
      <a-menu theme="light" mode="inline" ref="siderMenu">
        <VueDraggable v-model="uiItems" animation="150" :group="{ name: 'fields', pull: 'clone', put: false }"
          :sort="false">
          <template v-for="(item, nodeIndex) in uiItems" :key="`node-${nodeIndex}`">
            <a-tooltip :title="t(`components.workspace.uiDesign.${item.name}.tip`)" placement="right">
              <a-menu-item class="draggable-menu-item" :id="item.id">
                <DirectionAdjustmentThree />
                <span>{{ t(`components.workspace.uiDesign.${item.name}.title`) }}</span>
              </a-menu-item>
            </a-tooltip>
          </template>
        </VueDraggable>
      </a-menu>
    </a-layout-sider>
    <a-layout style="background-color: #fff;;">
      <a-layout-content :style="{ margin: '24px 16px 0', overflow: 'initial' }">
        <a-row :gutter="[16, 16]">
          <a-col :xxl="6" :xl="8" :lg="10" :md="24">
            <a-row :gutter="[16, 16]">
              <a-typography-title :level="3">
                <Edit fill="#28c5e5" />
                {{ t('workspace.workflowSpace.inputs') }}
              </a-typography-title>

              <a-col :span="24">
                <a-form layout="vertical" ref="inputFieldsEl">
                  <div class="draggable-item" v-for="( field, fieldIndex ) in inputFields "
                    :key="`field-${field}-${fieldIndex}`">
                    <DirectionAdjustmentThree class="handle" />
                    <a-form-item class="draggable-item-content" v-if="!nonFormItemsTypes.includes(field.field_type)">

                      <template #label>
                        {{ field.display_name }}
                      </template>
                      <TemperatureInput v-model="field.value"
                        v-if="field.category == 'llms' && field == 'temperature'" />
                      <a-select v-model:value="field.value" :options="field.options"
                        v-else-if="field.field_type == 'select'" />
                      <a-textarea v-model:value="field.value" :autoSize="true" :showCount="true"
                        :placeholder="field.placeholder" v-else-if="field.field_type == 'textarea'" />
                      <a-input v-model:value="field.value" :placeholder="field.placeholder"
                        v-else-if="field.field_type == 'input'" />
                      <a-input-number v-model:value="field.value" :placeholder="field.placeholder"
                        v-else-if="field.field_type == 'number'" />
                      <a-checkbox v-model:checked="field.value" v-else-if="field.field_type == 'checkbox'" />
                      <UploaderFieldUse v-model="field.value"
                        :supportFileTypes="field.support_file_types || '.docx, .pptx, .xlsx, .pdf, .txt, .md, .html, .json, .csv, .srt'"
                        v-else-if="field.field_type == 'file'" />
                      <ListFieldUse v-model="field.value" v-else-if="field.field_type == 'list'" />
                    </a-form-item>
                    <a-row class="draggable-item-content" v-if="field.field_type == 'typography-paragraph'">
                      <a-col :span="24" class="ui-special-item-container">
                        <a-textarea class="ui-special-item" v-model:value="field.value" :placeholder="field.placeholder"
                          auto-size @change="updateWorkflowUi" />
                        <Delete class="ui-special-item-delete" @click="deleteField(inputFields, fieldIndex)" />
                      </a-col>
                    </a-row>
                  </div>
                </a-form>
              </a-col>

              <a-divider />

              <a-col :span="24">
                <a-row :gutter="[16, 16]">

                  <template v-for="( node ) in triggerNodes" :key="`node-${node.id}`">
                    <a-col :span="24">
                      <a-button type="primary" block v-if="node.type == 'ButtonTrigger'">
                        {{ node.data.template.button_text.value }}
                      </a-button>
                      <div class="special-item-container" v-else-if="node.type == 'ScheduleTrigger'">
                        <a-typography-title :level="4">
                          {{ t('components.nodes.triggers.ScheduleTrigger.title') }}
                        </a-typography-title>
                      </div>
                    </a-col>
                  </template>
                </a-row>
              </a-col>
            </a-row>
          </a-col>

          <a-col :xxl="18" :xl="16" :lg="14" :md="24">
            <a-typography-title :level="3" style="display: flex; justify-content: space-between;">
              <span>
                <Lightning fill="#28c5e5" />
                {{ t('workspace.workflowSpace.outputs') }}
              </span>
            </a-typography-title>

            <a-row :gutter="[16, 16]" ref="outputNodesEl">
              <a-col :span="24" class="draggable-item" v-for="(node, index) in outputNodes"
                :key="`node-${node.id}-${index}`">
                <DirectionAdjustmentThree class="handle" />
                <div class="draggable-item-content">
                  <div v-if="node.type == 'Text'">
                    <a-typography-title :level="5">
                      {{ node.data.template.output_title.value }}
                    </a-typography-title>
                    <TextOutput :text="node.data.template.text.value"
                      :renderMarkdown="node.data.template.render_markdown.value" />
                  </div>

                  <div class="special-item-container" v-else-if="node.type == 'Audio'">
                    <a-typography-title :level="4">
                      {{ t('components.nodes.outputs.Audio.title') }}
                    </a-typography-title>
                  </div>

                  <div class="special-item-container" v-else-if="node.type == 'Mindmap'">
                    <a-typography-title :level="4">
                      {{ t('components.nodes.outputs.Mindmap.title') }}
                    </a-typography-title>
                  </div>

                  <div class="special-item-container" v-else-if="node.type == 'Mermaid'">
                    <a-typography-title :level="4">
                      {{ t('components.nodes.outputs.Mermaid.title') }}
                    </a-typography-title>
                  </div>

                  <div class="special-item-container" v-else-if="node.type == 'Echarts'">
                    <a-typography-title :level="4">
                      {{ t('components.nodes.outputs.Echarts.title') }}
                    </a-typography-title>
                  </div>

                  <div class="special-item-container" v-else-if="node.type == 'Html'">
                    <a-typography-title :level="4">
                      {{ t('components.nodes.outputs.Html.title') }}
                    </a-typography-title>
                  </div>

                  <div v-else>
                    <div class="ui-special-item-container" v-if="node.field_type == 'typography-paragraph'">
                      <a-textarea class="ui-special-item" v-model:value="node.value" :placeholder="node.placeholder"
                        auto-size @change="updateWorkflowUi" />
                      <Delete class="ui-special-item-delete" @click="deleteField(outputNodes, index)" />
                    </div>
                  </div>
                </div>
              </a-col>
            </a-row>

          </a-col>
        </a-row>
      </a-layout-content>
    </a-layout>
  </a-layout>
</template>

<style scoped>
.ghost {
  opacity: 0.5;
  background: #c8ebfb;
}

.draggable-item {
  padding: 10px;
  display: flex;
}

.handle {
  cursor: move;
  margin-right: 10px;
}

.draggable-item-content {
  flex-grow: 1;
}

.ui-special-item-container {
  display: flex;
  align-items: center;
}

.ui-special-item {
  flex-grow: 1;
}

.ui-special-item-delete {
  flex-grow: 0;
  margin-left: 10px;
}

.special-item-container {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 150px;
  background-color: #e7e7e7;
}
</style>

<style>
.ui-design-layout .draggable-menu-item {
  border: 3px dashed #ccc;
  background-color: #b9f3ff3c;
}

.ui-design-layout .ant-menu-item-active.draggable-menu-item:hover {
  background-color: #8ae7faa5 !important;
}
</style>