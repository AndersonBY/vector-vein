import assert from 'node:assert/strict'
import test from 'node:test'
import { fileURLToPath } from 'node:url'
import { createSSRApp } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createI18n } from 'vue-i18n'
import { createPinia } from 'pinia'
import { createServer } from 'vite'
import vue from '@vitejs/plugin-vue'

const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }

test('workflow stop guards duplicate and stale requests, retries failures, and preserves terminal output', async () => {
  const previousInterval = globalThis.setInterval
  globalThis.setInterval = () => 123
  const previous = globalThis.__stopHarness
  const calls = [], notices = []
  let request = async () => ({ status: 500 })
  globalThis.__stopHarness = { request: (...args) => { calls.push(args); return request(...args) }, notices }
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [vue(), { name: 'stop-fixtures', enforce: 'pre', transform(source, id) {
      if (!['WorkflowUse.vue', 'WorkflowRunRecordsDrawer.vue'].some(name => id.endsWith(name))) return
      return source.replace(/from (['"])(@[^'"]+|vue-router|ant-design-vue)\1/g, (all, quote, name) => {
        if (!name.startsWith('@/') && !['vue-router', 'ant-design-vue'].includes(name)) return all
        if (['@/utils/workflowFailures', '@/icons', '@/components/nodes/tools/_httpRequestShared.js'].includes(name)) return all
        return `from "virtual:stop:${name}"`
      })
    }, resolveId(id) { if (id.startsWith('virtual:stop:')) return '\0' + id }, load(id) {
      if (!id.startsWith('\0virtual:stop:')) return
      const name = id.slice('\0virtual:stop:'.length)
      if (name.endsWith('.vue')) return 'export default {}'
      if (name.startsWith('@/api/')) return 'export const workflowAPI = (...args) => globalThis.__stopHarness.request(...args); export const workflowRunRecordAPI = workflowAPI; export const workflowScheduleTriggerAPI = workflowAPI; export const databaseAPI = workflowAPI; export const relationalDatabaseAPI = workflowAPI; export const settingAPI = workflowAPI'
      if (name === 'vue-router') return 'export const useRouter = () => ({push(){}})'
      if (name === 'ant-design-vue') return 'export const message = {success: value => globalThis.__stopHarness.notices.push(["success",value]),error: value => globalThis.__stopHarness.notices.push(["error",value])}'
      if (name === '@/utils/util') return 'export const deepCopy = value => JSON.parse(JSON.stringify(value)); export const formatTime = value => value'
      if (name === '@/utils/workflow') return 'export const hasShowFields = () => false; export const checkFieldsValid = () => true; export const nonFormItemsTypes = []; export const getNodeConnectedNodes = () => []; export const getUIDesignFromWorkflow = workflow => ({inputFields: [],outputNodes: workflow.data.nodes,triggerNodes: [],humanFeedbackNodes: []})'
      if (name.startsWith('@/stores/')) { const exportName = {userSettings:'useUserSettingsStore',userDatabase:'useUserDatabasesStore',userWorkflows:'useUserWorkflowsStore',userRelationalDatabase:'useUserRelationalDatabasesStore'}[name.split('/').at(-1)]; return `import {defineStore} from "pinia"; export const ${exportName} = defineStore("${exportName}", {state: () => ({setting:{},userDatabases:[],userRelationalDatabases:[]})})` }
    } }], resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  try {
    const component = (await server.ssrLoadModule('/src/components/workspace/WorkflowUse.vue')).default
    let exercised = false
    const app = createSSRApp({ ...component, ssrRender: undefined, render: () => null, async setup(props, context) {
      const c = component.setup(props, context)
      const nodes = [{id:'out',type:'Text',data:{template:{text:{value:'completed output'}}}}]
      c.savedWorkflow.value = {data:{nodes:[]}}
      c.currentWorkflow.value = {data:{nodes:[]}}
      c.timelineSnapshot.value = {nodes:[]}
      c.runRecordId.value = 'one'; c.recordStatus.value = 'RUNNING'; c.running.value = true
      const pending = deferred(); request = () => pending.promise
      const stopping = c.stopWorkflow(); await c.stopWorkflow()
      assert.equal(calls.filter(([action]) => action === 'stop').length, 1)
      c.stopStatusPolling(); c.runRecordId.value = 'two'
      pending.resolve({status:200,data:{status:'STOPPED'}}); await stopping
      assert.equal(c.recordStatus.value, 'RUNNING')
      request = async () => { throw Error('offline') }
      await c.stopWorkflow(); assert.equal(c.stopRequest.value, null)
      assert.equal(c.recordStatus.value, 'RUNNING')
      request = async action => action === 'stop' ? {status:200,data:{status:'STOPPING'}} : {status:202,msg:'STOPPING',data:{finished_nodes:nodes}}
      await c.stopWorkflow(); assert.equal(c.recordStatus.value, 'STOPPING'); assert.equal(c.running.value, true)
      const before = calls.length; await c.stopWorkflow(); assert.equal(calls.length, before)
      request = async () => ({status:200,msg:'STOPPED',data:{data:{nodes}}})
      await c.checkWorkflowRunningStatus()
      assert.equal(c.recordStatus.value, 'STOPPED'); assert.equal(c.running.value, false)
      assert.equal(c.outputNodes.value[0].data.template.text.value, 'completed output')
      assert.equal(c.showTimeline.value, false)
      assert.equal(notices.filter(([kind]) => kind === 'success').length, 0)
      const definition = {id:'downstream',category:'outputs',type:'Text',data:{template:{text:{value:''}}}}
      c.savedWorkflow.value = {version:1,data:{nodes:[definition]}}
      c.currentWorkflow.value = {version:1,data:{nodes:[definition]}}
      c.outputNodes.value = [{...definition,finished:true,data:{template:{text:{value:'previous run output'}}}}]
      request = async action => action === 'run' ? {status:200,data:{rid:'rerun'}}
        : {status:202,msg:'STOPPING',data:{finished_nodes:[]}}
      await c.runWorkflow()
      assert.equal(c.outputNodes.value[0].data.template.text.value,'')
      await c.checkWorkflowRunningStatus()
      assert.equal(c.outputNodes.value[0].data.template.text.value,'')
      request = async () => ({status:200,msg:'STOPPED',data:{data:{nodes:[definition]}}})
      await c.checkWorkflowRunningStatus()
      assert.equal(c.outputNodes.value[0].data.template.text.value,'')
      assert.equal(c.running.value,false)

      const invalidHttp = { id: 'request', type: 'HttpRequest', data: { template: { query_params: { value: '{' } } } }
      c.savedWorkflow.value = { version: 1, data: { nodes: [invalidHttp, definition] } }
      c.currentWorkflow.value = { version: 1, data: { nodes: [invalidHttp, definition] } }
      c.outputNodes.value = [{ ...definition, finished: true, data: { template: { text: { value: 'retained until a valid run' } } } }]
      const beforeInvalid = calls.length
      await c.runWorkflow()
      assert.equal(calls.length, beforeInvalid)
      assert.equal(c.running.value, false)
      assert.equal(c.outputNodes.value[0].data.template.text.value, 'retained until a valid run')
      assert.match(notices.at(-1)[1], /query_params.*invalid_json/)

      const feedbackNode = id => ({id,type:'HumanFeedback',category:'controlFlows',data:{template:{human_input:{value:''},hint_message:{value:'<script>hint</script>'}}}})
      const pausedRecord = {rid:'paused',status:'PAUSED',data:{nodes:[feedbackNode('first'),feedbackNode('later'),definition],pending_feedback_nodes:['first']}}
      c.setWorkflowRecord(pausedRecord)
      assert.equal(c.running.value,false)
      assert.deepEqual(c.pendingFeedbackNodes.value.map(node => node.id),['first'])
      const beforeBlank = calls.length
      c.feedbackDrafts.first = '  '
      await c.resumeWorkflow(); assert.equal(calls.length,beforeBlank)
      c.feedbackDrafts.first = 'approved'
      request = async () => {throw Error('offline')}
      await c.resumeWorkflow()
      assert.equal(c.feedbackDrafts.first,'approved'); assert.equal(c.recordStatus.value,'PAUSED')
      const resumePending = deferred(); request = () => resumePending.promise
      const resume = c.resumeWorkflow(); const resumeCalls = calls.length
      await c.resumeWorkflow(); assert.equal(calls.length,resumeCalls)
      c.setWorkflowRecord({...pausedRecord,rid:'different'})
      resumePending.resolve({status:200,data:{status:'RUNNING'}}); await resume
      assert.equal(c.runRecordId.value,'different'); assert.equal(c.recordStatus.value,'PAUSED')
      c.feedbackDrafts.first = 'new draft'
      request = async (action,payload) => action === 'resume'
        ? (assert.deepEqual(payload,{rid:'different',human_feedback_nodes:[{node_id:'first',content:'new draft'}]}),{status:200,data:{status:'RUNNING'}})
        : {status:202,msg:'RUNNING',data:{finished_nodes:[]}}
      await c.resumeWorkflow()
      assert.equal(c.recordStatus.value,'RUNNING'); assert.equal(c.feedbackDrafts.first,undefined)
      c.setWorkflowRecord(pausedRecord)
      request = async action => action === 'stop' ? {status:200,data:{status:'STOPPED'}}
        : {status:200,msg:'STOPPED',data:pausedRecord}
      await c.stopWorkflow(); assert.equal(c.recordStatus.value,'STOPPED')
      c.setWorkflowRecord({...pausedRecord,data:{...pausedRecord.data,pending_feedback_nodes:[],pending_feedback_runs:['child']}})
      request = async action => action === 'get' ? {status:200,data:{...pausedRecord,rid:'child',data:{nodes:[feedbackNode('first')],pending_feedback_nodes:['first']}}} : {status:102,msg:'PAUSED',data:{...pausedRecord,data:{...pausedRecord.data,pending_feedback_nodes:[],pending_feedback_runs:['child']}}}
      await c.checkWorkflowRunningStatus()
      assert.equal(c.pendingFeedbackNodes.value[0].feedbackRid,'child')
      c.currentWorkflow.value.data = {nodes:[],feedback_resume_ready:true}
      c.feedbackRunRecords.value = []
      assert.equal(c.canContinue.value,true)
      request = async (action,payload) => action === 'resume'
        ? (assert.deepEqual(payload,{rid:c.runRecordId.value,human_feedback_nodes:[]}),{status:200,data:{status:'RUNNING'}})
        : {status:202,msg:'RUNNING',data:{finished_nodes:[]}}
      await c.resumeWorkflow()
      assert.equal(c.recordStatus.value,'RUNNING')
      c.stopStatusPolling()
      exercised = true
      return () => null
    } }, { workflow: {data:{nodes:[]}} })
    app.use(createPinia()); app.use(createI18n({legacy:false,locale:'en',missingWarn:false,fallbackWarn:false,messages:{en:{}}}))
    await renderToString(app); assert.equal(exercised, true)
    const drawer = (await server.ssrLoadModule('/src/components/workspace/WorkflowRunRecordsDrawer.vue')).default
    const drawerApp = createSSRApp({...drawer, ssrRender:undefined, render:() => null, async setup(props, context) {
      const c = drawer.setup(props, context)
      c.open.value = true
      c.loading.value = false
      const record = {rid:'drawer',status:'RUNNING'}
      c.workflowRunRecords.data = [record]
      const pending = deferred(); request = () => pending.promise
      const stop = c.stopWorkflowRunRecord(record)
      const count = calls.length
      await c.stopWorkflowRunRecord(record); assert.equal(calls.length,count)
      assert.equal(c.loading.value,false)
      request = async () => ({status:200,data:{records:[{...record,status:'STOPPING'}],total:1,page:1,page_size:10}})
      pending.resolve({status:200,data:{status:'STOPPING'}}); await stop
      assert.equal(c.workflowRunRecords.data[0].status,'STOPPING')
      assert.equal(c.workflowRunRecords.loading,false)
      const beforeRerun = calls.length; await c.rerunWorkflowRunRecord(record)
      assert.equal(calls.length,beforeRerun)
      record.status = 'RUNNING'; request = async () => {throw Error('offline')}
      await c.stopWorkflowRunRecord(record)
      assert.equal(c.stoppingRecords.size,0)
      assert.equal(record.status,'RUNNING')
      c.open.value = false
      return () => null
    }})
    drawerApp.use(createI18n({legacy:false,locale:'en',missingWarn:false,fallbackWarn:false,messages:{en:{}}}))
    await renderToString(drawerApp)
  } finally { await server.close(); globalThis.setInterval = previousInterval; globalThis.__stopHarness = previous }
})
