<script setup>
import { onBeforeMount, ref, watch } from 'vue'
import { useRoute } from "vue-router"
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'
import {
  ToTop,
  Github,
  Setting,
  ToBottom,
  Translate,
  Communication,
  DatabaseSetting,
  ApplicationMenu,
  WholeSiteAccelerator,
} from '@icon-park/vue-next'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import logoUrl from "@/assets/logo.svg"
import { getPageTitle } from '@/utils/title'
import { languageList } from '@/locales'
import HelpDropdown from '@/components/layouts/HelpDropdown.vue'
import { settingAPI } from '@/api/user'

const loading = ref(true)
const route = useRoute()
const userSettingsStore = useUserSettingsStore()
const { language, setting } = storeToRefs(userSettingsStore)
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

const windowPinned = ref(setting.value.window.on_top)
const toggleWindowPin = async () => {
  windowPinned.value = !windowPinned.value
  const resp = await settingAPI('update_window_setting', { pin_window: windowPinned.value })
  if (resp.status !== 200) {
    message.error(resp.msg)
    windowPinned.value = !windowPinned.value
  }
}
</script>

<template>
  <a-layout-header style="background: #fff;padding: 0 20px;" class="basic-header">
    <a-flex v-if="screenWidth > 960" align="middle" justify="space-between" :gutter="[16, 16]">
      <a-flex>
        <div class="logo">
          <img alt="VectorVein" :src="logoUrl" />
        </div>

        <div :class="['header-button', selectedKeys[0] == 'agent' ? 'active-header-button' : '']">
          <router-link :to="{ name: 'myAgents' }">
            <a-button type="text" id="header-agent-button">
              <template #icon>
                <Communication />
              </template>
              {{ t('components.layout.basicHeader.agent') }}
            </a-button>
          </router-link>
        </div>

        <div :class="['header-button', selectedKeys[0] == 'workflow' ? 'active-header-button' : '']">
          <router-link :to="{ name: 'WorkflowSpaceMain' }">
            <a-button type="text" id="header-workflow-button">
              <template #icon>
                <WholeSiteAccelerator />
              </template>
              {{ t('components.layout.basicHeader.workflow_space') }}
            </a-button>
          </router-link>
        </div>

        <div :class="['header-button', selectedKeys[0] == 'data' ? 'active-header-button' : '']">
          <router-link :to="{ name: 'DataSpaceMain' }">
            <a-button type="text" id="header-data-button">
              <template #icon>
                <DatabaseSetting />
              </template>
              {{ t('components.layout.basicHeader.data_space') }}
            </a-button>
          </router-link>
        </div>
      </a-flex>

      <a-flex align="center">
        <a-menu v-model:selectedKeys="selectedKeys" theme="light" mode="horizontal"
          :style="{ lineHeight: '64px', minWidth: '400px' }" style="border-bottom: none; justify-content: flex-end;">
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
            <router-link :to="{ name: 'settings' }">
              {{ t('components.layout.basicHeader.setting') }}
            </router-link>
          </a-menu-item>

          <HelpDropdown />
        </a-menu>

        <a-tooltip
          :title="!windowPinned ? t('components.layout.basicHeader.pin_window') : t('components.layout.basicHeader.unpin_window')">
          <a-button type="text" @click="toggleWindowPin">
            <template #icon>
              <ToTop v-if="!windowPinned" />
              <ToBottom v-else />
            </template>
          </a-button>
        </a-tooltip>
      </a-flex>

    </a-flex>

    <a-flex v-else style="width: 100%; height: 100%;" justify="space-between" align="center">
      <a-flex gap="small" align="center">
        <div class="logo">
          <img alt="VectorVein" :src="logoUrl" />
        </div>
        <div :class="['header-button', selectedKeys[0] == 'agent' ? 'active-header-button' : '']">
          <router-link :to="{ name: 'myAgents' }">
            <a-tooltip :title="t('components.layout.basicHeader.agent')">
              <a-button type="text" id="header-agent-button">
                <template #icon>
                  <Communication />
                </template>
              </a-button>
            </a-tooltip>
          </router-link>
        </div>
        <div :class="['header-button', selectedKeys[0] == 'workflow' ? 'active-header-button' : '']">
          <router-link :to="{ name: 'WorkflowSpaceMain' }">
            <a-tooltip :title="t('components.layout.basicHeader.workflow_space')">
              <a-button type="text" id="header-workflow-button">
                <template #icon>
                  <WholeSiteAccelerator />
                </template>
              </a-button>
            </a-tooltip>
          </router-link>
        </div>
        <div :class="['header-button', selectedKeys[0] == 'data' ? 'active-header-button' : '']">
          <router-link :to="{ name: 'DataSpaceMain' }">
            <a-tooltip :title="t('components.layout.basicHeader.data_space')">
              <a-button type="text" id="header-data-button">
                <template #icon>
                  <DatabaseSetting />
                </template>
              </a-button>
            </a-tooltip>
          </router-link>
        </div>
      </a-flex>
      <a-flex gap="small">
        <a-dropdown>
          <a-button>
            <ApplicationMenu />
          </a-button>

          <template #overlay>
            <a-menu>
              <a-menu-item key="/agent/my-agents">
                <router-link :to="{ name: 'myAgents' }">
                  <a-button type="link">
                    {{ t('components.layout.basicHeader.agent') }}
                  </a-button>
                </router-link>
              </a-menu-item>
              <a-menu-item key="/workflow">
                <router-link :to="{ name: 'WorkflowSpaceMain' }">
                  <a-button type="link">
                    {{ t('components.layout.basicHeader.workflow_space') }}
                  </a-button>
                </router-link>
              </a-menu-item>
              <a-menu-item key="/data">
                <router-link :to="{ name: 'DataSpaceMain' }">
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
                <router-link :to="{ name: 'settings' }">
                  {{ t('components.layout.basicHeader.setting') }}
                </router-link>
              </a-menu-item>

              <HelpDropdown />
            </a-menu>
          </template>
        </a-dropdown>
        <a-tooltip
          :title="!windowPinned ? t('components.layout.basicHeader.pin_window') : t('components.layout.basicHeader.unpin_window')">
          <a-button type="text" @click="toggleWindowPin">
            <template #icon>
              <ToTop v-if="!windowPinned" />
              <ToBottom v-else />
            </template>
          </a-button>
        </a-tooltip>
      </a-flex>
    </a-flex>
  </a-layout-header>
</template>

<style>
.basic-header {
  position: fixed;
  z-index: 1;
  width: 100%;
  background: #fff;
  box-shadow: 0 2px 10px 0 rgb(0 0 0 / 8%);
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

.header-button {
  position: relative;
}

.active-header-button span {
  color: #28c5e5;
}

.active-header-button::after,
.header-button:hover::after {
  position: absolute;
  inset-inline: 16px;
  bottom: 0;
  border-bottom: 2px solid #28c5e5;
  transition: border-color 0.3s cubic-bezier(0.645, 0.045, 0.355, 1);
  content: "";
}
</style>