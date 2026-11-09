import { iconButtonFixture } from './taskAgentButtonFixture.js'
import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick } from 'vue'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createServer } from 'vite'
import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'
async function componentSource(path, id) {
  const filename = fileURLToPath(new URL(path, import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const script = compileScript(descriptor, { id })
  const source = script.content.replace('export default', 'const component =')
  const template = compileTemplate({ source: descriptor.template.content, filename, id,
    compilerOptions: { bindingMetadata: script.bindings } }).code.replace('export function render', 'function render')
  return `${source}\n${template}\ncomponent.render = render; export default component`
}
const renderer = () => createRenderer({
  patchProp: (node, key, _old, value) => { node.props[key] = value },
  insert: (node, parent, anchor) => {
    if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
    node.parent = parent
    const index = anchor ? parent.children.indexOf(anchor) : -1
    if (index < 0) parent.children.push(node)
    else parent.children.splice(index, 0, node)
  },
  remove: node => { if (node?.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1) },
  createElement: type => ({ type, props: {}, style: {}, children: [], parent: null }),
  createText: text => ({ text }),
  createComment: text => ({ text }),
  setText: (node, text) => { node.text = text },
  setElementText: (node, text) => { node.text = text },
  parentNode: node => node.parent,
  nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
})
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await nextTick() }
const textOf = node => [node?.text || '', ...(node?.children || []).map(textOf)].join(' ')
const findAll = (node, predicate, results = []) => {
  if (predicate(node)) results.push(node)
  for (const child of node.children || []) findAll(child, predicate, results)
  return results
}



const empty = 'export default { render: () => null }'
const baseDetailModules = async () => ({
  '@/components/TextOutput.vue': empty,
  '@/views/Workspace/TaskAgent/TaskAgentTimeline.vue': empty,
  '@/views/Workspace/TaskAgent/TaskAgentWorkspace.vue': empty,
  '@/views/Workspace/TaskAgent/TaskAgentWorkflowRuns.vue': empty,
  '@/views/Workspace/TaskAgent/TaskAgentInteraction.vue': empty,
  '@/views/Workspace/TaskAgent/TaskAgentPermissions.vue': 'import {h} from "vue"; export default {props:["modelValue","disabled"],emits:["update:modelValue"],setup:(props,{emit})=>()=>h("PermissionsStub",{modelValue:props.modelValue,disabled:props.disabled,onChange:val=>emit("update:modelValue",val)})}',
  '@/views/Workspace/TaskAgent/TaskAgentContextUsage.vue': 'import {h} from "vue"; export default {props:["taskId","tokenUsage","contextWindow","disabled"],emits:["refresh"],setup:(props,{emit})=>()=>h("ContextUsageStub",{taskId:props.taskId,tokenUsage:props.tokenUsage,contextWindow:props.contextWindow,disabled:props.disabled,onRefresh:()=>emit("refresh")})}',
  '@/views/Workspace/TaskAgent/TaskAgentModelError.vue': 'import {h} from "vue"; export default {props:["failure","modelConfig"],setup:props=>()=>h("ModelErrorStub",{failure:props.failure,modelConfig:props.modelConfig})}',
  '@/components/ModelPicker.vue': 'import {h} from "vue"; export default {props:["model","modelProvider","preference","reasoningEffort","options","saveSelection","loading","disabled"],setup:props=>()=>h("ModelPickerStub",{model:props.model,modelProvider:props.modelProvider,reasoningEffort:props.reasoningEffort,disabled:props.disabled,loading:props.loading,saveSelection:props.saveSelection})}',
  '@/utils/common': 'export const getChatModelOptions=()=>[{value:"Local",label:"Local",children:[{value:"gpt-4.1",label:"GPT-4.1"},{value:"claude-sonnet",label:"Claude Sonnet"}]}]',
  '@/stores/modelCatalog': 'export const useModelCatalogStore=()=>({ensureLoaded:()=>{globalThis.__catalogLoaded=(globalThis.__catalogLoaded||0)+1}})',
  '@/icons': 'export const Left={render:()=>null},Send=Left,Pause=Left,PlayOne=Left,HandleSquare=Left,MenuUnfoldOne=Left,Down=Left,Robot=Left,Time=Left,ListOne=Left; export const Refresh=Left,Close=Left,Delete=Left,Undo=Left,Star=Left,OffScreenOne=Left,OpenExternal=Left;',
  '@/utils/taskAgentPresentation': await readFile(new URL('../src/utils/taskAgentPresentation.js', import.meta.url), 'utf8'),
  '@/utils/taskAgentTimeline': await readFile(new URL('../src/utils/taskAgentTimeline.js', import.meta.url), 'utf8'),
  '/task-message-test.js': 'export const message={error:m=>globalThis.__msgErrors?.push(m),success:m=>globalThis.__msgSuccess?.push(m),warning:m=>globalThis.__msgWarnings?.push(m)}',
})

test('detail answers the displayed question, retries the same request and ignores a response after route change', async () => {
  const empty = 'export default { render: () => null }'
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    ...(await baseDetailModules()),
    '/detail-test.js': (await componentSource('../src/views/Workspace/TaskAgent/TaskAgentDetail.vue', 'task-detail')).replaceAll("'./TaskAgent", "'@/views/Workspace/TaskAgent/TaskAgent").replace("'ant-design-vue'", "'/task-message-test.js'"),
    '@/components/TextOutput.vue': empty,
    '@/views/Workspace/TaskAgent/TaskAgentTimeline.vue': empty,
    '@/views/Workspace/TaskAgent/TaskAgentWorkspace.vue': empty,
    '@/views/Workspace/TaskAgent/TaskAgentWorkflowRuns.vue': empty,
    '@/views/Workspace/TaskAgent/TaskAgentInteraction.vue': 'import {h} from "vue"; export default {props:["question","busy","disabled"],emits:["answer","approve"],setup:(props,{emit})=>()=>h("Question",{question:props.question,disabled:props.disabled,onAnswer:action=>emit("answer",action)})}',
    '@/icons': 'export const Left={render:()=>null},Send=Left,Pause=Left,PlayOne=Left,HandleSquare=Left,MenuUnfoldOne=Left,Down=Left,Robot=Left,Time=Left,ListOne=Left; export const Refresh=Left,Close=Left,Delete=Left,Undo=Left,Star=Left,OffScreenOne=Left,OpenExternal=Left;',
    '@/api/taskAgent': 'export const taskAgentAPI=(action,payload)=>globalThis.__taskAPI(action,payload)',
    '@/utils/taskAgentPresentation': await readFile(new URL('../src/utils/taskAgentPresentation.js', import.meta.url), 'utf8'),
    '@/utils/taskAgentTimeline': await readFile(new URL('../src/utils/taskAgentTimeline.js', import.meta.url), 'utf8'),
    '/task-message-test.js': 'export const message={error:()=>{}}',
  }
  const server = await createServer({ configFile:false, root:fileURLToPath(new URL('..',import.meta.url)), plugins:[{name:'task-detail-test',resolveId:id=> Object.hasOwn(modules,id)?id:undefined,load:id=>modules[id]}], server:{middlewareMode:true,hmr:false,ws:false}, optimizeDeps:{noDiscovery:true},appType:'custom' })
  const originalWindow = globalThis.window
  let app
  try {
    const question = { kind:'user',sessionId:'task',turnId:'task/turn/first',generation:1,interactionId:'q1',operationId:'op',attempt:1,requestDigest:'digest',prompt:'Format?',answerSpec:{kind:'single',options:['Markdown','Text'],allowCustomOptions:false} }
    const snapshot = id => ({task:{tid:id,title:id,status:'WAITING_FOR_USER',current_turn_id:id+'/turn/first',config_snapshot:{agent_profile:{max_cycles:id==='task'?0:7}}},messages:[],timeline:[],state:{pendingInteraction:id==='task'?question:null},todos:[],sync_error:false})
    const calls=[]
    let actionCalls=0
    let lateResolve
    let liveResolve, liveRequested = false
    let timerId=0
    const timers=new Map()
    globalThis.window={setTimeout:fn=>{timers.set(++timerId,fn);return timerId},clearTimeout:id=>timers.delete(id)}
    globalThis.__taskAPI=async(action,payload)=>{
      calls.push({action,payload})
      if(action==='get') {
        if (!payload.cached && !liveRequested) { liveRequested = true; return new Promise(resolve => { liveResolve = resolve }) }
        return {status:200,data:snapshot(payload.task_id)}
      }
      actionCalls++
      if(actionCalls===1)return {status:503}
      return new Promise(resolve=>{lateResolve=resolve})
    }
    const component=(await server.ssrLoadModule('/detail-test.js')).default
    const messages=JSON.parse(await readFile(new URL('../src/locales/zh-CN.json',import.meta.url),'utf8'))
    const router=createRouter({history:createMemoryHistory(),routes:[{path:'/task/:taskId',name:'taskAgentDetail',component:{render:()=>null}},{path:'/tasks',name:'taskAgentTasks',component:{render:()=>null}}]})
    await router.push('/task/task');await router.isReady()
    app=renderer().createApp({render:()=>h(component)})
    app.use(router);app.use(createI18n({legacy:false,locale:'zh-CN',messages:{'zh-CN':messages}}))
    for(const name of ['AButton','ASpace','ASpin','ASkeleton','AAlert','AEmpty','APopconfirm','AModal','ATextarea'])app.component(name,{inheritAttrs:false,setup:(_,{attrs,slots})=>()=>h(name,attrs,slots.default?.())})
    const root={children:[]};app.mount(root);await flush();await flush()
    assert.equal(textOf(findAll(root,n=>n.type==='h1')[0]),'task')
    assert.match(textOf(findAll(root,n=>String(n.props?.class).includes('overview-cycles'))[0]),/无上限/)
    assert.doesNotMatch(textOf(findAll(root,n=>String(n.props?.class).includes('overview-cycles'))[0]),/50/)
    assert.deepEqual(calls.filter(call=>call.action==='get').map(call=>call.payload.cached),[true,false])
    assert.equal(findAll(root,n=>n.type==='ASpin')[0].props.spinning,false)
    liveResolve({status:200,data:snapshot('task')});await flush();await flush()
    const form=findAll(root,n=>n.type==='Question')[0]
    assert.equal(form.props.question.requestDigest,'digest')
    const answer={kind:'respond',target:{sessionId:'task',turnId:'task/turn/first',generation:1,interactionId:'q1',operationId:'op',attempt:1,requestDigest:'digest'},answer:{kind:'single',selected:['Markdown'],custom:[]}}
    form.props.onAnswer(answer);await flush();await flush()
    assert.equal(findAll(root,n=>n.type==='Question')[0].props.disabled,true)
    assert.match(textOf(root),/尚未确认提交结果/)
    const retry=findAll(root,n=>n.type==='AButton'&&String(n.props?.['aria-label'] || '').includes('重试提交'))[0]
    retry.props.onClick();await flush()
    const submissions=calls.filter(c=>c.action==='action')
    assert.equal(submissions.length,2)
    assert.deepEqual(submissions[0].payload,submissions[1].payload)
    assert.deepEqual(submissions[0].payload.action,answer)
    await router.push('/task/other');await flush();await flush()
    lateResolve({status:200,data:snapshot('task')});await flush();await flush()
    const headings=findAll(root,n=>n.type==='h1')
    assert.equal(textOf(headings[0]),'other')
    assert.match(textOf(findAll(root,n=>String(n.props?.class).includes('overview-cycles'))[0]),/\/ 7/)
    app.unmount();app=null
    assert.equal(timers.size,0)
  } finally {app?.unmount();await server.close();globalThis.window=originalWindow;delete globalThis.__taskAPI}
})

