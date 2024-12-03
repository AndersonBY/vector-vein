<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { AddOne, ReduceOne } from '@icon-park/vue-next'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'
import { createTemplateData } from './TextReplace'

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

const addReplaceItem = () => {
  fieldsData.value.replace_items.value.push({ source: '', target: '' })
}

const removeReplaceItem = (index) => {
  fieldsData.value.replace_items.value.splice(index, 1)
}
</script>

<template>
  <BaseNode :nodeId="id" :fieldsData="fieldsData" translatePrefix="components.nodes.textProcessing.TextReplace"
    :debug="props.data.debug" documentPath="/help/docs/text-processing#node-TextReplace">
    <template #main>
      <a-flex vertical gap="small">
        <BaseField :name="t('components.nodes.textProcessing.TextReplace.text')" required type="target"
          v-model:data="fieldsData.text">
          <a-textarea v-model:value="fieldsData.text.value" :autoSize="{ minRows: 2, maxRows: 6 }" :showCount="true"
            :placeholder="fieldsData.text.placeholder" />
        </BaseField>

        <a-tooltip :title="t('components.nodes.textProcessing.TextReplace.replace_tip')" placement="left">
          <div class="replace-items">
            <a-flex vertical gap="small">
              <template v-for="(item, index) in fieldsData.replace_items.value" :key="index">
                <a-flex gap="small" align="center">
                  <a-input v-model:value="item.source" class="replace-item-input"
                    :placeholder="t('components.nodes.textProcessing.TextReplace.source_text')" />
                  <span>→</span>
                  <a-input v-model:value="item.target" class="replace-item-input"
                    :placeholder="t('components.nodes.textProcessing.TextReplace.target_text')" />
                  <a-button type="text" @click="removeReplaceItem(index)" style="flex-shrink: 0;">
                    <template #icon>
                      <ReduceOne />
                    </template>
                  </a-button>
                </a-flex>
              </template>
            </a-flex>

            <a-button type="dashed" block style="margin-top: 8px;" @click="addReplaceItem">
              <template #icon>
                <AddOne />
              </template>
              {{ t('components.nodes.textProcessing.TextReplace.add_replace_item') }}
            </a-button>
          </div>
        </a-tooltip>
      </a-flex>
    </template>
  </BaseNode>
</template>

<style scoped>
.replace-items {
  padding: 10px;
}

.replace-item-input {
  max-width: 105px;
}
</style>