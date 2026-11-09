<script setup>
import { onBeforeMount, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import ShortcutFormItem from '@/components/settings/ShortcutFormItem.vue'

const { t } = useI18n()
const shortcuts = defineModel()
const ensureGlobalShortcuts = () => {
  if (!shortcuts.value.__global__) {
    shortcuts.value.__global__ = {
      open_task_agent: '',
      open_workflow_space: '',
      open_schedule_manager: '',
      open_data_space: '',
    }
  }
}

onBeforeMount(ensureGlobalShortcuts)

watch(shortcuts, (newVal) => {
  const keys = new Set()

  const isConflict = (key1, key2) => {
    return key1 !== key2 && (key1.includes(key2) || key2.includes(key1));
  }

  for (const key in newVal.__global__) {
      const value = newVal.__global__[key];
      if (value) {
        for (const existingKey of keys) {
          if (isConflict(value, existingKey)) {
            message.error(t('settings.shortcut_conflict', { key1: value, key2: existingKey }));
            return;
          }
        }
        keys.add(value);
      }
  }
}, { deep: true })
</script>

<template>
  <a-form v-if="shortcuts.__global__" :label-col="{ span: 12 }" :wrapper-col="{ span: 12 }">
    <ShortcutFormItem :name="t('settings.open_task_agent')" v-model="shortcuts.__global__.open_task_agent" />
    <ShortcutFormItem :name="t('settings.open_workflow_space')" v-model="shortcuts.__global__.open_workflow_space" />
    <ShortcutFormItem :name="t('settings.open_schedule_manager')" v-model="shortcuts.__global__.open_schedule_manager" />
    <ShortcutFormItem :name="t('settings.open_data_space')" v-model="shortcuts.__global__.open_data_space" />
  </a-form>
</template>
