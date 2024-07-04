<script setup>
import { ref, reactive, toRaw } from "vue"
import { useI18n } from 'vue-i18n'
import { Delete } from '@icon-park/vue-next'
import { deepCopy } from '@/utils/util'

const { t } = useI18n()

const ttsSettings = defineModel()

const reechoVoiceEditIndex = ref()
const reechoVoiceFormStatus = ref()
const reechoVoiceFormModalOpen = ref(false)
const reechoVoiceForm = reactive({
  voice_label: '',
  voice_id: '',
})

const reechoVoiceRemove = (index) => {
  ttsSettings.value.reecho.voices.splice(index, 1)
}

const reechoVoiceEdit = (voice, index) => {
  reechoVoiceForm.voice_id = voice.voice_id
  reechoVoiceForm.voice_label = voice.voice_label
  reechoVoiceFormStatus.value = 'edit'
  reechoVoiceEditIndex.value = index
  reechoVoiceFormModalOpen.value = true
}

const reechoVoiceAdd = () => {
  reechoVoiceFormStatus.value = 'add'
  reechoVoiceFormModalOpen.value = true
}

const reechoVoiceSave = () => {
  reechoVoiceFormModalOpen.value = false
  if (reechoVoiceFormStatus.value === 'edit') {
    ttsSettings.value.reecho.voices[reechoVoiceEditIndex.value].voice_label = reechoVoiceForm.voice_label
    ttsSettings.value.reecho.voices[reechoVoiceEditIndex.value].voice_id = reechoVoiceForm.voice_id
  } else {
    ttsSettings.value.reecho.voices.push(deepCopy(toRaw(reechoVoiceForm)))
  }
  reechoVoiceForm.voice_id = ''
  reechoVoiceForm.voice_label = ''
}
</script>

<template>
  <a-tabs tab-position="left">
    <a-tab-pane key="piper" tab="piper">
      <a-flex vertical justify="center" gap="middle">
        <a-alert message="piper-tts deployment" type="info">
          <template #description>
            <a-typography-link style="text-align: center;" target="_blank"
              href="https://github.com/rhasspy/piper/blob/master/src/python_run/README_http.md">
              https://github.com/rhasspy/piper/blob/master/src/python_run/README_http.md
            </a-typography-link>
          </template>
        </a-alert>
        <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
          <a-form-item label="API Base">
            <a-input v-model:value="ttsSettings.piper.api_base" />
          </a-form-item>
        </a-form>
      </a-flex>
    </a-tab-pane>

    <a-tab-pane key="reecho" tab="Reecho.ai">
      <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
        <a-form-item label="API Key">
          <a-input-password v-model:value="ttsSettings.reecho.api_key" />
        </a-form-item>
        <a-form-item :label="t('settings.voices')">
          <a-flex vertical gap="small">
            <a-flex v-for="(voice, index) in ttsSettings.reecho.voices" gap="small" align="center">
              <a-button type="text" block @click="reechoVoiceEdit(voice, index)">
                {{ voice.voice_label }}
              </a-button>
              <a-button type="text" @click="reechoVoiceRemove(index)">
                <template #icon>
                  <Delete fill="#ff4d4f" />
                </template>
              </a-button>
            </a-flex>
            <a-button type="dashed" block @click="reechoVoiceAdd">
              {{ t('common.add') }}
            </a-button>
          </a-flex>
          <a-modal v-model:open="reechoVoiceFormModalOpen" :title="t('common.add')" @ok="reechoVoiceSave">
            <a-form :label-col="{ span: 8 }" :wrapper-col="{ span: 16 }">
              <a-form-item :label="t('settings.voice_label')">
                <a-input v-model:value="reechoVoiceForm.voice_label" />
              </a-form-item>
              <a-form-item :label="t('settings.voice_id')">
                <a-input v-model:value="reechoVoiceForm.voice_id" />
              </a-form-item>
            </a-form>
          </a-modal>
        </a-form-item>
      </a-form>
    </a-tab-pane>
  </a-tabs>
</template>