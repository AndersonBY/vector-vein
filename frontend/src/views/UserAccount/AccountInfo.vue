<template>
  <a-row type="flex" justify="center" :gutter="[16, 16]">
    <a-col span="12">
      <a-card :title="t('userAccount.accountInfo.my_account')">
        <a-list item-layout="horizontal">
          <a-list-item>
            <div>
              <a-typography-text strong>{{ t('userAccount.accountInfo.my_credits') }}</a-typography-text>
              <a-divider type="vertical" />
              <a-typography-text type="success">{{ userAccount.credits }}</a-typography-text>
            </div>
          </a-list-item>
        </a-list>
      </a-card>
    </a-col>
  </a-row>
</template>

<script setup>
import { defineComponent, reactive } from 'vue'
import { useI18n } from 'vue-i18n'
import { storeToRefs } from 'pinia'
import { useUserAccountStore } from '@/stores/userAccount'

defineComponent({
  name: 'AccountInfo',
})

const userAccountStore = useUserAccountStore()
const { userAccount } = storeToRefs(userAccountStore)
const { t } = useI18n()
</script>
