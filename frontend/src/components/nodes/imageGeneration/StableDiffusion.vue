<script setup>
import { defineComponent, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

defineComponent({
  name: 'StableDiffusion',
})

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
  events: {
    required: false,
  },
  templateData: {
    "description": "description",
    "task_name": "image_generation.stable_diffusion",
    "has_inputs": true,
    "template": {
      "prompt": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "prompt",
        "display_name": "prompt",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "negative_prompt": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "negative_prompt",
        "display_name": "negative_prompt",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "textarea"
      },
      "model": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "stable-diffusion-v1-5",
        "password": false,
        "options": [
          {
            "value": "stable-diffusion-v1-5",
            "label": "stable-diffusion-v1-5"
          },
          {
            "value": "stable-diffusion-512-v2-1",
            "label": "stable-diffusion-512-v2-1"
          },
          {
            "value": "stable-diffusion-768-v2-1",
            "label": "stable-diffusion-768-v2-1"
          },
          {
            "value": "stable-diffusion-xl-beta-v2-2-2",
            "label": "stable-diffusion-xl-beta-v2-2-2"
          },
        ],
        "name": "model",
        "display_name": "model",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "cfg_scale": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": 7,
        "password": false,
        "name": "cfg_scale",
        "display_name": "cfg_scale",
        "type": "float",
        "clear_after_run": true,
        "list": false,
        "field_type": "number"
      },
      "sampler": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "k_dpmpp_2m",
        "password": false,
        "options": [
          {
            "value": "ddim",
            "label": "ddim",
          },
          {
            "value": "plms",
            "label": "plms",
          },
          {
            "value": "k_euler",
            "label": "k_euler",
          },
          {
            "value": "k_euler_ancestral",
            "label": "k_euler_ancestral",
          },
          {
            "value": "k_heun",
            "label": "k_heun",
          },
          {
            "value": "k_dpm_2",
            "label": "k_dpm_2",
          },
          {
            "value": "k_dpm_2_ancestral",
            "label": "k_dpm_2_ancestral",
          },
          {
            "value": "k_dpmpp_2s_ancestral",
            "label": "k_dpmpp_2s_ancestral",
          },
          {
            "value": "k_dpmpp_2m",
            "label": "k_dpmpp_2m",
          },
          {
            "value": "k_dpmpp_sde",
            "label": "k_dpmpp_sde",
          },
        ],
        "name": "sampler",
        "display_name": "sampler",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "width": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": 512,
        "password": false,
        "name": "width",
        "display_name": "width",
        "type": "float",
        "clear_after_run": true,
        "list": false,
        "field_type": "number"
      },
      "height": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": 512,
        "password": false,
        "name": "height",
        "display_name": "height",
        "type": "float",
        "clear_after_run": true,
        "list": false,
        "field_type": "number"
      },
      "output_type": {
        "required": false,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "only_link",
        "password": false,
        "options": [
          {
            "value": "only_link",
            "label": "only_link"
          },
          {
            "value": "markdown",
            "label": "markdown"
          },
          {
            "value": "html",
            "label": "html"
          },
        ],
        "name": "output_type",
        "display_name": "output_type",
        "type": "str",
        "clear_after_run": false,
        "list": true,
        "field_type": "select"
      },
      "output": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": true,
        "value": "",
        "password": false,
        "name": "output",
        "display_name": "output",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": ""
      },
    }
  },
})
const emit = defineEmits(['change', 'delete'])

const { t } = useI18n()

const fieldsData = ref(props.data.template)
fieldsData.value.output_type.options = fieldsData.value.output_type.options.map(item => {
  item.label = t(`components.nodes.imageGeneration.StableDiffusion.output_type_${item.value}`)
  return item
})

const deleteNode = () => {
  props.events.delete({
    id: props.id,
  })
}
</script>

<template>
  <BaseNode :title="t('components.nodes.imageGeneration.StableDiffusion.title')" :description="props.data.description"
    documentLink="https://vectorvein.com/help/docs/image-generation#h2-0" @delete="deleteNode">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="prompt" :name="t('components.nodes.imageGeneration.StableDiffusion.prompt')" required
            type="target" v-model:show="fieldsData.prompt.show">
            <a-textarea class="field-content" v-model:value="fieldsData.prompt.value" :autoSize="true" :showCount="true"
              :placeholder="fieldsData.prompt.placeholder" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="negative_prompt" :name="t('components.nodes.imageGeneration.StableDiffusion.negative_prompt')"
            required type="target" v-model:show="fieldsData.negative_prompt.show">
            <a-textarea class="field-content" v-model:value="fieldsData.negative_prompt.value" :autoSize="true"
              :showCount="true" :placeholder="fieldsData.negative_prompt.placeholder" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="model" :name="t('components.nodes.imageGeneration.StableDiffusion.model')" required type="target"
            v-model:show="fieldsData.model.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.model.value" :options="fieldsData.model.options" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="cfg_scale" :name="t('components.nodes.imageGeneration.StableDiffusion.cfg_scale')" required
            type="target" v-model:show="fieldsData.cfg_scale.show">
            <a-input-number v-model:value="fieldsData.cfg_scale.value" :controls="false" style="width: 100%;" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="sampler" :name="t('components.nodes.imageGeneration.StableDiffusion.sampler')" required
            type="target" v-model:show="fieldsData.sampler.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.sampler.value"
              :options="fieldsData.sampler.options" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="width" :name="t('components.nodes.imageGeneration.StableDiffusion.width')" required type="target"
            v-model:show="fieldsData.width.show">
            <a-input-number v-model:value="fieldsData.width.value" :controls="false" style="width: 100%;" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="height" :name="t('components.nodes.imageGeneration.StableDiffusion.height')" required
            type="target" v-model:show="fieldsData.height.show">
            <a-input-number v-model:value="fieldsData.height.value" :controls="false" style="width: 100%;" />
          </BaseField>
        </a-col>
        <a-col :span="24">
          <BaseField id="output_type" :name="t('components.nodes.imageGeneration.StableDiffusion.output_type')" required
            type="target" v-model:show="fieldsData.output_type.show">
            <a-select style="width: 100%;" v-model:value="fieldsData.output_type.value"
              :options="fieldsData.output_type.options" />
          </BaseField>
        </a-col>
      </a-row>
    </template>
    <template #output>
      <BaseField id="output" :name="t('components.nodes.imageGeneration.StableDiffusion.output')" type="source" nameOnly>
      </BaseField>
    </template>
  </BaseNode>
</template>

<style></style>