<script setup>
import { useI18n } from 'vue-i18n'
import { message } from 'ant-design-vue'

const props = defineProps({
  text: {
    type: String,
    required: false,
    default: '',
  },
  tipText: {
    type: String,
    required: false,
    default: '',
  },
  copyText: {
    type: String,
    required: true,
  },
  block: {
    type: Boolean,
    default: false,
  },
  successMessage: {
    type: String,
    required: false,
    default: '',
  },
  disabled: {
    type: Boolean,
    required: false,
    default: false,
  },
  type: {
    type: String,
    required: false,
    default: 'primary',
  },
})

const { t } = useI18n()
const successMessage = props.successMessage ? props.successMessage : t('components.copyButton.copy_success')
const copyToClipboard = async () => {
  try {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(props.copyText);
      message.success(successMessage);
    } else {
      const textArea = document.createElement('textarea');
      textArea.value = props.copyText;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      message.success(successMessage);
    }
  } catch (err) {
    console.error('Failed to copy: ', err);
  }
}
</script>

<template>
  <a-tooltip :title="tipText || t('components.copyButton.click_to_copy')">
    <a-button :type="type" @click="copyToClipboard" :block="block" :disabled="disabled">
      <template #icon>
        <slot name="icon"></slot>
      </template>
      {{ text }}
    </a-button>
  </a-tooltip>
</template>