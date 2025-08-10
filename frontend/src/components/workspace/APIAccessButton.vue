<script setup>
import { ref, reactive, shallowRef, computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Code, CodeDownload, Copy } from '@icon-park/vue-next'
import { python } from '@codemirror/lang-python'
import { javascript } from '@codemirror/lang-javascript'
import { oneDark } from '@codemirror/theme-one-dark'
import { EditorView } from "@codemirror/view"
import { Codemirror } from 'vue-codemirror'
import CopyButton from '@/components/CopyButton.vue'
import { jsonToPythonDict } from '@/utils/util'
import { hasShowFields, getUIDesignFromWorkflow, nonFormItemsTypes } from '@/utils/workflow'
import { settingAPI } from '@/api/user'

const props = defineProps({
  workflowData: {
    type: Object,
    required: true,
  },
  appearanceType: {
    type: String,
    required: false,
    default: 'menuItem'
  },
  tooltip: {
    type: String,
    required: false,
    default: '',
  },
  buttonProps: {
    type: Object,
    required: false,
    default: () => {
      return {
        block: false,
        danger: false,
        disabled: false,
        ghost: false,
        loading: false,
        shape: 'default',
        size: 'middle',
        type: 'default',
      }
    },
  }
})

const { t } = useI18n()
const open = ref(false)
const apiUrl = ref('http://localhost:8787')

// Get current API URL from settings
onMounted(async () => {
  try {
    const res = await settingAPI('get', {})
    if (res.data?.api?.current_url) {
      apiUrl.value = res.data.api.current_url
    } else if (res.data?.api?.port) {
      apiUrl.value = `http://${res.data.api.host || 'localhost'}:${res.data.api.port}`
    }
  } catch (error) {
    console.error('Failed to get API settings:', error)
  }
})

let submitData = {}
props.workflowData.data.nodes.forEach((node) => {
  if (node.data.has_inputs && hasShowFields(node) && !['triggers'].includes(node.category)) {
    Object.keys(node.data.template).forEach((field) => {
      if (node.data.template[field].show) {
        if (!submitData[node.id]) {
          submitData[node.id] = {}
        }
        submitData[node.id][field] = node.data.template[field].value
      }
    })
  }
})

const submitInputFields = ref([])
const uiDesign = getUIDesignFromWorkflow(props.workflowData)
const reactiveUIDesign = reactive(uiDesign)
submitInputFields.value = reactiveUIDesign.inputFields.filter((field) => !nonFormItemsTypes.includes(field.field_type)).map((field) => {
  return {
    node_id: field.nodeId,
    field_name: field.fieldName,
    value: field.value,
  }
})

const asyncPayload = {
  wid: props.workflowData.wid,
  output_scope: 'output_fields_only',
  wait_for_completion: false,
  input_fields: submitInputFields.value
}
const syncPayload = {
  wid: props.workflowData.wid,
  output_scope: 'output_fields_only',
  wait_for_completion: true,
  input_fields: submitInputFields.value
}

const programmingLanguage = ref('python')
const syncOrAsync = ref('async')

const FontSizeTheme = EditorView.theme({
  ".cm-content": {
    fontFamily: "Cascadia Code, Consolas, Monaco, Menlo, Ubuntu Mono, Liberation Mono, DejaVu Sans Mono, Courier New, monospace",
    fontSize: '14px',
  },
})

const languageSettings = {
  python: {
    extensions: [python(), oneDark, FontSizeTheme],
    tabSize: 4,
    extName: 'py',
  },
  javascript: {
    extensions: [javascript(), oneDark, FontSizeTheme],
    tabSize: 2,
    extName: 'js',
  },
  curl: {
    extensions: [oneDark, FontSizeTheme],
    tabSize: 2,
    extName: 'sh',
  },
}

const view = shallowRef()
const handleReady = (payload) => {
  view.value = payload.view
}

