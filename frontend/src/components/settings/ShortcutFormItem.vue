<script setup>
import { ref, onBeforeUnmount } from 'vue'
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import { Setting, CloseOne } from '@icon-park/vue-next'
import { shortcutAPI } from '@/api/user'

const props = defineProps({
  name: {
    type: String,
    required: true,
  },
})

const { t } = useI18n()
const shortcut = defineModel()

const loading = ref(false)

const checkTimer = ref()

const startShortcutSetting = async () => {
  try {
    loading.value = true
    const startResponse = await shortcutAPI('set_setting_mode')
    if (startResponse.status != 200) {
      message.error(t('settings.error_start_shortcut_setting'))
    }
    checkTimer.value = setInterval(async () => {
      const checkResponse = await shortcutAPI('get_setting_mode')
      if (checkResponse.status == 200) {
        clearInterval(checkTimer.value)

        const specialKeys = [];
        const alphaKeys = [];
        for (const key of checkResponse.data) {
          if (key.length === 1) {
            alphaKeys.push(key)
          } else {
            specialKeys.push(`<${key.toLowerCase()}>`)
          }
        }

        specialKeys.sort((a, b) => {
          const specialKeyOrder = ['<cmd>', '<ctrl>', '<alt>', '<shift>']
          const aIndex = specialKeyOrder.indexOf(a)
          const bIndex = specialKeyOrder.indexOf(b)
          if (aIndex === bIndex) {
            return a.localeCompare(b)
          }
          return aIndex - bIndex
        })

        shortcut.value = specialKeys.concat(alphaKeys).join('+')
        loading.value = false
      }
    }, 200)
  } catch (error) {
    console.error(error)
  }
}

onBeforeUnmount(() => {
  clearInterval(checkTimer.value)
})
</script>

<template>
  <a-form-item>
    <template #label>
      <a-typography-text style="text-wrap: wrap;">
        {{ name }}
      </a-typography-text>
    </template>
    <a-flex gap="small" align="center">
      <a-input v-model:value="shortcut"
        :placeholder="loading ? t('settings.waiting_for_combo_key') : t('settings.shortcut_not_set')" disabled>
        <template #suffix>
          <CloseOne theme="filled" @click="shortcut = ''" style="cursor: pointer;" />
        </template>
      </a-input>
      <a-button type="text" :loading="loading" @click="startShortcutSetting">
        <template #icon>
          <Setting />
        </template>
      </a-button>
    </a-flex>
  </a-form-item>
</template>