test('detail handles parked unknown MCP provider wait by disabling follow-up and settling via explicit cancel without reissuing MCP calls', async () => {
  const empty = 'export default { render: () => null }'
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    ...(await baseDetailModules()),
    '/detail-mcp-wait-test.js': (await componentSource('../src/views/Workspace/TaskAgent/TaskAgentDetail.vue', 'task-detail-mcp-wait')).replaceAll("'./TaskAgent", "'@/views/Workspace/TaskAgent/TaskAgent").replace("'ant-design-vue'", "'/task-message-test.js'"),
    '@/components/TextOutput.vue': empty,
    '@/views/Workspace/TaskAgent/TaskAgentTimeline.vue': empty,
    '@/views/Workspace/TaskAgent/TaskAgentWorkspace.vue': empty,
    '@/views/Workspace/TaskAgent/TaskAgentWorkflowRuns.vue': empty,
    '@/views/Workspace/TaskAgent/TaskAgentInteraction.vue': empty,
    '@/icons': 'export const Left={render:()=>null},Send=Left,Pause=Left,PlayOne=Left,HandleSquare=Left,MenuUnfoldOne=Left,Down=Left,Robot=Left,Time=Left,ListOne=Left; export const Refresh=Left,Close=Left,Delete=Left,Undo=Left,Star=Left,OffScreenOne=Left,OpenExternal=Left;',
    '@/api/taskAgent': 'export const taskAgentAPI=(action,payload)=>globalThis.__taskMcpWaitAPI(action,payload)',
    '@/utils/taskAgentPresentation': await readFile(new URL('../src/utils/taskAgentPresentation.js', import.meta.url), 'utf8'),
    '@/utils/taskAgentTimeline': await readFile(new URL('../src/utils/taskAgentTimeline.js', import.meta.url), 'utf8'),
    '/task-message-test.js': 'export const message={error:()=>{}}',
  }
  const server = await createServer({ configFile:false, root:fileURLToPath(new URL('..',import.meta.url)), plugins:[{name:'task-detail-mcp-wait-test',resolveId:id=> Object.hasOwn(modules,id)?id:undefined,load:id=>modules[id]}], server:{middlewareMode:true,hmr:false,ws:false}, optimizeDeps:{noDiscovery:true},appType:'custom' })
  const originalWindow = globalThis.window
  let app
  try {
    let settled = false
    const calls = []
    const makeData = () => ({
      task: {
        tid: 'mcp-wait-task',
        title: 'MCP Wait Task',
        status: settled ? 'INTERRUPTED' : 'FAILED',
        current_turn_id: 'mcp-wait-task/turn/1',
        config_snapshot: {
          agent_profile: { name: 'Data Agent', max_cycles: 0, permission_mode: 'auto' },
          skills: [{ skill_id: 'sk1', version: 2, name: 'sql-helper', description: 'SQL helper' }],
          mcp_tools: [{ server_id: 'srv1', server_name: 'DB Server', name: 'run_sql', namespaced_name: 'mcp__srv1__run_sql__abcd', title: 'Run SQL' }],
        },
      },
      messages: [],
      timeline: [
        { id: 't1', kind: 'tool', turn_id: 'mcp-wait-task/turn/1', tool_name: 'mcp__srv1__run_sql__abcd', display_name: 'DB Server: Run SQL', status: 'unknown', error_code: 'timeout' },
      ],
      mcp_runs: [
        { job_id: 'j1', task_id: 'mcp-wait-task', turn_id: 'mcp-wait-task/turn/1', tool_call_id: 'tc1', server_id: 'srv1', server_name: 'DB Server', tool_name: 'run_sql', namespaced_name: 'mcp__srv1__run_sql__abcd', status: 'UNKNOWN', dispatched: true, dispatch_uncertain: true, unknown_code: 'timeout', unknown_reason: 'Timed out after dispatch', artifacts: [] },
      ],
      state: { waitKind: settled ? null : 'provider', unconfirmedCount: 1 },
      todos: [],
      sync_error: false,
    })
    globalThis.window = { setTimeout: () => 1, clearTimeout: () => {} }
    globalThis.__taskMcpWaitAPI = async (action, payload) => {
      calls.push({ action, payload })
      if (action === 'get') return { status: 200, data: makeData() }
      if (action === 'action' && payload.action?.kind === 'cancel') {
        settled = true
        return { status: 200, data: makeData() }
      }
      return { status: 409, data: {} }
    }
    const component = (await server.ssrLoadModule('/detail-mcp-wait-test.js')).default
    const messages = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/task/:taskId', name: 'taskAgentDetail', component: { render: () => null } }, { path: '/tasks', name: 'taskAgentTasks', component: { render: () => null } }] })
    await router.push('/task/mcp-wait-task'); await router.isReady()
    app = renderer().createApp({ render: () => h(component) })
    app.use(router); app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } }))
    app.component('ATextarea', { props: ['value', 'disabled'], emits: ['update:value'], setup: (props, { emit, attrs }) => () => h('ATextarea', { ...attrs, value: props.value, disabled: props.disabled, 'onUpdate:value': value => emit('update:value', value) }) })
    for (const name of ['AButton', 'ASpace', 'ASpin', 'ASkeleton', 'AAlert', 'AEmpty', 'APopconfirm', 'AModal']) {
      app.component(name, { inheritAttrs: false, setup: (_, { attrs, slots }) => () => h(name, attrs, slots.default?.()) })
    }
    const root = { children: [] }; app.mount(root); await flush(); await flush()

    // While waitKind === 'provider' and active-turn MCP run is UNKNOWN:
    assert.match(textOf(root), /停止等待/)
    const textarea = () => findAll(root, n => n.type === 'ATextarea')[0]
    assert.equal(textarea().props.disabled, true)

    // Trigger explicit cancel via popconfirm confirm handler
    const popconfirm = findAll(root, n => n.type === 'APopconfirm')[0]
    assert.ok(popconfirm)
    await popconfirm.props.onConfirm()
    await flush(); await flush()

    // Settled to INTERRUPTED: cancel action was sent once, follow-up is now enabled, unconfirmed warning remains visible
    const cancelCalls = calls.filter(c => c.action === 'action')
    assert.equal(cancelCalls.length, 1)
    assert.deepEqual(cancelCalls[0].payload.action, { kind: 'cancel' })
    assert.equal(textarea().props.disabled, false)
    assert.match(findAll(root, n => n.type === 'AAlert')[0].props.message, /未确认/)
  } finally {
    app?.unmount(); await server.close(); globalThis.window = originalWindow; delete globalThis.__taskMcpWaitAPI
  }
})

