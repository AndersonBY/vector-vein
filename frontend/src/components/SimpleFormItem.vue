<script setup>
import { Correct, Error } from '@icon-park/vue-next'

const value = defineModel()

const props = defineProps({
  title: {
    type: String,
    default: '',
  },
  description: {
    type: String,
    default: '',
  },
  type: {
    type: String,
    default: 'input',
  },
  options: {
    type: Array,
    default: () => [],
  },
  disabled: {
    type: Boolean,
    default: false,
  },
  layout: {
    type: String,
    default: 'horizontal',
  }
})

const emit = defineEmits(['change'])

const handleChange = (e) => {
  emit('change', e)
}
</script>

<template>
  <a-row class="simple-form-item" :gutter="[16, layout == 'horizontal' ? 16 : 6]">
    <a-col :xs="24" :md="layout == 'horizontal' ? 12 : 24">
      <p class="simple-form-item-title">
        {{ title }}
      </p>
      <p class="simple-form-item-description">
        {{ description }}
      </p>
    </a-col>
    <a-col :xs="24" :md="layout == 'horizontal' ? 12 : 24">
      <slot></slot>
      <a-flex :justify="layout == 'horizontal' ? 'flex-end' : 'flex-start'" align="center" style="height: 100%;">
        <a-input v-if="type === 'input'" v-model:value="value" @change="handleChange" :disabled="disabled" />
        <a-textarea v-else-if="type === 'textarea'" v-model:value="value" :autoSize="{ minRows: 2, maxRows: 6 }"
          @change="handleChange" :disabled="disabled" />
        <a-input-number v-else-if="type === 'input-number'" v-model:value="value" @change="handleChange"
          :disabled="disabled" />
        <template v-else-if="type === 'checkbox' || type === 'switch'">
          <a-switch v-if="!disabled" v-model:checked="value" @change="handleChange" />
          <template v-else>
            <Correct theme="filled" fill="#87d068" v-if="value" />
            <Error theme="filled" fill="#cf1322" v-else />
          </template>
        </template>
        <a-select v-else-if="type === 'select'" v-model:value="value" :options="options" style="width: 100%;"
          @change="handleChange" :disabled="disabled" />
        <a-cascader v-else-if="type === 'cascader'" v-model:value="value" :options="options" style="width: 100%;"
          @change="handleChange" :disabled="disabled" />
      </a-flex>
    </a-col>
  </a-row>
</template>

<style>
.simple-form-item .simple-form-item-title {
  font-size: 20px;
  font-weight: 600;
  margin-bottom: 0;
}

.simple-form-item .simple-form-item-description {
  color: rgb(102, 102, 102);
  margin-bottom: 0;
  margin-top: 6px;
}
</style>