const code = computed(() => {
  return {
    python: {
      async: `import time
import requests

# Local API endpoint
api_url = "${apiUrl.value}"

# If you need full graph data, you can set output_scope to "all".
payload = ${jsonToPythonDict(asyncPayload)}

# Run workflow
response = requests.post(f"{api_url}/api/workflow/run", json=payload)
result = response.json()
print(f"Status: {result['status']}")
print(f"Message: {result['msg']}")

if result["status"] != 200:
    print("Run workflow failed!")
    exit()

record_id = result["data"]["rid"]
print(f"Record ID: {record_id}")

# Check status
status_payload = {"rid": record_id}
while True:
    response = requests.post(f"{api_url}/api/workflow/check-status", json=status_payload)
    result = response.json()
    print(f"Status: {result['status']} - {result['msg']}")
    
    if result["status"] == 200:  # FINISHED
        print("Workflow finished successfully!")
        print("Output:", result["data"])
        break
    elif result["status"] == 500:  # FAILED
        print("Workflow failed!")
        print("Error:", result["data"])
        break
    elif result["status"] == 202:  # RUNNING
        print("Workflow is still running...")
        time.sleep(2)
    else:
        print(f"Unknown status: {result['status']}")
        break
`,
      sync: `import requests

# Local API endpoint
api_url = "${apiUrl.value}"

# If you need full graph data, you can set output_scope to "all".
# wait_for_completion=True will wait up to 30 seconds for completion
payload = ${jsonToPythonDict(syncPayload)}

response = requests.post(f"{api_url}/api/workflow/run", json=payload)
result = response.json()
print(f"Status: {result['status']}")
print(f"Message: {result['msg']}")

if result["status"] == 200 and result["msg"] == "FINISHED":
    print("Workflow finished successfully!")
    print("Output:", result["data"])
elif result["status"] == 202 and result["msg"] == "TIMEOUT":
    print("Workflow is taking longer than 30 seconds.")
    print("Record ID:", result["data"]["rid"])
    print("Please check status separately using the record ID.")
else:
    print(f"Unexpected result: {result}")
`
    },
    javascript: {
      async: `const axios = require('axios');

// Local API endpoint
const apiUrl = "${apiUrl.value}";

// If you need full graph data, you can set output_scope to "all".
const payload = ${JSON.stringify(asyncPayload, null, 2)};

// Run workflow
axios.post(\`\${apiUrl}/api/workflow/run\`, payload)
  .then(response => {
    const result = response.data;
    console.log(\`Status: \${result.status}\`);
    console.log(\`Message: \${result.msg}\`);

    if (result.status !== 200) {
      console.error("Run workflow failed!");
      process.exit();
    }

    const recordId = result.data.rid;
    console.log(\`Record ID: \${recordId}\`);

    // Check status
    const statusPayload = { rid: recordId };
    
    const checkStatus = () => {
      axios.post(\`\${apiUrl}/api/workflow/check-status\`, statusPayload)
        .then(statusResponse => {
          const statusResult = statusResponse.data;
          console.log(\`Status: \${statusResult.status} - \${statusResult.msg}\`);

          if (statusResult.status === 200) { // FINISHED
            console.log("Workflow finished successfully!");
            console.log("Output:", statusResult.data);
          } else if (statusResult.status === 500) { // FAILED
            console.error("Workflow failed!");
            console.error("Error:", statusResult.data);
          } else if (statusResult.status === 202) { // RUNNING
            console.log("Workflow is still running...");
            setTimeout(checkStatus, 2000);
          } else {
            console.log(\`Unknown status: \${statusResult.status}\`);
          }
        })
        .catch(error => {
          console.error("Error checking status:", error);
        });
    };

    checkStatus();
  })
  .catch(error => {
    console.error("Error running workflow:", error);
  });
`,
      sync: `const axios = require('axios');

// Local API endpoint
const apiUrl = "${apiUrl.value}";

// If you need full graph data, you can set output_scope to "all".
// wait_for_completion=true will wait up to 30 seconds for completion
const payload = ${JSON.stringify(syncPayload, null, 2)};

axios.post(\`\${apiUrl}/api/workflow/run\`, payload)
  .then(response => {
    const result = response.data;
    console.log(\`Status: \${result.status}\`);
    console.log(\`Message: \${result.msg}\`);

    if (result.status === 200 && result.msg === "FINISHED") {
      console.log("Workflow finished successfully!");
      console.log("Output:", result.data);
    } else if (result.status === 202 && result.msg === "TIMEOUT") {
      console.log("Workflow is taking longer than 30 seconds.");
      console.log("Record ID:", result.data.rid);
      console.log("Please check status separately using the record ID.");
    } else {
      console.log("Unexpected result:", result);
    }
  })
  .catch(error => {
    console.error("Error running workflow:", error);
  });
`
    },
    curl: {
      async: `# Run workflow
curl -X POST '${apiUrl.value}/api/workflow/run' \\
-H 'Content-Type: application/json' \\
-d '${JSON.stringify(asyncPayload, null, 2)}'

# Save the record ID from the response, then check status:
# curl -X POST '${apiUrl.value}/api/workflow/check-status' \\
# -H 'Content-Type: application/json' \\
# -d '{"rid": "RECORD_ID_HERE"}'`,
      sync: `# Run workflow with wait_for_completion=true (max 30 seconds)
curl -X POST '${apiUrl.value}/api/workflow/run' \\
-H 'Content-Type: application/json' \\
-d '${JSON.stringify(syncPayload, null, 2)}'`,
    },
  }
})

