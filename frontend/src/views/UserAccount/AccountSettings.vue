<script setup>
import { defineComponent } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useUserAccountStore } from '@/stores/userAccount'

defineComponent({
  name: 'AccountSettings',
})

const userAccountStore = useUserAccountStore()
const { userAccount } = storeToRefs(userAccountStore)
const { t } = useI18n()
</script>
  
<template>
  <a-row type="flex" justify="center" :gutter="[16, 16]">
    <a-col :xs="24" :lg="12">
      <a-card :title="t('userAccount.accountSettings.account_settings')">
        <a-list item-layout="horizontal">
          <a-list-item>
            <a-typography-text strong>
              {{ t('userAccount.accountSettings.account_email') }}
            </a-typography-text>
            <a-divider type="vertical" />
            <a-typography-text type="secondary">{{ userAccount.email }}</a-typography-text>
          </a-list-item>
        </a-list>
      </a-card>
    </a-col>
  </a-row>
</template>