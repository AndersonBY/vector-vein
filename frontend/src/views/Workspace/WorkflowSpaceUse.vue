<script setup>
import { onBeforeMount, defineComponent, ref, computed } from "vue"
import { useI18n } from 'vue-i18n'
import { useRoute, useRouter } from "vue-router"
import { message } from 'ant-design-vue'
import VueMarkdown from 'vue-markdown-render'
import { storeToRefs } from 'pinia'
import { useUserSettingsStore } from '@/stores/userSettings'
import { useUserWorkflowsStore } from "@/stores/userWorkflows"
import { useUserDatabasesStore } from "@/stores/userDatabase"
import WorkflowEditor from '@/components/workspace/WorkflowEditor.vue'
import ListFieldUse from "@/components/workspace/ListFieldUse.vue"
import UploaderFieldUse from "@/components/workspace/UploaderFieldUse.vue"
import AudioPlayer from "@/components/workspace/AudioPlayer.vue"
import MindmapRenderer from "@/components/workspace/MindmapRenderer.vue"
import TemperatureInput from '@/components/nodes/TemperatureInput.vue'
import WorkflowRunRecordsDrawer from "@/components/workspace/WorkflowRunRecordsDrawer.vue"
import { workflowAPI, workflowScheduleTriggerAPI } from "@/api/workflow"
import { databaseAPI } from "@/api/database"

defineComponent({
  name: 'WorkflowSpace',
})

const { t } = useI18n()
const userSettingsStore = useUserSettingsStore()
const { language, setting } = storeToRefs(userSettingsStore)
const userDatabasesStore = useUserDatabasesStore()
const { userDatabases } = storeToRefs(userDatabasesStore)
const loading = ref(true)
const updating = ref(false)
const userWorkflowsStore = useUserWorkflowsStore()
const route = useRoute()
const router = useRouter()
const workflowId = route.params.workflowId
const briefModalOpen = ref(false)
const briefModalWidth = ref(window.innerWidth <= 768 ? '90vw' : '60vw')

onBeforeMount(async () => {
  const getWorkflowRequest = workflowAPI('get', { wid: workflowId })
  const listDatabasesRequest = databaseAPI('list', {})
  const workflowResponse = await getWorkflowRequest
  const listDatabasesResponse = await listDatabasesRequest
  if (listDatabasesResponse.status == 200) {
    userDatabasesStore.setUserDatabases(listDatabasesResponse.data)
  }
  if (workflowResponse.status != 200) {
    message.error(t('workspace.workflowSpace.get_workflow_failed'))
    router.push({ name: 'WorkflowSpaceMain' })
    return
  }
  currentWorkflow.value = workflowResponse.data
  currentWorkflow.value.data.nodes.forEach((node) => {
    if (node.category == "vectorDb") {
      node.data.template.database.options = userDatabases.value.filter((database) => {
        return database.status == 'VALID'
      }).map((item) => {
        return {
          value: item.vid,
          label: item.name,
        }
      })
    }
  })
  loading.value = false
})

const clearNodesFiles = () => {
  currentWorkflow.value.data.nodes.forEach((node) => {
    if (node.data.has_inputs) {
      Object.keys(node.data.template).forEach((field) => {
        if (node.data.template[field].field_type == 'file') {
          node.data.template[field].value = []
        }
      })
    }
  })
}

const currentWorkflow = ref({})

const running = ref(false)
const checkStatusTimer = ref(null)
const runRecordId = ref(null)
const runWorkflow = async () => {
  showingRecord.value = false
  let checkFieldsValid = true
  try {
    currentWorkflow.value.data.nodes.forEach((node) => {
      if (node.data.has_inputs && hasShowFields(node) && !['triggers'].includes(node.category)) {
        Object.keys(node.data.template).forEach((field) => {
          if (node.data.template[field].field_type == 'checkbox') {
            return
          }
          if (node.data.template[field].show && node.data.template[field].required && !node.data.template[field].value) {
            message.error(t('workspace.workflowSpace.field_is_empty', { field: node.data.template[field].display_name }))
            checkFieldsValid = false
          }
        })
      }
    })
  } catch (errorInfo) {
    checkFieldsValid = false
  }
  if (!checkFieldsValid) {
    return
  }
  running.value = true
  currentWorkflow.value.data.setting = setting.value.data
  const response = await workflowAPI('run', currentWorkflow.value)
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.submit_workflow_success'))
    runRecordId.value = response.data.rid
    checkStatusTimer.value = setInterval(async () => {
      const response = await workflowAPI('check_status', { rid: runRecordId.value })
      if (response.status == 200) {
        message.success(t('workspace.workflowSpace.run_workflow_success'))
        clearInterval(checkStatusTimer.value)
        running.value = false
        currentWorkflow.value = response.data
        // clearNodesFiles()
      } else if (response.status == 500) {
        running.value = false
        message.error(t('workspace.workflowSpace.run_workflow_failed'))
        clearInterval(checkStatusTimer.value)
      }
    }, 1000)
  } else {
    message.error(t('workspace.workflowSpace.submit_workflow_failed'))
    running.value = false
  }
}

