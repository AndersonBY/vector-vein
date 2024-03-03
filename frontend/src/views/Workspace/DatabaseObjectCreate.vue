<script setup>
import { ref, reactive, onBeforeMount, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import { DocDetail, DatabaseSetting, FileCabinet, Check, Close } from '@icon-park/vue-next'
import UploaderFieldUse from '@/components/workspace/UploaderFieldUse.vue'
import QuestionPopover from '@/components/QuestionPopover.vue'
import { databaseAPI, databaseObjectAPI } from '@/api/database'

const { t } = useI18n()
const loading = ref(true)
const route = useRoute()
const router = useRouter()
const databaseId = route.params.databaseId

const database = ref({})
const objectInfo = reactive({
  add_method: 'url',
  use_oversea_crawler: false,
  source_url: '',
  files: [],
  title: '',
  content: '',
})
const processRules = reactive({
  split_method: 'general',
  chunk_length: 1000,
  delimiter: '\\n',
  remove_url_and_email: false,
})

const currentStep = ref(0)
const steps = ref([
  {
    title: t('workspace.databaseObjectCreate.add_object'),
    content: 'First-content',
  },
  {
    title: t('workspace.databaseObjectCreate.process_rules'),
    content: 'Second-content',
  },
  {
    title: t('workspace.databaseObjectCreate.finish'),
    content: 'Last-content',
  },
])

const nextStepDisabled = computed(() => {
  if (currentStep.value == 0) {
    if (objectInfo.add_method == 'url') {
      return objectInfo.source_url == ''
    } else if (objectInfo.add_method == 'files') {
      return objectInfo.files.length == 0
    } else {
      return objectInfo.title == '' || objectInfo.content == ''
    }
  } else if (currentStep.value == 1) {
  }
})

const getDatabase = async () => {
  const getDatabaseResponse = await databaseAPI('get', { vid: databaseId })
  if (getDatabaseResponse.status == 200) {
    database.value = getDatabaseResponse.data

  } else {
    message.error(getDatabaseResponse.msg)
  }
}

onBeforeMount(async () => {
  loading.value = true
  await getDatabase()
  loading.value = false
})

const creating = ref(false)
const create = async () => {
  if (objectInfo.add_method == 'text' && objectInfo.content.length == 0) {
    message.error(t('workspace.databaseObjectCreate.content_empty'))
    return
  }
  creating.value = true
  const response = await databaseObjectAPI('create', {
    vid: databaseId,
    ...objectInfo,
    process_rules: processRules,
  })
  if (response.status === 200) {
    message.success(t('workspace.databaseObjectCreate.create_success'))
  } else {
    message.error(t('workspace.databaseObjectCreate.create_failed'))
  }
  creating.value = false
  await router.push(`/data/${databaseId}`)
}

</script>

<template>
  <div class="loading-container" v-if="loading">
    <a-spin />
  </div>
  <div class=" dataspace-container" v-else>
    <a-row justify="center" :gutter="[16, 16]">
      <a-col :xl="16" :lg="18" :md="20" :sm="22" :xs="24">
        <a-breadcrumb>
          <a-breadcrumb-item>
            <router-link :to="`/data`">
              <FileCabinet />
              {{ t('components.layout.basicHeader.data_space') }}
            </router-link>
          </a-breadcrumb-item>
          <a-breadcrumb-item>
            <router-link :to="`/data/${database.vid}`">
              <DatabaseSetting />
              {{ database.name }}
            </router-link>
          </a-breadcrumb-item>
          <a-breadcrumb-item>
            {{ t('workspace.databaseObjectCreate.add_object') }}
          </a-breadcrumb-item>
        </a-breadcrumb>
      </a-col>
      <a-col :xl="16" :lg="18" :md="20" :sm="22" :xs="24">
        <a-card :loading="loading">
          <template #title>
            <DocDetail />
            {{ t('workspace.databaseObjectCreate.add_object') }}
          </template>

          <a-steps :current="currentStep" :items="steps" style="margin-bottom: 30px;"></a-steps>

          <a-form :label-col="{ span: 6 }" v-if="currentStep == 0">
            <a-form-item :label="t('workspace.databaseObjectCreate.add_method')">
              <a-radio-group v-model:value="objectInfo.add_method">
                <a-radio-button value="url">
                  {{ t('workspace.databaseObjectCreate.add_method_url') }}
                </a-radio-button>
                <a-radio-button value="files">
                  {{ t('workspace.databaseObjectCreate.add_method_files') }}
                </a-radio-button>
                <a-radio-button value="text">
                  {{ t('workspace.databaseObjectCreate.add_method_text') }}
                </a-radio-button>
              </a-radio-group>
            </a-form-item>

            <template v-if="objectInfo.add_method == 'url'">
              <a-form-item :label="t('workspace.databaseObjectCreate.use_oversea_crawler')"
                v-if="objectInfo.add_method == 'url'">
                <a-checkbox v-model:checked="objectInfo.use_oversea_crawler" />
              </a-form-item>
              <a-form-item :label="t('workspace.databaseObjectCreate.object_source_url')">
                <a-input v-model:value="objectInfo.source_url" />
              </a-form-item>
            </template>

            <template v-if="objectInfo.add_method == 'files'">
              <UploaderFieldUse v-model="objectInfo.files" :multiple="true" style="margin-bottom: 30px;" />
            </template>

            <template v-if="objectInfo.add_method == 'text'">
              <a-form-item :label="t('workspace.databaseObjectCreate.object_title')">
                <a-input v-model:value="objectInfo.title" />
              </a-form-item>
              <a-form-item :label="t('workspace.databaseObjectCreate.object_content')">
                <a-textarea v-model:value="objectInfo.content" :auto-size="true" :show-count="true" />
              </a-form-item>
            </template>
          </a-form>

          <a-form :label-col="{ span: 6 }" v-if="currentStep == 1">
            <a-form-item :label="t('workspace.databaseObjectCreate.split_method')">
              <a-radio-group v-model:value="processRules.split_method">
                <a-radio-button value="general">
                  {{ t('workspace.databaseObjectCreate.split_method_general') }}
                </a-radio-button>
                <a-radio-button value="delimeter">
                  {{ t('workspace.databaseObjectCreate.split_method_delimeter') }}
                </a-radio-button>
                <a-radio-button value="markdown">
                  {{ t('workspace.databaseObjectCreate.split_method_markdown') }}
                </a-radio-button>
                <a-radio-button value="table">
                  {{ t('workspace.databaseObjectCreate.split_method_table') }}
                </a-radio-button>
              </a-radio-group>
            </a-form-item>

            <a-form-item v-if="!['delimeter', 'table'].includes(processRules.split_method)">

              <template #label>
                {{ t('workspace.databaseObjectCreate.chunk_length') }}
                <QuestionPopover :contents="[
    t('workspace.databaseObjectCreate.question.chunk_length.1'),
    t('workspace.databaseObjectCreate.question.chunk_length.2'),
    t('workspace.databaseObjectCreate.question.chunk_length.3')
  ]" />
              </template>
              <a-input-number v-model:value="processRules.chunk_length" />
            </a-form-item>

            <a-form-item :label="t('workspace.databaseObjectCreate.delimiter')"
              v-if="processRules.split_method == 'delimeter'">
              <a-input v-model:value="processRules.delimiter" style="width: 200px;" />
            </a-form-item>

            <a-form-item :label="t('workspace.databaseObjectCreate.remove_url_and_email')">
              <a-checkbox v-model:checked="processRules.remove_url_and_email">
              </a-checkbox>
            </a-form-item>
          </a-form>

          <a-row align="center" :gutter="[16, 16]">
            <a-col :xl="16" :md="24">
              <a-descriptions bordered v-if="currentStep == 2">
                <a-descriptions-item :label="t('workspace.databaseObjectCreate.add_method')" :span="3">
                  {{ t(`workspace.databaseObjectCreate.add_method_${objectInfo.add_method}`) }}
                </a-descriptions-item>

                <a-descriptions-item :label="t('workspace.databaseObjectCreate.object_source_url')" :span="3"
                  v-if="objectInfo.add_method == 'url'">
                  <a href="objectInfo.source_url" target="_blank">{{ objectInfo.source_url }}</a>
                </a-descriptions-item>

                <a-descriptions-item :label="t('workspace.databaseObjectCreate.object_files')" :span="3"
                  v-if="objectInfo.add_method == 'files'">
                  <a-list :dataSource="objectInfo.files">

                    <template #renderItem="{ item }">
                      <a-list-item>
                        <a-list-item-meta :title="item" />
                      </a-list-item>
                    </template>
                  </a-list>
                </a-descriptions-item>

                <a-descriptions-item :label="t('workspace.databaseObjectCreate.object_title')" :span="1"
                  v-if="objectInfo.add_method == 'text'">
                  {{ objectInfo.title }}
                </a-descriptions-item>
                <a-descriptions-item :label="t('workspace.databaseObjectCreate.object_content')" :span="2"
                  v-if="objectInfo.add_method == 'text'">
                  {{ objectInfo.content }}
                </a-descriptions-item>

                <a-descriptions-item :label="t('workspace.databaseObjectCreate.split_method')">
                  {{ t(`workspace.databaseObjectCreate.split_method_${processRules.split_method}`) }}
                </a-descriptions-item>
                <a-descriptions-item :label="t('workspace.databaseObjectCreate.chunk_length')"
                  v-if="processRules.split_method != 'delimeter'">
                  {{ processRules.chunk_length }}
                </a-descriptions-item>
                <a-descriptions-item :label="t('workspace.databaseObjectCreate.delimiter')"
                  v-if="processRules.split_method == 'delimeter'">
                  {{ processRules.delimiter }}
                </a-descriptions-item>
                <a-descriptions-item :label="t('workspace.databaseObjectCreate.remove_url_and_email')">
                  <Check v-if="processRules.remove_url_and_email" />
                  <Close v-else />
                </a-descriptions-item>

              </a-descriptions>
            </a-col>
          </a-row>

          <a-space style="float: right;">
            <a-button :disabled="currentStep == 0" @click="currentStep -= 1">
              {{ t('common.previous_step') }}
            </a-button>
            <a-button type="primary" :disabled="nextStepDisabled" @click="currentStep += 1" v-if="currentStep < 2">
              {{ t('common.next_step') }}
            </a-button>
            <a-button type="primary" :loading="creating" @click="create" v-if="currentStep == 2">
              {{ t('workspace.databaseObjectCreate.finish') }}
            </a-button>
          </a-space>

        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<style scoped>
.loading-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 80vh;
}

.dataspace-container {
  padding: 16px;
}
</style>