test('detail approval scopes planned tool arguments to exact turnId and does not reuse old turn arguments for same tool_call_id', async () => {
  const empty = 'export default { render: () => null }'
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    ...(await baseDetailModules()),
    '/detail-approval-scope-test.js': (await componentSource('../src/views/Workspace/TaskAgent/TaskAgentDetail.vue', 'task-detail-approval-scope')).replaceAll("'./TaskAgent", "'@/views/Workspace/TaskAgent/TaskAgent").replace("'ant-design-vue'", "'/task-message-test.js'"),
    '@/components/TextOutput.vue': empty,
    '@/views/Workspace/TaskAgent/TaskAgentTimeline.vue': empty,
    '@/views/Workspace/TaskAgent/TaskAgentWorkspace.vue': empty,
    '@/views/Workspace/TaskAgent/TaskAgentWorkflowRuns.vue': empty,
    '@/views/Workspace/TaskAgent/TaskAgentInteraction.vue': 'import {h} from "vue"; export default {props:["question","busy","disabled"],emits:["answer","approve"],setup:(props,{emit})=>()=>h("ApprovalBox",{question:props.question,onApprove:decision=>emit("approve",decision)})}',
    '@/icons': 'export const Left={render:()=>null},Send=Left,Pause=Left,PlayOne=Left,HandleSquare=Left,MenuUnfoldOne=Left,Down=Left,Robot=Left,Time=Left,ListOne=Left; export const Refresh=Left,Close=Left,Delete=Left,Undo=Left,Star=Left,OffScreenOne=Left,OpenExternal=Left;',
    '@/api/taskAgent': 'export const taskAgentAPI=(action,payload)=>globalThis.__taskApprovalScopeAPI(action,payload)',
    '@/utils/taskAgentPresentation': await readFile(new URL('../src/utils/taskAgentPresentation.js', import.meta.url), 'utf8'),
    '@/utils/taskAgentTimeline': await readFile(new URL('../src/utils/taskAgentTimeline.js', import.meta.url), 'utf8'),
    '/task-message-test.js': 'export const message={error:()=>{}}',
  }
  const server = await createServer({ configFile:false, root:fileURLToPath(new URL('..',import.meta.url)), plugins:[{name:'task-detail-approval-scope',resolveId:id=> Object.hasOwn(modules,id)?id:undefined,load:id=>modules[id]}], server:{middlewareMode:true,hmr:false,ws:false}, optimizeDeps:{noDiscovery:true},appType:'custom' })
  const originalWindow = globalThis.window
  let app
  try {
    const calls = []
    globalThis.window = { setTimeout: () => 1, clearTimeout: () => {} }
    globalThis.__taskApprovalScopeAPI = async (action, payload) => {
      calls.push({ action, payload })
      return {
        status: 200,
        data: {
          task: {
            tid: 'task-dup-call',
            title: 'Duplicate Call ID Task',
            status: 'WAITING_FOR_APPROVAL',
            current_turn_id: 'task-dup-call/turn/2',
            config_snapshot: {
              agent_profile: { name: 'General', max_cycles: 0, permission_mode: 'ask' },
              mcp_tools: [{ server_id: 'srv1', server_name: 'DB', name: 'query', namespaced_name: 'mcp__srv1__query__1111', title: 'Query' }],
            },
          },
          messages: [],
          timeline: [
            { id: 't-old', kind: 'tool', turn_id: 'task-dup-call/turn/1', tool_call_id: 'call_1', tool_name: 'mcp__srv1__query__1111', display_name: 'DB: Query', status: 'success', arguments: { sql: 'SELECT old_turn' } },
            { id: 'ap-old', kind: 'approval_requested', turn_id: 'task-dup-call/turn/1', request_id: 'req_1', tool_call_id: 'call_1', tool_name: 'mcp__srv1__query__1111' },
            { id: 't-new', kind: 'tool', turn_id: 'task-dup-call/turn/2', tool_call_id: 'call_1', tool_name: 'mcp__srv1__query__1111', display_name: 'DB: Query', status: 'pending', arguments: { sql: 'SELECT current_turn_2' } },
            { id: 'ap-new', kind: 'approval_requested', turn_id: 'task-dup-call/turn/2', request_id: 'req_2', tool_call_id: 'call_1', tool_name: 'mcp__srv1__query__1111' },
          ],
          mcp_runs: [],
          state: {
            pendingInteraction: {
              kind: 'approval',
              sessionId: 'task-dup-call',
              turnId: 'task-dup-call/turn/2',
              requestId: 'req_2',
              tool_name: 'mcp__srv1__query__1111',
              display_name: 'DB: Query',
            },
          },
          todos: [],
          sync_error: false,
        },
      }
    }
    const component = (await server.ssrLoadModule('/detail-approval-scope-test.js')).default
    const messages = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/task/:taskId', name: 'taskAgentDetail', component: { render: () => null } }, { path: '/tasks', name: 'taskAgentTasks', component: { render: () => null } }] })
    await router.push('/task/task-dup-call'); await router.isReady()
    app = renderer().createApp({ render: () => h(component) })
    app.use(router); app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } }))
    for (const name of ['AButton', 'ASpace', 'ASpin', 'ASkeleton', 'AAlert', 'AEmpty', 'APopconfirm', 'AModal', 'ATextarea']) {
      app.component(name, { inheritAttrs: false, setup: (_, { attrs, slots }) => () => h(name, attrs, slots.default?.()) })
    }
    const root = { children: [] }; app.mount(root); await flush(); await flush()

    const approvalBox = findAll(root, n => n.type === 'ApprovalBox')[0]
    assert.ok(approvalBox)
    assert.deepEqual(approvalBox.props.question.arguments, { sql: 'SELECT current_turn_2' })
    await approvalBox.props.onApprove('allow')
    await flush()
    const approvalCalls = calls.filter(c => c.action === 'approval')
    assert.equal(approvalCalls.length, 1)
    assert.equal(approvalCalls[0].payload.request_id, 'req_2')
    assert.equal(approvalCalls[0].payload.turn_id, 'task-dup-call/turn/2')
  } finally {
    app?.unmount(); await server.close(); globalThis.window = originalWindow; delete globalThis.__taskApprovalScopeAPI
  }
})