const updateWorkflowScheduleTrigger = async () => {
  running.value = true
  const response = await workflowScheduleTriggerAPI('update', {
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    ...currentWorkflow.value
  })
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.update_schedule_success'))
  } else {
    message.error(t('workspace.workflowSpace.update_schedule_failed'))
  }
  running.value = false
}

const deletingSchedule = ref(false)
const deleteWorkflowScheduleTrigger = async () => {
  deletingSchedule.value = true
  const response = await workflowScheduleTriggerAPI('delete', {
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    ...currentWorkflow.value
  })
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.delete_schedule_success'))
  } else {
    message.error(t('workspace.workflowSpace.delete_schedule_failed'))
  }
  deletingSchedule.value = false
}

const saveWorkflow = async (data) => {
  showingRecord.value = false
  const { title, brief, images, tags, workflow } = data
  updating.value = true
  currentWorkflow.value.title = title
  currentWorkflow.value.brief = brief
  currentWorkflow.value.images = images
  currentWorkflow.value.data = workflow
  clearNodesFiles()
  const response = await workflowAPI('update', {
    wid: currentWorkflow.value.wid,
    title: title,
    brief: brief,
    images: images,
    tags: tags,
    data: workflow,
  })
  updating.value = false
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.save_success'))
    currentWorkflow.value.images = response.data.images
    currentWorkflow.value.tags = response.data.tags
  } else {
    message.error(t('workspace.workflowSpace.save_failed'))
  }
  userWorkflowsStore.updateUserWorkflow(currentWorkflow.value)
}

const deleteWorkflow = async () => {
  const response = await workflowAPI('delete', { wid: currentWorkflow.value.wid })
  if (response.status == 200) {
    message.success(t('workspace.workflowSpace.delete_success'))
    userWorkflowsStore.deleteUserWorkflow(currentWorkflow.value.wid)
    userWorkflowsStore.deleteUserWorkflow(currentWorkflow.value.wid, true)
    router.push({ name: 'WorkflowSpaceMain' })
  } else {
    message.error(t('workspace.workflowSpace.delete_failed'))
  }
}

const editorModalRef = ref(null)
const openEditor = () => {
  editorModalRef.value.showModal()
}

const hasShowFields = (node) => {
  let hasShow = false
  Object.keys(node.data.template).forEach(key => {
    if (node.data.template[key].show) {
      hasShow = true
    }
  })
  return hasShow
}

