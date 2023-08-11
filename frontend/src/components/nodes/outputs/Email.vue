<script setup>
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import BaseNode from '@/components/nodes/BaseNode.vue'
import BaseField from '@/components/nodes/BaseField.vue'

const props = defineProps({
  id: {
    type: String,
    required: true,
  },
  data: {
    type: Object,
    required: true,
  },
  templateData: {
    "description": "description",
    "task_name": "output.email",
    "has_inputs": true,
    "template": {
      "to_email": {
        "required": true,
        "placeholder": "",
        "show": true,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "to_email",
        "display_name": "to_email",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
      "subject": {
        "required": true,
        "placeholder": "",
        "show": true,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "subject",
        "display_name": "subject",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
      "content_html": {
        "required": true,
        "placeholder": "",
        "show": false,
        "multiline": false,
        "value": "",
        "password": false,
        "name": "content_html",
        "display_name": "content_html",
        "type": "str",
        "clear_after_run": true,
        "list": false,
        "field_type": "input"
      },
    }
  },
})

const { t } = useI18n()

const fieldsData = ref(props.data.template)
</script>

<template>
  <BaseNode :nodeId="id" :title="t('components.nodes.outputs.Email.title')" :description="props.data.description"
    documentLink="https://vectorvein.com/help/docs/outputs#h2-8">
    <template #main>
      <a-row type="flex">
        <a-col :span="24">
          <BaseField id="to_email" :name="t('components.nodes.outputs.Email.to_email')" required type="target"
            v-model:show="fieldsData.to_email.show">
            <a-input class="field-content" v-model:value="fieldsData.to_email.value"
              :placeholder="fieldsData.to_email.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="subject" :name="t('components.nodes.outputs.Email.subject')" required type="target"
            v-model:show="fieldsData.subject.show">
            <a-input class="field-content" v-model:value="fieldsData.subject.value"
              :placeholder="fieldsData.subject.placeholder" />
          </BaseField>
        </a-col>

        <a-col :span="24">
          <BaseField id="content_html" :name="t('components.nodes.outputs.Email.content_html')" required type="target"
            v-model:show="fieldsData.content_html.show">
            <a-input class="field-content" v-model:value="fieldsData.content_html.value"
              :placeholder="fieldsData.content_html.placeholder" />
          </BaseField>
        </a-col>
      </a-row>
    </template>
  </BaseNode>
</template>

<style></style>