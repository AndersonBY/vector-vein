<script setup>
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { theme, Tooltip } from 'ant-design-vue'
import { Check, CloseSmall, Help } from '@/icons'
import { useUserSettingsStore } from '@/stores/userSettings'
import { resolveModelCapabilities } from '@/utils/modelCapabilities'

const props = defineProps({
  provider: { type: String, default: '' },
  model: { type: String, default: '' },
})
const { t } = useI18n()
const { token } = theme.useToken()
const settings = useUserSettingsStore()
const capabilities = computed(() => resolveModelCapabilities(
  settings.setting.data?.llm_settings?.backends, props.provider, props.model,
))
const featureKeys = ['native_multimodal', 'function_call_available', 'response_format_available']
const limitKeys = ['context_length', 'max_output_tokens']
const status = value => t(`modelCapabilities.${value === null ? 'unknown' : value ? 'yes' : 'no'}`)
const featureDescription = key => {
  const description = `${t(`modelCapabilities.${key}`)}：${status(capabilities.value[key])}`
  return key === 'function_call_available' && capabilities.value[key] === false
    ? `${description}。${t('modelCapabilities.tools_hint')}` : description
}
</script>

<template>
  <section class="model-capabilities" :aria-label="t('modelCapabilities.title')" :style="{
    '--capability-text': token.colorText,
    '--capability-secondary': token.colorTextSecondary,
    '--capability-border': token.colorBorderSecondary,
    '--capability-accent': token.colorPrimaryText,
  }">
    <ul class="features">
      <li v-for="key in featureKeys" :key="key">
        <Tooltip :title="featureDescription(key)">
          <span class="feature" :class="{ supported: capabilities[key] === true }" tabindex="0"
            :aria-label="featureDescription(key)">
            <Check v-if="capabilities[key] === true" :size="16" aria-hidden="true" />
            <CloseSmall v-else-if="capabilities[key] === false" :size="16" aria-hidden="true" />
            <Help v-else :size="16" aria-hidden="true" />
            {{ t(`modelCapabilities.${key}`) }}
          </span>
        </Tooltip>
      </li>
    </ul>
    <dl class="limits">
      <div v-for="key in limitKeys" :key="key">
        <dt>{{ t(`modelCapabilities.${key}`) }}</dt>
        <dd>{{ capabilities[key]?.toLocaleString() ?? t('modelCapabilities.unknown') }}
          <span v-if="capabilities[key] !== null" class="unit">tokens</span>
        </dd>
      </div>
    </dl>
  </section>
</template>

<style scoped>
.model-capabilities {
  margin-top: 16px;
  padding: 16px 0 4px;
  border-top: 1px solid var(--capability-border);
  color: var(--capability-text);
  font-size: 14px;
  line-height: 1.6;
}
.features { display: flex; flex-wrap: wrap; gap: 8px 24px; margin: 0; padding: 0; list-style: none; }
.feature { display: inline-flex; align-items: center; gap: 6px; color: var(--capability-secondary); }
.feature.supported { color: var(--capability-text); }
.feature.supported :deep(.vv-icon) { color: var(--capability-accent); }
.feature:focus-visible { outline: 2px solid var(--capability-accent); outline-offset: 4px; border-radius: 2px; }
.limits { display: flex; flex-wrap: wrap; gap: 8px 28px; margin: 12px 0 0; }
.limits > div { display: flex; align-items: baseline; gap: 10px; }
dt, .unit { color: var(--capability-secondary); font-size: 13px; }
dd { margin: 0; font-weight: 500; font-variant-numeric: tabular-nums; }
.unit { margin-left: 3px; font-weight: 400; }
</style>