const currentCode = computed(() => {
  return code.value[programmingLanguage.value][syncOrAsync.value];
})

const downloadCode = () => {
  const blob = new Blob([currentCode.value], { type: 'text/plain;charset=utf-8' });
  const link = document.createElement('a');
  link.href = URL.createObjectURL(blob);
  link.download = `workflow_api.${languageSettings[programmingLanguage.value].extName}`;
  link.click();
  URL.revokeObjectURL(link.href);
}
</script>

<template>
  <a-menu-item v-if="appearanceType == 'menuItem'" key="api_access" @click="open = true">
    <Code /> {{ t('components.workspace.apiAccessButton.api_access') }}
  </a-menu-item>
  <a-tooltip v-else-if="appearanceType == 'button'" :title="props.tooltip">
    <a-button :block="buttonProps.block" :danger="buttonProps.danger" :disabled="buttonProps.disabled"
      :ghost="buttonProps.ghost" :loading="buttonProps.loading" :shape="buttonProps.shape" :size="buttonProps.size"
      :type="buttonProps.type" @click="open = true">
      <template #icon>
        <Code />
      </template>
    </a-button>
  </a-tooltip>
  <a-modal :open="open" width="70vw" @cancel="open = false">
    <template #title>
      <a-flex align="center" gap="small">
        <Code />
        {{ t('components.workspace.apiAccessButton.api_access') }}
      </a-flex>
    </template>

    <template #footer>
      <a-flex align="flex-start" gap="middle">
        <a-select v-model:value="syncOrAsync" style="width: 150px; text-align: start;">
          <a-select-option value="sync">
            {{ t('common.sync') }}
          </a-select-option>
          <a-select-option value="async">
            {{ t('common.async') }}
          </a-select-option>
        </a-select>
        <CopyButton type="text" :copyText="currentCode">
          <template #icon>
            <Copy />
          </template>
        </CopyButton>

        <a-tooltip :title="t('components.codeEditorModal.download_code')">
          <a-button type="text" @click="downloadCode">
            <template #icon>
              <CodeDownload />
            </template>
          </a-button>
        </a-tooltip>
      </a-flex>
    </template>

    <a-tabs v-model:activeKey="programmingLanguage">
      <a-tab-pane key="python" tab="Python" />
      <a-tab-pane key="javascript" tab="JavaScript" />
      <a-tab-pane key="curl" tab="cURL" />
    </a-tabs>

    <div style="margin-bottom: 16px;">
      <a-alert type="info" show-icon>
        <template #message>
          <span>{{ t('components.workspace.apiAccessButton.local_api_note', { url: apiUrl }) }}</span>
        </template>
      </a-alert>
    </div>

    <div style="position: relative;">
      <Codemirror 
        :modelValue="currentCode" 
        :style="{ height: '55vh', minHeight: '300px' }" 
        :autofocus="true"
        :indent-with-tab="true" 
        :tab-size="languageSettings[programmingLanguage].tabSize"
        :extensions="languageSettings[programmingLanguage].extensions" 
        :disabled="true" 
        @ready="handleReady" />
    </div>

    <a-row :gutter="16" style="margin-top: 16px;">
      <a-col :span="24">
        <a-space>
          <a-typography-text type="secondary">
            {{ t('components.workspace.apiAccessButton.workflow_id') }}:
          </a-typography-text>
          <a-typography-text copyable>
            {{ props.workflowData.wid }}
          </a-typography-text>
        </a-space>
      </a-col>

      <a-col :span="24" v-if="submitInputFields.length > 0">
        <a-typography-text type="secondary">
          {{ t('components.workspace.apiAccessButton.input_fields') }}:
        </a-typography-text>
      </a-col>

      <a-col :span="24" v-for="(field, index) in submitInputFields" :key="index">
        <a-space>
          <a-typography-text type="secondary">
            {{ t('components.workspace.apiAccessButton.node_id') }}:
          </a-typography-text>
          <a-typography-text copyable>
            {{ field.node_id }}
          </a-typography-text>

          <a-divider type="vertical" />

          <a-typography-text type="secondary">
            {{ t('components.workspace.apiAccessButton.field_name') }}:
          </a-typography-text>
          <a-typography-text copyable>
            {{ field.field_name }}
          </a-typography-text>
        </a-space>
      </a-col>
    </a-row>
  </a-modal>
</template>

<style scoped>
.code-editor .cm-editor {
  height: 100%;
}
</style>