test('detail shows bottom thinking indicator after live output while active, replaces send with composer stop, and hides thinking on non-thinking states', async () => {
  const empty = 'export default { render: () => null }'
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    ...(await baseDetailModules()),
    '/detail-thinking-stop-test.js': (await componentSource('../src/views/Workspace/TaskAgent/TaskAgentDetail.vue', 'task-detail-thinking-stop')).replaceAll("'./TaskAgent", "'@/views/Workspace/TaskAgent/TaskAgent").replace("'ant-design-vue'", "'/task-message-test.js'"),
    '@/components/TextOutput.vue': 'import {h} from "vue"; export default {props:["text","showCopy"],setup:props=>()=>h("LiveOutput",{text:props.text},props.text)}',
    '@/views/Workspace/TaskAgent/TaskAgentTimeline.vue': 'import {h} from "vue"; export default {setup:()=>()=>h("TimelineStub")}',
    '@/views/Workspace/TaskAgent/TaskAgentWorkspace.vue': empty,
    '@/views/Workspace/TaskAgent/TaskAgentWorkflowRuns.vue': 'import {h} from "vue"; export default {props:["runs"],setup:()=>()=>h("WorkflowRunsStub")}',
    '@/views/Workspace/TaskAgent/TaskAgentInteraction.vue': 'import {h} from "vue"; export default {props:["question","busy","disabled"],emits:["answer","approve"],setup:props=>()=>h("InteractionStub",{question:props.question})}',
    '@/icons': 'export const Left={render:()=>null},Send=Left,Pause=Left,PlayOne=Left,HandleSquare=Left,MenuUnfoldOne=Left,Down=Left,Robot=Left,Time=Left,ListOne=Left; export const Refresh=Left,Close=Left,Delete=Left,Undo=Left,Star=Left,OffScreenOne=Left,OpenExternal=Left;',
    '@/api/taskAgent': 'export const taskAgentAPI=(action,payload)=>globalThis.__taskThinkingStopAPI(action,payload)',
    '@/utils/taskAgentPresentation': await readFile(new URL('../src/utils/taskAgentPresentation.js', import.meta.url), 'utf8'),
    '@/utils/taskAgentTimeline': await readFile(new URL('../src/utils/taskAgentTimeline.js', import.meta.url), 'utf8'),
    '/task-message-test.js': 'export const message={error:()=>{}}',
  }
  const server = await createServer({ configFile:false, root:fileURLToPath(new URL('..',import.meta.url)), plugins:[{name:'task-detail-thinking-stop',resolveId:id=> Object.hasOwn(modules,id)?id:undefined,load:id=>modules[id]}], server:{middlewareMode:true,hmr:false,ws:false}, optimizeDeps:{noDiscovery:true},appType:'custom' })
  const originalWindow = globalThis.window
  let app
  try {
    const calls = []
    let currentState = {
      status: 'PROCESSING',
      liveText: 'Streaming live output chunk...',
      pendingInteraction: null,
      waitKind: null,
      mcpRuns: [],
      syncError: false,
    }
    const buildPayload = () => ({
      task: {
        tid: 'task-polish',
        title: 'Polish Task',
        status: currentState.status,
        current_turn_id: 'task-polish/turn/1',
        model: 'gpt-4.1',
        config_snapshot: {
          agent_profile: { name: 'General', max_cycles: 10, permission_mode: 'auto' },
        },
      },
      messages: [],
      timeline: [],
      workflow_runs: [],
      mcp_runs: currentState.mcpRuns,
      live: currentState.liveText ? { text: currentState.liveText } : null,
      state: {
        waitKind: currentState.waitKind,
        pendingInteraction: currentState.pendingInteraction,
        unconfirmedCount: 0,
      },
      todos: [],
      sync_error: currentState.syncError,
    })

    globalThis.window = { setTimeout: () => 1, clearTimeout: () => {} }
    globalThis.__taskThinkingStopAPI = async (action, payload) => {
      calls.push({ action, payload })
      if (action === 'action' && payload.action?.kind === 'cancel') {
        currentState.status = 'INTERRUPTED'
        currentState.liveText = ''
        currentState.pendingInteraction = null
        currentState.waitKind = null
      }
      if (action === 'action' && payload.action?.kind === 'resume') {
        currentState.status = 'PROCESSING'
        currentState.liveText = 'Resumed streaming...'
      }
      return { status: 200, data: buildPayload() }
    }

    const component = (await server.ssrLoadModule('/detail-thinking-stop-test.js')).default
    const messages = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/task/:taskId', name: 'taskAgentDetail', component: { render: () => null } }, { path: '/tasks', name: 'taskAgentTasks', component: { render: () => null } }] })
    await router.push('/task/task-polish'); await router.isReady()
    app = renderer().createApp({ render: () => h(component) })
    app.use(router); app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } }))
    for (const name of ['AButton', 'ASpace', 'ASpin', 'ASkeleton', 'AAlert', 'AEmpty', 'APopconfirm', 'AModal', 'ATextarea']) {
      app.component(name, { inheritAttrs: false, setup: (_, { attrs, slots }) => () => h(name, attrs, slots.default?.()) })
    }
    const root = { children: [] }; app.mount(root); await flush(); await flush()

    // 1. Active PROCESSING state: no .working-state, bottom .task-thinking-indicator is AFTER LiveOutput and BEFORE footer
    assert.equal(findAll(root, n => String(n.props?.class || '').includes('working-state')).length, 0)
    assert.equal( textOf(root).includes('正在处理任务'), false )
    const taskContent = findAll(root, n => String(n.props?.class || '').includes('task-content'))[0]
    assert.ok(taskContent)
    const childTypes = taskContent.children.map(c => c.props?.class || c.type)
    const liveIdx = childTypes.indexOf('LiveOutput')
    const thinkingIdx = childTypes.findIndex(v => String(v).includes('task-thinking-indicator'))
    assert.ok(liveIdx >= 0 && thinkingIdx > liveIdx, `Expected LiveOutput < Thinking, got ${JSON.stringify(childTypes)}`)
    assert.equal(findAll(taskContent, n => n.props?.class === 'follow-up-area').length, 0)
    const scroller = findAll(root, n => n.props?.class === 'detail-content')[0]
    assert.equal(findAll(scroller, n => n.props?.class === 'follow-up-area').length, 0, 'composer must not scroll with messages')
    assert.equal(findAll(root, n => n.props?.class === 'follow-up-area').length, 1)
    assert.match(textOf(findAll(root, n => String(n.props?.class || '').includes('task-thinking-indicator'))[0]), /正在思考/)

    // Ordinary Pause button is removed; only ONE Stop button in composer toolbar
    assert.equal(findAll(root, n => n.type === 'AButton' && textOf(n).includes('暂停')).length, 0)
    assert.equal(findAll(root, n => String(n.props?.class || '').includes('task-controls')).length, 0)
    const composerToolbar = findAll(root, n => String(n.props?.class || '').includes('composer-toolbar'))[0]
    const stopBtns = findAll(composerToolbar, n => n.type === 'AButton' && n.props?.['aria-label'] === '停止')
    const sendBtns = findAll(composerToolbar, n => n.type === 'AButton' && n.props?.['aria-label'] === '发送消息')
    assert.equal(stopBtns.length, 1)
    assert.equal(sendBtns.length, 0)

    // Typing and pressing Ctrl+Enter while active must NOT send follow-up
    const textarea = findAll(root, n => n.type === 'ATextarea')[0]
    assert.equal(textarea.props.disabled, true)
    textarea.props['onUpdate:value']?.(' Attempt follow-up while active ')
    await flush()
    textarea.props.onKeydown?.({ key: 'Enter', ctrlKey: true, preventDefault: () => {} })
    await flush()
    assert.equal(calls.filter(c => c.action === 'send_message').length, 0)

    // Confirming Stop in composer sends cancel action -> transitions to INTERRUPTED
    const stopPopconfirm = findAll(composerToolbar, n => n.type === 'APopconfirm')[0]
    await stopPopconfirm.props.onConfirm()
    await flush(); await flush()
    assert.equal(calls.filter(c => c.action === 'action' && c.payload.action?.kind === 'cancel').length, 1)
    assert.equal(findAll(root, n => String(n.props?.class || '').includes('task-thinking-indicator')).length, 0)
    assert.equal(findAll(composerToolbar, n => n.type === 'AButton' && n.props?.['aria-label'] === '发送消息').length, 1)

    // 2. WAITING_FOR_WORKFLOW: thinking indicator is hidden, composer still has Stop button to cancel workflow wait
    currentState.status = 'WAITING_FOR_WORKFLOW'
    await router.push('/tasks'); await flush(); await router.push('/task/task-polish'); await flush(); await flush()
    assert.equal(findAll(root, n => String(n.props?.class || '').includes('task-thinking-indicator')).length, 0)
    const wfToolbar = findAll(root, n => String(n.props?.class || '').includes('composer-toolbar'))[0]
    assert.equal(findAll(wfToolbar, n => n.type === 'AButton' && n.props?.['aria-label'] === '停止').length, 1)

    // 3. Question / Approval state: thinking indicator is hidden, TaskAgentInteraction is visible, and accessible Stop control is in task-controls
    currentState.status = 'WAITING_FOR_USER'
    currentState.pendingInteraction = { kind: 'user', sessionId: 'task-polish', turnId: 'task-polish/turn/1', prompt: 'Confirm?' }
    await router.push('/tasks'); await flush(); await router.push('/task/task-polish'); await flush(); await flush()
    assert.equal(findAll(root, n => String(n.props?.class || '').includes('task-thinking-indicator')).length, 0)
    assert.equal(findAll(root, n => n.type === 'InteractionStub').length, 1)
    const questionControls = findAll(root, n => String(n.props?.class || '').includes('task-controls'))[0]
    assert.ok(questionControls)
    const qToolbar = findAll(root, n => String(n.props?.class || '').includes('composer-toolbar'))[0]
    assert.equal(findAll(qToolbar, n => n.type === 'APopconfirm').length, 1)

    // 4. Legacy PAUSED state: thinking indicator is hidden, Resume and Stop are available
    currentState.status = 'PAUSED'
    currentState.pendingInteraction = null
    await router.push('/tasks'); await flush(); await router.push('/task/task-polish'); await flush(); await flush()
    assert.equal(findAll(root, n => String(n.props?.class || '').includes('task-thinking-indicator')).length, 0)
    const pausedControls = findAll(root, n => String(n.props?.class || '').includes('task-controls'))[0]
    const resumeBtn = findAll(pausedControls, n => n.type === 'AButton' && String(n.props?.['aria-label'] || '').includes('继续执行'))[0]
    assert.ok(resumeBtn)
    await resumeBtn.props.onClick()
    await flush(); await flush()
    assert.equal(calls.filter(c => c.action === 'action' && c.payload.action?.kind === 'resume').length, 1)
    assert.equal(findAll(root, n => String(n.props?.class || '').includes('task-thinking-indicator')).length, 1)

    // 5. Sync error hides thinking indicator
    currentState.syncError = true
    await router.push('/tasks'); await flush(); await router.push('/task/task-polish'); await flush(); await flush()
    assert.equal(findAll(root, n => String(n.props?.class || '').includes('task-thinking-indicator')).length, 0)
  } finally {
    app?.unmount(); await server.close(); globalThis.window = originalWindow; delete globalThis.__taskThinkingStopAPI
  }
})