const showingRecord = ref(false)
const recordStatus = ref('')
const recordErrorTask = ref('')
const alertType = computed(() => {
  if (recordStatus.value == 'FINISHED') {
    return 'success'
  }
  else if (recordStatus.value == 'FAILED') {
    return 'error'
  }
  else {
    return 'info'
  }
})
const setWorkflowRecord = (record) => {
  recordStatus.value = record.status
  currentWorkflow.value.data = record.data
  let [category, node] = (record.data.error_task || '.').split('.')
  category = category.split('_')
    .map((word, index) => {
      if (index === 0) {
        return word.charAt(0).toLowerCase() + word.slice(1);
      }
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join('')
  node = node.split('_')
    .map((word) => {
      return word.charAt(0).toUpperCase() + word.slice(1);
    })
    .join('')
  recordErrorTask.value = `${category}.${node}`
  showingRecord.value = true
}

const openLocalFile = (file) => {
  window.pywebview.api.open_local_file(file)
}
</script>

<template>
  <div class="space-container" v-if="loading">
    <a-skeleton active />
  </div>
  <a-spin :spinning="updating" class="space-container" v-else>
    <a-row justify="space-between" align="middle">
      <a-col>
        <a-typography-title>
          {{ currentWorkflow.title }}
        </a-typography-title>
        <a-space>
          <a-typography-text type="secondary">
            {{ t('workspace.workflowSpace.update_time', {
              time: new
                Date(currentWorkflow.update_time).toLocaleString()
            }) }}
          </a-typography-text>
          <a-divider type="vertical" />
          <a-typography-link @click="briefModalOpen = true">
            {{ t('workspace.workflowSpace.brief') }}
            <a-modal :open="briefModalOpen" :title="t('workspace.workflowSpace.brief')" :width="briefModalWidth"
              :footer="null" class="introduction-modal" @cancel="briefModalOpen = false">
              <a-carousel autoplay arrows dots-class="slick-dots slick-thumb">
                <template #customPaging="props">
                  <a>
                    <img :src="currentWorkflow.images[props.i]" />
                  </a>
                </template>
                <div v-for="(image, index) in currentWorkflow.images" :key="index">
                  <img :src="image" />
                </div>
              </a-carousel>
              <VueMarkdown v-highlight :source="currentWorkflow.brief"
                class="custom-scrollbar markdown-body custom-hljs" />
            </a-modal>
          </a-typography-link>
          <a-divider type="vertical" />
          <a-tag :color="tag.color" v-for="(tag, index) in currentWorkflow.tags" :key="index">
            {{ tag.title }}
          </a-tag>
        </a-space>
      </a-col>
      <a-col>
        <a-space>
          <WorkflowRunRecordsDrawer :workflowId="workflowId" @open-record="setWorkflowRecord" />
          <a-button type="primary" @click="openEditor">
            {{ t('workspace.workflowSpace.edit') }}
          </a-button>
          <a-popconfirm placement="leftTop" :title="t('workspace.workflowSpace.delete_confirm')"
            @confirm="deleteWorkflow">
            <a-button type="primary" danger>
              {{ t('workspace.workflowSpace.delete') }}
            </a-button>
          </a-popconfirm>
        </a-space>
      </a-col>
    </a-row>
    <a-divider />
    <a-row :gutter="[16, 16]">
      <a-col :span="24" v-if="showingRecord">
        <a-alert :type="alertType" show-icon>
          <template #message>
            <span>
              {{ t('workspace.workflowSpace.record_status', {
                status:
                  t(`components.workspace.workflowRunRecordsDrawer.status_${recordStatus.toLowerCase()}`)
              }) }}
            </span>
            <a-divider type="vertical" />
            <span v-if="recordStatus == 'FAILED' && recordErrorTask != '.'">
              {{ t('workspace.workflowSpace.record_error_task', {
                task: t('components.nodes.' + recordErrorTask + '.title')
              }) }}
            </span>
          </template>
        </a-alert>
      </a-col>

      <a-col :lg="12" :md="24">
        <a-row :gutter="[16, 16]">
          <a-typography-title :level="3">{{ t('workspace.workflowSpace.inputs') }}</a-typography-title>
          <template v-for="(node) in currentWorkflow.data.nodes" :key="`node-${node.id}`">
            <a-col :span="24" v-if="node.data.has_inputs && hasShowFields(node) && !['triggers'].includes(node.category)">
              <a-form layout="vertical">
                <template :key="`field-${field}-${templateIndex}`"
                  v-for="(field, templateIndex) in Object.keys(node.data.template)">
                  <a-form-item :key="`field-${field}-${templateIndex}`" :label="node.data.template[field].display_name"
                    v-if="node.data.template[field].show">
                    <TemperatureInput v-model:value="node.data.template[field].value"
                      v-if="node.category == 'llms' && field == 'temperature'" />
                    <a-select v-model:value="node.data.template[field].value" :options="node.data.template[field].options"
                      v-else-if="node.data.template[field].field_type == 'select'" />
                    <a-textarea v-model:value="node.data.template[field].value" :autoSize="true" :showCount="true"
                      :placeholder="node.data.template[field].placeholder"
                      v-else-if="node.data.template[field].field_type == 'textarea'" />
                    <a-input v-model:value="node.data.template[field].value"
                      :placeholder="node.data.template[field].placeholder"
                      v-else-if="node.data.template[field].field_type == 'input'" />
                    <a-input-number v-model:value="node.data.template[field].value"
                      :placeholder="node.data.template[field].placeholder"
                      v-else-if="node.data.template[field].field_type == 'number'" />
                    <a-checkbox v-model:checked="node.data.template[field].value"
                      v-else-if="node.data.template[field].field_type == 'checkbox'" />
                    <UploaderFieldUse v-model="node.data.template[field].value"
                      v-else-if="node.data.template[field].field_type == 'file'" />
                    <ListFieldUse v-model="node.data.template[field].value"
                      v-else-if="node.data.template[field].field_type == 'list'" />
                  </a-form-item>
                </template>
              </a-form>
            </a-col>
          </template>

          <a-divider />

          <a-typography-title :level="3">{{ t('workspace.workflowSpace.triggers') }}</a-typography-title>
          <a-col :span="24">
            <a-row :gutter="[16, 16]">
              <template v-for="(node) in currentWorkflow.data.nodes" :key="`node-${node.id}`">
                <a-col :span="24" v-if="node.category == 'triggers'">
                  <a-button type="primary" block @click="runWorkflow" :loading="running"
                    v-if="node.type == 'ButtonTrigger'">
                    {{ node.data.template.button_text.value }}
                  </a-button>
                  <a-card :title="t('components.nodes.triggers.ScheduleTrigger.schedule_settings')"
                    v-else-if="node.type == 'ScheduleTrigger'">
                    <template #extra>
                      <a-space>
                        <a-button type="primary" @click="updateWorkflowScheduleTrigger" :loading="running">
                          {{ t('components.nodes.triggers.ScheduleTrigger.save_schedule_settings') }}
                        </a-button>
                        <a-popconfirm :title="t('workspace.workflowSpace.delete_schedule_trigger_confirm')"
                          @confirm="deleteWorkflowScheduleTrigger">
                          <a-button type="primary" danger>
                            {{ t('workspace.workflowSpace.delete') }}
                          </a-button>
                        </a-popconfirm>
                      </a-space>
                    </template>
                    <cron-ant v-model="node.data.template.schedule.value"
                      :button-props="{ type: 'primary', shape: 'round', }" :locale="language" />
                  </a-card>
                </a-col>
              </template>
            </a-row>
          </a-col>
        </a-row>
      </a-col>

      <a-col :lg="12" :md="24">
        <a-typography-title :level="3">{{ t('workspace.workflowSpace.outputs') }}</a-typography-title>
        <a-spin :spinning="running">
          <a-row :gutter="[16, 16]">
            <template v-for="(node) in currentWorkflow.data.nodes" :key="`node-${node.id}`">
              <template v-if="node.type == 'Text'">
                <a-col :span="24" v-if="node.data.template.text.show">
                  <a-typography-title :level="5">
                    {{ node.data.template.output_title.value }}
                  </a-typography-title>
                  <template v-if="node.data.template.render_markdown.value">
                    <vue-markdown v-highlight :source="node.data.template.text.value" class="markdown-body custom-hljs" />
                    <a-typography-paragraph :copyable="{ text: node.data.template.text.value }">
                    </a-typography-paragraph>
                  </template>
                  <a-typography-paragraph :copyable="{ text: node.data.template.text.value }" v-else>
                    {{ node.data.template.text.value }}
                  </a-typography-paragraph>
                </a-col>
              </template>

              <template v-else-if="node.type == 'Document'">
                <a-col :span="24" v-if="node.data.template.show_local_file.value">
                  <a-typography-link @click="openLocalFile(node.data.template.output.value)">
                    {{ node.data.template.output.value }}
                  </a-typography-link>
                </a-col>
              </template>

              <template v-else-if="node.type == 'Audio'">
                <a-col :span="24" v-if="node.data.template.show_player.value">
                  <AudioPlayer :audios="[node.data.template.audio_url.value]" />
                </a-col>
              </template>

              <template v-else-if="node.type == 'Mindmap'">
                <a-col :span="24" v-if="node.data.template.show_mind_map.value">
                  <MindmapRenderer :content="node.data.template.content.value" style="width: 100%;min-height: 50vh;" />
                </a-col>
              </template>
            </template>
          </a-row>
        </a-spin>
      </a-col>
    </a-row>
    <WorkflowEditor ref="editorModalRef" :title="currentWorkflow.title" :brief="currentWorkflow.brief"
      :images="currentWorkflow.images" :tags="currentWorkflow.tags" :key="currentWorkflow.wid"
      :nodes="currentWorkflow.data.nodes" :edges="currentWorkflow.data.edges" @ok="saveWorkflow" />
  </a-spin>
</template>

<style scoped>
.space-container {
  height: calc(100vh - 64px);
}

:deep(.slick-dots) {
  position: relative;
  height: auto;
}

:deep(.slick-slide img) {
  border: 5px solid #fff;
  display: block;
  margin: auto;
  max-width: 80%;
  max-height: 60vh;
}

:deep(.slick-arrow) {
  display: none !important;
}

:deep(.slick-thumb) {
  bottom: 0px;
}

:deep(.slick-thumb li) {
  width: 60px;
  height: 45px;
}

:deep(.slick-thumb li img) {
  width: 100%;
  height: 100%;
  filter: grayscale(100%);
  display: block;
}

:deep .slick-thumb li.slick-active img {
  filter: grayscale(0%);
}
</style>