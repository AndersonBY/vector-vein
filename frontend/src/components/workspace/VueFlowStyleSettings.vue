<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { NodeRound } from '@icon-park/vue-next'

const emit = defineEmits(['save'])

const styleSettings = defineModel()

const { t } = useI18n()
const open = ref(false)

const save = () => {
  emit('save', styleSettings)
  open.value = false
}
</script>

<template>
  <a-tooltip :title="t('components.workspace.vueFlowStyleSettings.title')">
    <a-button type="text" size="large" @click="open = true" class="settings-button">
      <template #icon>
        <NodeRound />
      </template>
    </a-button>
    <a-drawer v-model:open="open" class="custom-class" :title="t('components.workspace.vueFlowStyleSettings.title')"
      placement="right">
      <template #extra>
        <a-button type="primary" @click="save">
          {{ t('common.save') }}
        </a-button>
      </template>
      <a-form :model="styleSettings" :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }" autocomplete="off">
        <a-form-item :label="t('components.workspace.vueFlowStyleSettings.edge_type')" name="edge_type">
          <a-select v-model:value="styleSettings.edge.type">
            <a-select-option value="default">
              {{ t('components.workspace.vueFlowStyleSettings.edge_type_bezier') }}
            </a-select-option>
            <a-select-option value="step">
              {{ t('components.workspace.vueFlowStyleSettings.edge_type_step') }}
            </a-select-option>
            <a-select-option value="smoothstep">
              {{ t('components.workspace.vueFlowStyleSettings.edge_type_smoothstep') }}
            </a-select-option>
            <a-select-option value="straight">
              {{ t('components.workspace.vueFlowStyleSettings.edge_type_straight') }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item :label="t('components.workspace.vueFlowStyleSettings.edge_animated')" name="edge_animated">
          <a-switch v-model:checked="styleSettings.edge.animated" />
        </a-form-item>
      </a-form>
    </a-drawer>
  </a-tooltip>
</template>