test('detail renders runtime settings toolbar across active, question, approval, and completed states, supports live permission/model updates, same-ID uncertain retry, ModelError, and ignores stale-route responses', async () => {
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    ...(await baseDetailModules()),
    '/detail-runtime-settings-test.js': (await componentSource('../src/views/Workspace/TaskAgent/TaskAgentDetail.vue', 'task-detail-runtime-settings')).replaceAll("'./TaskAgent", "'@/views/Workspace/TaskAgent/TaskAgent").replace("'ant-design-vue'", "'/task-message-test.js'"),
    '@/views/Workspace/TaskAgent/TaskAgentInteraction.vue': 'import {h} from "vue"; export default {props:["question","busy","disabled"],emits:["answer","approve"],setup:(props,{emit})=>()=>h("InteractionBox",{question:props.question,disabled:props.disabled,onApprove:d=>emit("approve",d),onAnswer:a=>emit("answer",a)})}',
    '@/api/taskAgent': 'export const taskAgentAPI=(action,payload)=>globalThis.__taskRuntimeSettingsAPI(action,payload)',
  }
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)), plugins: [{ name: 'task-detail-runtime-settings', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }], server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  const originalWindow = globalThis.window
  let app
  try {
    const calls = []
    globalThis.__catalogLoaded = 0
    globalThis.__msgSuccess = []
    globalThis.__msgWarnings = []
    globalThis.__msgErrors = []

    const stateByTask = {
      'task-live': {
        status: 'PROCESSING',
        pendingInteraction: null,
        runtime_settings: {
          revision: 1,
          last_change_id: '',
          permission_mode: 'ask',
          model_provider: 'Local',
          model: 'gpt-4.1',
          reasoning_effort: 'default',
          context_length: 128000,
          pending_change_id: null,
        },
        token_usage: { latest_input_tokens: 16000, cache_read_tokens: 8000, cache_input_tokens: 16000, reported_calls: 1, cache_missing_calls: 0 },
      },
      'task-other': {
        status: 'COMPLETED',
        pendingInteraction: null,
        runtime_settings: {
          revision: 3,
          last_change_id: '',
          permission_mode: 'full',
          model_provider: 'Local',
          model: 'claude-sonnet',
          reasoning_effort: 'high',
          context_length: 200000,
          pending_change_id: null,
        },
        token_usage: null,
      },
    }

    const buildTaskPayload = tid => {
      const s = stateByTask[tid]
      return {
        task: {
          tid,
          title: `Task ${tid}`,
          status: s.status,
          current_turn_id: `${tid}/turn/1`,
          model_provider: 'Local',
          model: 'gpt-4.1',
          reasoning_effort: 'default',
          config_snapshot: {
            context_length: 64000,
            agent_profile: { name: 'General', max_cycles: 10, permission_mode: 'ask' },
          },
        },
        runtime_settings: { ...s.runtime_settings },
        token_usage: s.token_usage,
        messages: [],
        timeline: [],
        workflow_runs: [],
        mcp_runs: [],
        live: s.status === 'PROCESSING' ? { text: 'Working...' } : null,
        state: {
          waitKind: null,
          pendingInteraction: s.pendingInteraction,
          unconfirmedCount: 0,
        },
        todos: [],
        sync_error: s.sync_error || false,
        start_pending: s.start_pending || false,
        start_model_failure: s.start_model_failure || null,
      }
    }

    let settingsHandler = async payload => {
      const s = stateByTask[payload.task_id]
      s.runtime_settings = {
        ...s.runtime_settings,
        revision: s.runtime_settings.revision + 1,
        last_change_id: payload.request_id,
        ...(payload.permission_mode ? { permission_mode: payload.permission_mode } : {}),
        ...(payload.model ? { model_provider: payload.model_provider, model: payload.model, reasoning_effort: payload.reasoning_effort || 'default' } : {}),
      }
      return { status: 200, data: buildTaskPayload(payload.task_id) }
    }

    globalThis.window = { setTimeout: () => 1, clearTimeout: () => {} }
    globalThis.__taskRuntimeSettingsAPI = async (action, payload) => {
      calls.push({ action, payload: JSON.parse(JSON.stringify(payload || {})) })
      if (action === 'get') return { status: 200, data: buildTaskPayload(payload.task_id) }
      if (action === 'update_runtime_settings') return settingsHandler(payload)
      return { status: 200, data: {} }
    }

    const component = (await server.ssrLoadModule('/detail-runtime-settings-test.js')).default
    const messages = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
    const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/task/:taskId', name: 'taskAgentDetail', component: { render: () => null } }, { path: '/tasks', name: 'taskAgentTasks', component: { render: () => null } }] })
    await router.push('/task/task-live'); await router.isReady()
    app = renderer().createApp({ render: () => h(component) })
    app.use(router); app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } }))
    for (const name of ['AButton', 'ASpace', 'ASpin', 'ASkeleton', 'AAlert', 'AEmpty', 'APopconfirm', 'AModal', 'ATextarea']) {
      app.component(name, { inheritAttrs: false, setup: (_, { attrs, slots }) => () => h(name, attrs, slots.default?.()) })
    }
    const root = { children: [] }; app.mount(root); await flush(); await flush()

    // 1. Model catalog loaded on mount; while active (PROCESSING), Permissions + ModelPicker are NOT disabled, ContextUsage compaction IS disabled
    assert.ok(globalThis.__catalogLoaded >= 1)
    const perm = () => findAll(root, n => n.type === 'PermissionsStub')[0]
    const picker = () => findAll(root, n => n.type === 'ModelPickerStub')[0]
    const ctxUsage = () => findAll(root, n => n.type === 'ContextUsageStub')[0]
    const rightGroup = () => findAll(root, n => String(n.props?.class || '').includes('composer-right-actions'))[0]

    assert.ok(perm() && picker() && ctxUsage() && rightGroup())
    assert.equal(perm().props.modelValue, 'ask')
    assert.equal(perm().props.disabled, false, 'Active execution must not disable TaskAgentPermissions')
    assert.equal(picker().props.model, 'gpt-4.1')
    assert.equal(picker().props.disabled, false, 'Active execution must not disable ModelPicker')
    assert.equal(ctxUsage().props.taskId, 'task-live')
    assert.equal(ctxUsage().props.contextWindow, 128000)
    assert.equal(ctxUsage().props.disabled, true, 'Active execution disables compaction in ContextUsage while keeping popover readable')

    stateByTask['task-live'].status = 'PENDING'
    stateByTask['task-live'].start_pending = true
    ctxUsage().props.onRefresh()
    await flush(); await flush()
    assert.match(textOf(root), /正在启动 Agent/)
    assert.equal(perm().props.disabled, true)
    assert.equal(picker().props.disabled, true)
    assert.equal(findAll(rightGroup(), n => n.type === 'AButton' && n.props?.['aria-label'] === '停止')[0].props.disabled, true)
    assert.equal(findAll(root, n => String(n.props?.class || '').includes('sync-notice')).length, 0)
    stateByTask['task-live'].start_pending = false
    stateByTask['task-live'].sync_error = true
    stateByTask['task-live'].start_model_failure = { category: 'credentials_missing' }
    ctxUsage().props.onRefresh()
    await flush(); await flush()
    assert.match(textOf(root), /尚未成功启动/)
    assert.equal(findAll(root, n => n.type === 'ModelErrorStub')[0].props.failure.category, 'credentials_missing')
    stateByTask['task-live'].sync_error = false
    stateByTask['task-live'].start_model_failure = null

    // 2. Approval / Question state: toolbar remains rendered and enabled, single Stop button in composer-right-actions, and question.permission_mode uses latest runtimeSettings
    stateByTask['task-live'].status = 'WAITING_FOR_APPROVAL'
    stateByTask['task-live'].pendingInteraction = {
      kind: 'approval',
      sessionId: 'task-live',
      turnId: 'task-live/turn/1',
      requestId: 'req_ap_1',
      tool_name: 'bash',
    }
    ctxUsage().props.onRefresh()
    await flush(); await flush()

    const interactionBox = () => findAll(root, n => n.type === 'InteractionBox')[0]
    assert.ok(interactionBox())
    assert.equal(interactionBox().props.question.permission_mode, 'ask')
    assert.equal(perm().props.disabled, false)
    assert.equal(picker().props.disabled, false)
    assert.equal(findAll(rightGroup(), n => n.type === 'AButton' && n.props?.['aria-label'] === '停止').length, 1)

    // Change permission_mode during pending approval: updates runtime_settings and question.permission_mode while preserving pending approval
    await perm().props.onChange('auto')
    await flush(); await flush()
    const permCall = calls.filter(c => c.action === 'update_runtime_settings').at(-1)
    assert.ok(permCall)
    assert.equal(permCall.payload.task_id, 'task-live')
    assert.equal(permCall.payload.expected_revision, 1)
    assert.equal(permCall.payload.permission_mode, 'auto')
    assert.equal(perm().props.modelValue, 'auto')
    assert.equal(interactionBox().props.question.permission_mode, 'auto')
    assert.equal(interactionBox().props.question.requestId, 'req_ap_1')

    // 3. Completed state: settings toolbar and ContextUsage compaction are enabled
    stateByTask['task-live'].status = 'COMPLETED'
    stateByTask['task-live'].pendingInteraction = null
    ctxUsage().props.onRefresh()
    await flush(); await flush()
    assert.equal(perm().props.disabled, false)
    assert.equal(picker().props.disabled, false)
    assert.equal(ctxUsage().props.disabled, false)

    // 4. Uncertain 503 failure on model change preserves pendingSettings and retries with exact same request_id + expected_revision
    settingsHandler = async () => ({ status: 503, data: {} })
    const firstModelOk = await picker().props.saveSelection({ model_provider: 'Local', model: 'claude-sonnet', model_preference: 'custom', reasoning_effort: 'high' })
    await flush()
    assert.equal(firstModelOk, false)
    assert.equal(perm().props.disabled, true, 'Pending uncertain settings must disable competing edits')
    assert.equal(picker().props.disabled, true)
    assert.match(textOf(root), /设置保存结果尚未确认/)
    const firstModelPayload = calls.filter(c => c.action === 'update_runtime_settings').at(-1).payload

    // Retry button sends exact same request_id and expected_revision
    settingsHandler = async payload => {
      const s = stateByTask[payload.task_id]
      s.runtime_settings = {
        ...s.runtime_settings,
        revision: s.runtime_settings.revision + 1,
        last_change_id: payload.request_id,
        model_provider: payload.model_provider,
        model: payload.model,
        reasoning_effort: payload.reasoning_effort,
      }
      return { status: 200, data: buildTaskPayload(payload.task_id) }
    }
    const retryBtn = findAll(root, n => n.type === 'AButton' && String(n.props?.['aria-label'] || '').includes('重试保存设置'))[0]
    assert.ok(retryBtn)
    await retryBtn.props.onClick()
    await flush(); await flush()
    const retryModelPayload = calls.filter(c => c.action === 'update_runtime_settings').at(-1).payload
    assert.deepEqual(retryModelPayload, firstModelPayload, 'Retry must reuse exact request_id and expected_revision')
    assert.equal(picker().props.model, 'claude-sonnet')
    assert.equal(picker().props.reasoningEffort, 'high')
    assert.equal(perm().props.disabled, false)

    // 5. Definitive 400 failure with model_failure renders TaskAgentModelError and clears pendingSettings
    settingsHandler = async () => ({
      status: 400,
      data: { model_failure: { category: 'configuration', parameter: 'reasoning_effort' } },
    })
    const badModelOk = await picker().props.saveSelection({ model_provider: 'Local', model: 'gpt-4.1', model_preference: 'custom', reasoning_effort: 'default' })
    await flush()
    assert.equal(badModelOk, false)
    const modelErrorStub = findAll(root, n => n.type === 'ModelErrorStub')[0]
    assert.ok(modelErrorStub, 'Expected TaskAgentModelError to render when model_failure is returned')
    assert.equal(modelErrorStub.props.failure.parameter, 'reasoning_effort')
    assert.equal(perm().props.disabled, false, 'Definitive 400 failure must clear pendingSettings')

    // 6. Stale-route settings response is ignored after switching to another task
    let resolveLateSettings
    settingsHandler = () => new Promise(resolve => { resolveLateSettings = resolve })
    const inflightPromise = perm().props.onChange('full')
    await flush()
    await router.push('/task/task-other')
    await flush(); await flush()
    assert.equal(picker().props.model, 'claude-sonnet')
    assert.equal(perm().props.modelValue, 'full')

    resolveLateSettings({
      status: 200,
      data: {
        ...buildTaskPayload('task-live'),
        runtime_settings: {
          revision: 99,
          last_change_id: 'stale',
          permission_mode: 'ask',
          model_provider: 'Local',
          model: 'gpt-4.1',
          reasoning_effort: 'default',
          context_length: 128000,
          pending_change_id: null,
        },
      },
    })
    await inflightPromise
    await flush()
    assert.equal(picker().props.model, 'claude-sonnet', 'Stale settings response from previous route must be ignored')
    assert.equal(perm().props.modelValue, 'full')
  } finally {
    app?.unmount(); await server.close(); globalThis.window = originalWindow
    delete globalThis.__taskRuntimeSettingsAPI; delete globalThis.__catalogLoaded
    delete globalThis.__msgSuccess; delete globalThis.__msgWarnings; delete globalThis.__msgErrors
  }
})