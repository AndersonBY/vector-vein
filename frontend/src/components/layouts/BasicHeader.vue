<script setup>
import { onBeforeMount, ref, watch, h } from 'vue'
import { useRoute } from "vue-router"
import { useI18n } from 'vue-i18n'
import {
  Setting,
  WholeSiteAccelerator,
  DatabaseSetting,
  Translate,
  Down,
  ApplicationMenu,
  Help,
  Github,
} from '@icon-park/vue-next'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import logoUrl from "@/assets/logo.svg"
import { getPageTitle } from '@/utils/title'
import { languageList } from '@/locales'
import HelpDropdown from '@/components/layouts/HelpDropdown.vue'

const loading = ref(true)
const route = useRoute()
const userSettingsStore = useUserSettingsStore()
const { language } = storeToRefs(userSettingsStore)
const { locale, t, te } = useI18n({ useScope: "global" })

const selectedKeys = ref([route.meta?.headerKey || route.path])
watch(route, (route) => {
  selectedKeys.value = [route.meta?.headerKey || route.path]
})

const handleLanguageChange = async (value) => {
  userSettingsStore.setLanguage(value)
  locale.value = value
  document.title = getPageTitle(te, t, route.meta.title)
}

const screenWidth = ref(window.innerWidth)

onBeforeMount(() => {
  loading.value = false
  window.addEventListener("resize", () => {
    screenWidth.value = window.innerWidth
  })
})

const settingOpen = ref(false)
</script>

<template>
  <a-layout-header style="background: #fff; width: 100%;padding: 0 50px;box-shadow: 0 2px 10px 0 rgb(0 0 0 / 8%);"
    class="basic-header">
    <a-flex v-if="screenWidth > 960" align="middle" justify="space-between" :gutter="[16, 16]">
      <a-flex>
        <div class="logo">
          <img alt="VectorVein" :src="logoUrl" />
        </div>

        <div :class="['header-button', selectedKeys[0] == 'workflow' ? 'active-header-button' : '']">
          <router-link to="/workflow">
            <a-button type="text" id="header-workflow-button">
              <template #icon>
                <WholeSiteAccelerator />
              </template>
              {{ t('components.layout.basicHeader.workflow_space') }}
            </a-button>
          </router-link>
        </div>

        <div :class="['header-button', selectedKeys[0] == 'data' ? 'active-header-button' : '']">
          <router-link to="/data">
            <a-button type="text" id="header-data-button">
              <template #icon>
                <DatabaseSetting />
              </template>
              {{ t('components.layout.basicHeader.data_space') }}
            </a-button>
          </router-link>
        </div>
      </a-flex>

      <a-menu v-model:selectedKeys="selectedKeys" theme="light" mode="horizontal"
        :style="{ lineHeight: '64px', minWidth: '340px' }" style="border-bottom: none; justify-content: flex-end;">
        <a-menu-item key="github" title="Github">
          <template #icon>
            <a-tooltip :title="t('components.layout.basicHeader.opensource_code')">
              <a href="https://github.com/AndersonBY/vector-vein" target="_blank">
                <Github />
              </a>
            </a-tooltip>
          </template>
        </a-menu-item>

        <a-sub-menu key="/language" :title="languageList[language]">
          <template #icon>
            <Translate />
          </template>
          <a-menu-item @click="handleLanguageChange(value)" v-for="(value) in Object.keys(languageList)" :key="value">
            {{ languageList[value] }}
          </a-menu-item>
        </a-sub-menu>

        <a-menu-item key="setting" @click="settingOpen = true">
          <template #icon>
            <Setting />
          </template>
          <router-link to="/settings">
            {{ t('components.layout.basicHeader.setting') }}
          </router-link>
        </a-menu-item>

        <HelpDropdown />
      </a-menu>

    </a-flex>

    <a-row style="width: 100%;" justify="space-between" v-else>
      <a-col>
        <img alt="VectorVein" :src="logoUrl" />
      </a-col>
      <a-col>
        <a-dropdown>
          <a-button>
            <ApplicationMenu />
          </a-button>

          <template #overlay>
            <a-menu>
              <a-menu-item key="/workflow">
                <router-link to="/workflow">
                  <a-button type="link">
                    {{ t('components.layout.basicHeader.workflow_space') }}
                  </a-button>
                </router-link>
              </a-menu-item>
              <a-menu-item key="/data">
                <router-link to="/data">
                  <a-button type="link">
                    {{ t('components.layout.basicHeader.data_space') }}
                  </a-button>
                </router-link>
              </a-menu-item>
              <a-sub-menu key="/language" :title="languageList[language]">
                <template #icon>
                  <Translate />
                </template>
                <a-menu-item @click="handleLanguageChange(value)" v-for="(value) in Object.keys(languageList)"
                  :key="value">
                  {{ languageList[value] }}
                </a-menu-item>
              </a-sub-menu>

              <a-menu-item key="setting" @click="settingOpen = true">
                <template #icon>
                  <Setting />
                </template>
                <router-link to="/settings">
                  {{ t('components.layout.basicHeader.setting') }}
                </router-link>
              </a-menu-item>

              <HelpDropdown />
            </a-menu>
          </template>
        </a-dropdown>
      </a-col>
    </a-row>
  </a-layout-header>
</template>

<style>
.basic-header {
  position: fixed;
  z-index: 1;
  width: 100%;
}

.logo {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

.logo img {
  height: 30px;
}
</style>