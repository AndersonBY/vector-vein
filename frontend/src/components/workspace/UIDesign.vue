<script setup>
import { ref, reactive, nextTick } from 'vue'
import { DirectionAdjustmentThree, Edit, Lightning } from '@icon-park/vue-next'
import { useI18n } from 'vue-i18n'
import { VueDraggable, useDraggable } from 'vue-draggable-plus'
import { getUIDesignFromWorkflow, nonFormItemsTypes } from '@/utils/workflow'
import ListFieldUse from "@/components/workspace/ListFieldUse.vue"
import UploaderFieldUse from "@/components/workspace/UploaderFieldUse.vue"
import TemperatureInput from '@/components/nodes/TemperatureInput.vue'
import TextOutput from "@/components/TextOutput.vue"
import DraggableText from "@/components/workspace/draggableItems/DraggableText.vue"

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
    value: '',
    name: "typography-paragraph",
    display_name: "typography-paragraph",
    type: "str",
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
  <a-layout class="ui-design-layout" has-sider>
    <a-layout-sider class="ui-design-sider custom-scrollbar">
      <a-menu theme="light" mode="inline" ref="siderMenu" class="ui-design-sider-menu">
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
    <a-layout-content class="ui-design-sider-content">
      <a-row :gutter="[16, 16]">
        <a-col :xxl="6" :xl="8" :lg="10" :md="24">
          <a-flex vertical>
            <a-typography-title :level="3">
              <Edit fill="#28c5e5" />
              {{ t('workspace.workflowSpace.inputs') }}
            </a-typography-title>

            <a-form layout="vertical" ref="inputFieldsEl">
              <a-flex align="center" class="draggable-item" v-for="( field, fieldIndex ) in inputFields "
                :key="`field-${field}-${fieldIndex}`">
                <DirectionAdjustmentThree class="handle" />
                <a-form-item class="draggable-item-content" v-if="!nonFormItemsTypes.includes(field.field_type)">
                  <template #label>
                    {{ field.display_name }}
                  </template>
                  <TemperatureInput v-model="field.value" v-if="field.field_type == 'temperature'" />
                  <a-select v-model:value="field.value" :options="field.options"
                    v-else-if="field.field_type == 'select'" />
                  <a-textarea v-model:value="field.value" :autoSize="{ minRows: 2, maxRows: 10 }"
                    :placeholder="field.placeholder" v-else-if="field.field_type == 'textarea'" />
                  <a-input v-model:value="field.value" :placeholder="field.placeholder"
                    v-else-if="field.field_type == 'input'" />
                  <a-input-number v-model:value="field.value" :placeholder="field.placeholder"
                    v-else-if="field.field_type == 'number'" />
                  <a-checkbox v-model:checked="field.value" v-else-if="field.field_type == 'checkbox'" />
                  <UploaderFieldUse v-model="field.value"
                    :supportFileTypes="field.support_file_types || '.docx, .pptx, .xlsx, .pdf, .txt, .md, .html, .json, .csv, .srt, .zip'"
                    v-else-if="field.field_type == 'file'" />
                  <ListFieldUse v-model="field.value" v-else-if="field.field_type == 'list'" />
                </a-form-item>
                <a-row class="draggable-item-content" v-if="field.field_type == 'typography-paragraph'">
                  <a-col :span="24" class="ui-special-item-container">
                    <DraggableText v-model="field.value" :placeholder="field.placeholder" @change="updateWorkflowUi"
                      @delete="deleteField(inputFields, fieldIndex)" />
                  </a-col>
                </a-row>
              </a-flex>
            </a-form>

            <a-divider />

            <a-flex vertical>
              <div v-for="( node ) in triggerNodes" :key="`node-${node.id}`">
                <a-button type="primary" block v-if="node.type == 'ButtonTrigger'">
                  {{ node.data.template.button_text.value }}
                </a-button>
                <div class="special-item-container" v-else-if="node.type == 'ScheduleTrigger'">
                  <a-typography-title :level="4">
                    {{ t('components.nodes.triggers.ScheduleTrigger.title') }}
                  </a-typography-title>
                </div>
              </div>
            </a-flex>
          </a-flex>
        </a-col>

        <a-col :xxl="18" :xl="16" :lg="14" :md="24">
          <a-typography-title :level="3" style="display: flex; justify-content: space-between;">
            <span>
              <Lightning fill="#28c5e5" />
              {{ t('workspace.workflowSpace.outputs') }}
            </span>
          </a-typography-title>

          <a-flex vertical ref="outputNodesEl">
            <a-flex align="center" class="draggable-item" v-for="(node, index) in outputNodes"
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
                    <DraggableText v-model="node.value" :placeholder="node.placeholder" @change="updateWorkflowUi"
                      @delete="deleteField(outputNodes, index)" />
                  </div>
                </div>
              </div>
            </a-flex>
          </a-flex>

        </a-col>
      </a-row>
    </a-layout-content>
  </a-layout>
</template>

<style scoped>
.ui-design-layout {
  height: 100%;
  min-height: calc(100vh - 40px - 40px);
  background-color: #fff;
}

.ui-design-sider {
  overflow: auto;
  background-color: #fff;
  position: fixed;
  min-height: calc(100vh - 40px - 40px);
}

.ui-design-sider-menu {
  padding: 10px;
}

.ui-design-sider-content {
  margin: 0 16px 0 200px;
  overflow: initial;
  background-color: #fff;
  padding: 10px;
}

.ghost {
  opacity: 0.5;
  background: #c8ebfb;
}

.handle {
  cursor: move;
  margin-right: 10px;
}

.draggable-item .handle {
  opacity: 0;
  width: 0;
  transform: translateX(-20px);
  transition: opacity 0.3s ease, transform 0.3s ease, width 0.3s ease;
}

.draggable-item:hover .handle {
  opacity: 1;
  width: 20px;
  transform: translateX(0);
}

.draggable-item .draggable-item-content {
  transition: margin-left 0.3s ease;
}

.draggable-item:hover .draggable-item-content {
  margin-left: 20px;
}

.draggable-item-content {
  flex-grow: 1;
  width: 100%;
}

.ui-special-item-container {
  display: flex;
  align-items: center;
}

.ui-special-item {
  flex-grow: 1;
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