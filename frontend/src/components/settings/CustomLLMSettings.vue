<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { Edit } from '@icon-park/vue-next'
import LLMStandardSettings from "@/components/settings/LLMStandardSettings.vue"

const props = defineProps({
  endpoints: {
    type: Array,
    required: true
  }
})

const localModels = defineModel('localModels')
const modelFamilyMap = defineModel('modelFamilyMap')

const { t } = useI18n()

const selectedModelFamily = ref('')
const modelFamilyName = ref('')
const handleTabChange = (activeKey) => {
  modelFamilyName.value = activeKey;
}
const addNewModelFamily = () => {
  modelFamilyName.value = 'new-model-family'
  modelFamilyMap.value[modelFamilyName.value] = []
  selectedModelFamily.value = modelFamilyName.value
}

function deleteModelFamily() {
  delete modelFamilyMap.value[selectedModelFamily.value]
}

const editModelFamilyNameModalOpen = ref(false)
function familyNameChange() {
  if (modelFamilyMap.value[modelFamilyName.value]) {
    message.error(t('settings.model_family_name_repeat'))
    return
  }
  modelFamilyMap.value[modelFamilyName.value] = modelFamilyMap.value[selectedModelFamily.value]
  delete modelFamilyMap.value[selectedModelFamily.value]
  selectedModelFamily.value = modelFamilyName.value
  editModelFamilyNameModalOpen.value = false
}

function addModel(model) {
  modelFamilyMap.value[selectedModelFamily.value].push(model)
}
</script>

<template>
  <a-flex vertical gap="small">
    <a-flex align="center" justify="space-between">
      <a-button type="dashed" @click="addNewModelFamily">
        {{ t('settings.add_model_family') }}
      </a-button>
      <a-popconfirm :title="t('settings.delete_model_family_confirm', { modelFamily: modelFamilyName })"
        @confirm="deleteModelFamily">
        <a-button danger>
          {{ t('settings.delete_model_family') }}
        </a-button>
      </a-popconfirm>
    </a-flex>
    <a-tabs tab-position="left" v-model:activeKey="selectedModelFamily" @change="handleTabChange">
      <a-tab-pane v-for="[family, models] in Object.entries(modelFamilyMap)" :key="family" :tab="family">
        <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
          <a-form-item>
            <template #label>
              <a-typography-text>
                {{ t('settings.model_family') }}
              </a-typography-text>
            </template>
            <a-flex align="center" gap="small">
              <a-typography-text :content="modelFamilyName" />
              <a-button type="text" @click="editModelFamilyNameModalOpen = true">
                <template #icon>
                  <Edit />
                </template>
              </a-button>
              <a-modal v-model:open="editModelFamilyNameModalOpen" :title="t('settings.edit_model_family_name')"
                @ok="familyNameChange">
                <a-input v-model:value="modelFamilyName" />
              </a-modal>
            </a-flex>
          </a-form-item>
          <LLMStandardSettings v-model="localModels" :filterModels="models" :endpoints="endpoints"
            @addModel="addModel" />
        </a-form>
      </a-tab-pane>
    </a-tabs>
  </a-flex>
</template>
