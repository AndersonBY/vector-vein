<script setup>
import { ref, computed } from "vue"
import { useI18n } from 'vue-i18n'
import { useRoute } from "vue-router"
import { ExpandLeft, ExpandRight } from '@icon-park/vue-next'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'

const { t } = useI18n()
const route = useRoute()
const selectedKeys = ref([route.name])
const openKeys = ref([route.name])
const collapsed = ref(false)

const userSettingsStore = useUserSettingsStore()
const { theme } = storeToRefs(userSettingsStore)
const componentTheme = computed(() => theme.value == 'default' ? 'light' : 'dark')
</script>

<template>
  <div class="main-container">
    <a-layout class="layout">
      <a-layout-sider class="layout-sider" width="200" v-model:collapsed="collapsed"
        :style="{ padding: collapsed ? '0' : '8px' }" breakpoint="lg" collapsed-width="0"
        :zeroWidthTriggerStyle="{ background: 'unset', top: 0 }" :theme="componentTheme">
        <template #trigger>
          <a-button type="text" @click="collapsed = !collapsed">
            <template #icon>
              <ExpandLeft v-if="collapsed" />
              <ExpandRight v-else />
            </template>
          </a-button>
        </template>
        <a-menu v-model:selectedKeys="selectedKeys" v-model:openKeys="openKeys" mode="inline" style="height: 100%"
          :theme="componentTheme">
          <a-menu-item key="myAgents" id="my_agents">
            <router-link :to="{ name: 'myAgents' }">
              {{ t('workspace.agentSpace.my_agents') }}
            </router-link>
          </a-menu-item>
          <a-menu-item key="publicAgents" id="public_agents">
            <router-link :to="{ name: 'publicAgents' }">
              {{ t('workspace.agentSpace.public_agents') }}
            </router-link>
          </a-menu-item>
        </a-menu>
      </a-layout-sider>
      <a-layout-content>
        <router-view></router-view>
      </a-layout-content>
    </a-layout>
  </div>
</template>

<style scoped>
.main-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: calc(100vh - 64px);
  height: 100%;
  background-color: var(--component-background);
}

.start-easily-item-col {
  width: 100%;
}

.start-easily-item-card-content {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: flex-end;
}

.layout-sider .ant-menu-inline {
  border-inline-end: 0;
}
</style>
