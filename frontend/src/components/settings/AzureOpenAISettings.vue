<script setup>
import { computed } from "vue"
import { useI18n } from 'vue-i18n'
import { ReduceOne, AddOne } from '@icon-park/vue-next'

const { t } = useI18n()

const azureOpenAISettings = defineModel()

const deleteItem = (index) => {
  azureOpenAISettings.value.endpoints.splice(index, 1)
}
const updateItem = (value, index, key) => {
  azureOpenAISettings.value.endpoints[index][key] = value
}

const endpointOptions = computed(() => {
  return azureOpenAISettings.value.endpoints.map((endpoint, index) => {
    return {
      value: index,
      label: endpoint.api_base
    }
  })
})

const endpointChanged = (value, key) => {
  azureOpenAISettings.value[key].endpoint = azureOpenAISettings.value.endpoints[value]
}
</script>

<template>
  <a-row :gutter="[16, 32]">
    <a-col :span="8" style="text-align: end;">Azure Endpoints</a-col>
    <a-col :span="16">
      <a-flex vertical gap="small">
        <div :key="index" v-for="(endpoint, index) in azureOpenAISettings.endpoints">
          <a-flex gap="small" align="center">
            <a-input :value="endpoint.api_base" placeholder="API Base"
              @input="updateItem($event.target.value, index, 'api_base')" />
            <a-input-password :value="endpoint.api_key" placeholder="API Key"
              @input="updateItem($event.target.value, index, 'api_key')" />
            <a-button type="text" size="small" @click="deleteItem(index)">
              <template #icon>
                <ReduceOne />
              </template>
            </a-button>
          </a-flex>
        </div>
        <div>
          <a-button type="dashed" style="width: 100%;"
            @click="azureOpenAISettings.endpoints.push({ api_base: '', api_key: '' })">
            <template #icon>
              <AddOne />
            </template>
            {{ t('common.add') }}
          </a-button>
        </div>
      </a-flex>
    </a-col>

    <a-col :span="8" style="text-align: end;">Azure gpt-3.5 Deployment</a-col>
    <a-col :span="16">
      <a-flex vertical gap="small">
        <a-input v-model:value="azureOpenAISettings.gpt_35_deployment.id" placeholder="Deployment ID" />
        <a-select v-model:value="azureOpenAISettings.gpt_35_deployment.endpoint_id" :options="endpointOptions"
          style="width: 100%;"
          @change="endpointChanged(azureOpenAISettings.gpt_35_deployment.endpoint_id, 'gpt_35_deployment')" />
      </a-flex>
    </a-col>

    <a-col :span="8" style="text-align: end;">Azure gpt-4 Deployment</a-col>
    <a-col :span="16">
      <a-flex vertical gap="small">
        <a-input v-model:value="azureOpenAISettings.gpt_4_deployment.id" placeholder="Deployment ID" />
        <a-select v-model:value="azureOpenAISettings.gpt_4_deployment.endpoint_id" :options="endpointOptions"
          style="width: 100%;"
          @change="endpointChanged(azureOpenAISettings.gpt_4_deployment.endpoint_id, 'gpt_4_deployment')" />
      </a-flex>
    </a-col>

    <a-col :span="8" style="text-align: end;">Azure gpt-4o Deployment</a-col>
    <a-col :span="16">
      <a-flex vertical gap="small">
        <a-input v-model:value="azureOpenAISettings.gpt_4o_deployment.id" placeholder="Deployment ID" />
        <a-select v-model:value="azureOpenAISettings.gpt_4o_deployment.endpoint_id" :options="endpointOptions"
          style="width: 100%;"
          @change="endpointChanged(azureOpenAISettings.gpt_4o_deployment.endpoint_id, 'gpt_4o_deployment')" />
      </a-flex>
    </a-col>

    <a-col :span="8" style="text-align: end;">Azure gpt-4o-mini Deployment</a-col>
    <a-col :span="16">
      <a-flex vertical gap="small">
        <a-input v-model:value="azureOpenAISettings.gpt_4o_mini_deployment.id" placeholder="Deployment ID" />
        <a-select v-model:value="azureOpenAISettings.gpt_4o_mini_deployment.endpoint_id" :options="endpointOptions"
          style="width: 100%;"
          @change="endpointChanged(azureOpenAISettings.gpt_4o_mini_deployment.endpoint_id, 'gpt_4o_mini_deployment')" />
      </a-flex>
    </a-col>

    <a-col :span="8" style="text-align: end;">Azure gpt-4-vision Deployment</a-col>
    <a-col :span="16">
      <a-flex vertical gap="small">
        <a-input v-model:value="azureOpenAISettings.gpt_4v_deployment.id" placeholder="Deployment ID" />
        <a-select v-model:value="azureOpenAISettings.gpt_4v_deployment.endpoint_id" :options="endpointOptions"
          style="width: 100%;"
          @change="endpointChanged(azureOpenAISettings.gpt_4v_deployment.endpoint_id, 'gpt_4v_deployment')" />
      </a-flex>
    </a-col>

    <a-col :span="8" style="text-align: end;">Azure text-embedding-ada-002 Deployment</a-col>
    <a-col :span="16">
      <a-flex vertical gap="small">
        <a-input v-model:value="azureOpenAISettings.text_embedding_ada_002_deployment.id" placeholder="Deployment ID" />
        <a-select v-model:value="azureOpenAISettings.text_embedding_ada_002_deployment.endpoint_id"
          :options="endpointOptions" style="width: 100%;"
          @change="endpointChanged(azureOpenAISettings.text_embedding_ada_002_deployment.endpoint_id, 'text_embedding_ada_002_deployment')" />
      </a-flex>
    </a-col>

    <a-col :span="8" style="text-align: end;">Azure whisper Deployment</a-col>
    <a-col :span="16">
      <a-flex vertical gap="small">
        <a-input v-model:value="azureOpenAISettings.whisper_deployment.id" placeholder="Deployment ID" />
        <a-select v-model:value="azureOpenAISettings.whisper_deployment.endpoint_id" :options="endpointOptions"
          style="width: 100%;"
          @change="endpointChanged(azureOpenAISettings.whisper_deployment.endpoint_id, 'whisper_deployment')" />
      </a-flex>
    </a-col>

    <a-col :span="8" style="text-align: end;">Azure TTS Deployment</a-col>
    <a-col :span="16">
      <a-flex vertical gap="small">
        <a-input v-model:value="azureOpenAISettings.tts_deployment.id" placeholder="Deployment ID" />
        <a-select v-model:value="azureOpenAISettings.tts_deployment.endpoint_id" :options="endpointOptions"
          style="width: 100%;"
          @change="endpointChanged(azureOpenAISettings.tts_deployment.endpoint_id, 'tts_deployment')" />
      </a-flex>
    </a-col>

    <a-col :span="8" style="text-align: end;">Azure TTS-HD Deployment</a-col>
    <a-col :span="16">
      <a-flex vertical gap="small">
        <a-input v-model:value="azureOpenAISettings.tts_hd_deployment.id" placeholder="Deployment ID" />
        <a-select v-model:value="azureOpenAISettings.tts_hd_deployment.endpoint_id" :options="endpointOptions"
          style="width: 100%;"
          @change="endpointChanged(azureOpenAISettings.tts_hd_deployment.endpoint_id, 'tts_hd_deployment')" />
      </a-flex>
    </a-col>

    <a-col :span="8" style="text-align: end;">Azure DALL·E 3 Deployment</a-col>
    <a-col :span="16">
      <a-flex vertical gap="small">
        <a-input v-model:value="azureOpenAISettings.dalle3_deployment.id" placeholder="Deployment ID" />
        <a-select v-model:value="azureOpenAISettings.dalle3_deployment.endpoint_id" :options="endpointOptions"
          style="width: 100%;"
          @change="endpointChanged(azureOpenAISettings.dalle3_deployment.endpoint_id, 'dalle3_deployment')" />
      </a-flex>
    </a-col>
  </a-row>
</template>