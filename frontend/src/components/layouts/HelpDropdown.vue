<script setup>
import { ref, reactive, onBeforeMount } from "vue"
import { Help } from '@icon-park/vue-next'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import VueMarkdown from 'vue-markdown-render'
import { useUserSettingsStore } from '@/stores/userSettings'
import { websiteBase } from '@/utils/common'
import { officialSiteAPI } from '@/api/remote'

const { t } = useI18n()
const userSettingsStore = useUserSettingsStore()
const { language } = storeToRefs(userSettingsStore)
const updateInfo = reactive({
  updatable: false,
  version: '',
  download_url: '',
  release_date: '',
  release_notes: '',
})

onBeforeMount(async () => {
  const res = await officialSiteAPI('get_update_info', {})
  if (res.status === 200) {
    updateInfo.updatable = res.data.updatable
    updateInfo.version = res.data.version
    updateInfo.release_date = res.data.release_date
    updateInfo.release_notes = res.data.release_notes
  }
})

const openAboutVectorVein = ref(false)
const openUpdateInfo = ref(false)
</script>

<template>
  <a-sub-menu key="/help">
    <template #icon>
      <Help />
    </template>
    <template #title>
      {{ t('components.layout.helpDropdown.help') }}
      <a-tag v-if="updateInfo.updatable" color="green" :bordered="false">New</a-tag>
    </template>
    <a-menu-item key="document">
      <a :href="`${websiteBase}/help/docs/introduction`" target="_blank">
        {{ t('components.layout.helpDropdown.documentation') }}
      </a>
    </a-menu-item>
    <a-menu-item key="slack">
      <a href="https://join.slack.com/t/vectorveinhq/shared_invite/zt-1vit9yh0n-CPhrqdA5zZVEHHyW75qkQA" target="_blank">
        Slack
      </a>
    </a-menu-item>
    <a-menu-item key="/update" v-if="updateInfo.updatable" @click="openUpdateInfo = true">
      {{ t('components.layout.helpDropdown.update_available') }}
      <a-modal :open="openUpdateInfo" :footer="null" @cancel="openUpdateInfo = false">
        <template #title>
          <a href="https://github.com/AndersonBY/vector-vein/releases">
            {{ t('components.layout.helpDropdown.new_version', {
              version: updateInfo.version, releaseDatetime: new
                Date(updateInfo.release_date).toLocaleString()
            }) }}
          </a>
        </template>
        <VueMarkdown v-highlight :source="updateInfo.release_notes[language]"
          class="custom-scrollbar markdown-body custom-hljs" />
      </a-modal>
    </a-menu-item>
    <a-menu-item key="/about" @click="openAboutVectorVein = true">
      {{ t('components.layout.helpDropdown.about_vectorvein') }}
      <a-modal :title="t('components.layout.helpDropdown.about_vectorvein')" :open="openAboutVectorVein" :footer="null"
        @cancel="openAboutVectorVein = false">
        <VueMarkdown v-highlight :source="t('components.layout.helpDropdown.about_vectorvein_description')"
          class="custom-scrollbar markdown-body custom-hljs" />
      </a-modal>
    </a-menu-item>
  </a-sub-menu>
</template>