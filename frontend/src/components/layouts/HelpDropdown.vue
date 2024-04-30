<script setup>
import { ref, reactive, onBeforeMount } from "vue"
import { Help } from '@icon-park/vue-next'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import VueMarkdown from 'vue-markdown-render'
import { useUserSettingsStore } from '@/stores/userSettings'
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

onBeforeMount(() => {
  officialSiteAPI('get_update_info', {}).then(res => {
    if (res.status === 200) {
      updateInfo.updatable = res.data.updatable
      updateInfo.version = res.data.version
      updateInfo.release_date = res.data.release_date
      updateInfo.release_notes = res.data.release_notes
    }
  })
})

const openAboutVectorVein = ref(false)
const openUpdateInfo = ref(false)
</script>

<template>
  <a-sub-menu key="/help" :title="t('components.layout.helpDropdown.help')">
    <template #icon>
      <Help />
    </template>
    <a-menu-item key="document">
      <a href="https://vectorvein.com/help/docs/introduction" target="_blank">
        {{ t('components.layout.helpDropdown.documentation') }}
      </a>
    </a-menu-item>
    <a-menu-item key="/update" v-if="updateInfo.updatable" @click="openUpdateInfo = true">
      {{ t('components.layout.helpDropdown.update_available') }}
      <a-modal
        :title="t('components.layout.helpDropdown.new_version', { version: updateInfo.version, releaseDatetime: new Date(updateInfo.release_date).toLocaleString() })"
        :open="openUpdateInfo" :footer="null" @cancel="openUpdateInfo = false">
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