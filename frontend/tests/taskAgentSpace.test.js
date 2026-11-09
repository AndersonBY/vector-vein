import { iconButtonFixture } from './taskAgentButtonFixture.js'
import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick, ref } from 'vue'
import { createI18n } from 'vue-i18n'
import { createMemoryHistory, createRouter } from 'vue-router'
import { createServer } from 'vite'
import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'
import { taskAgentSpaceRoute } from '../src/router/modules/taskAgent.js'

test('task agent parent route always opens the workbench', () => {
  assert.deepEqual(taskAgentSpaceRoute.redirect, { name: 'taskAgentWorkbench' })
})

test('application router exposes Task Agent and shared workspaces without old chat routes', async () => {
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{
      name: 'memory-router',
      transform(source, id) {
        if (id.replaceAll('\\', '/').includes('/src/router/')) {
          return source.replaceAll('createWebHashHistory', 'createMemoryHistory')
            .replace("'@/layouts'", "'virtual:layout'")
        }
      },
      resolveId(id) { if (id === 'virtual:layout') return '\0layout' },
      load(id) {
        if (id === '\0layout') return 'export const WorkspaceLayout = { render: () => null }'
        if (/\/src\/views\/.*\.vue$/.test(id.replaceAll('\\', '/'))) return 'export default { render: () => null }'
      },
    }],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  try {
    const { default: router } = await server.ssrLoadModule('/src/router/index.js')
    for (const name of ['taskAgentWorkbench', 'taskAgentProject', 'taskAgentDetail', 'taskAgentCreate', 'taskAgentEdit', 'WorkflowSpaceMain', 'DataSpaceMain', 'settings']) {
      assert.ok(router.hasRoute(name), name)
    }
    for (const name of ['taskAgentProjects', 'myAgents', 'publicAgents', 'agentDetail', 'chatSpace', 'conversationNew', 'conversationDetail']) {
      assert.equal(router.hasRoute(name), false, name)
    }
    assert.ok(router.getRoutes().every(route => !route.path.startsWith('/agent')))
    await router.push('/')
    await router.isReady()
    assert.equal(router.currentRoute.value.name, 'taskAgentWorkbench')
    assert.equal(router.currentRoute.value.path, '/task-agent/workbench')
    assert.equal(router.currentRoute.value.meta.headerKey, 'task-agent')
  } finally { await server.close() }
})

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
  createElement: type => ({ type, props: {}, children: [], parent: null }),
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

for (const scope of ['standalone', 'project-page', 'project-picker', 'picker-reset', 'profile-default', 'scheduled-refresh']) test(`workbench submits a goal in ${scope}`, async () => {
  const withProject = ['project-page', 'project-picker'].includes(scope)
  const onProjectPage = scope === 'project-page'
  const emptyComponent = 'export default { render: () => null }'
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    '/task-agent-workbench-test.js': await componentSource('../src/views/Workspace/TaskAgent/TaskAgentWorkbench.vue', 'task-workbench'),
    '@/components/ModelPicker.vue': emptyComponent,
    '@/components/taskAgent/AgentPicker.vue': 'import {h} from "vue";export default{props:["modelValue","disabled"],emits:["update:modelValue","change"],setup:(props,{emit})=>()=>h("AgentPicker",{value:props.modelValue,disabled:props.disabled,onChange:value=>{emit("update:modelValue",value);emit("change",value)}})}',
    '@/views/Workspace/TaskAgent/TaskAgentProjectEditor.vue': emptyComponent,
    '@/views/Workspace/TaskAgent/TaskAgentProjectPicker.vue': 'import {h} from "vue";export default{props:["modelValue","disabled"],emits:["update:modelValue"],setup:(props,{emit})=>()=>h("ProjectPicker",{value:props.modelValue,onChange:value=>emit("update:modelValue",value)})}',
    '@/views/Workspace/TaskAgent/TaskAgentWorkspace.vue': 'import {h} from "vue";export default{props:["projectId","project","visible"],setup:props=>()=>h("ProjectWorkspace",{projectId:props.projectId,visible:props.visible})}',
    '@/views/Workspace/TaskAgent/TaskAgentPermissions.vue': 'import {h} from "vue"; export default {props:["modelValue"],emits:["update:modelValue"],setup:(props,{emit})=>()=>h("Permissions",{value:props.modelValue,onChange:value=>emit("update:modelValue",value)})}',
    '@/views/Workspace/TaskAgent/TaskAgentModelError.vue': 'import {h} from "vue"; export default {props:["failure"],setup:props=>()=>h("ModelError",{category:props.failure.category})}',
    '@/components/workspace/UploaderFieldUse.vue': emptyComponent,
    '@/components/workspace/AttachmentsList.vue': emptyComponent,
    '@/icons': 'export const DoubleRight={render:()=>null},Link=DoubleRight,Robot=DoubleRight,Send=DoubleRight,MenuUnfoldOne=DoubleRight,Edit=DoubleRight,Search=DoubleRight,Tool=DoubleRight; export const Refresh=DoubleRight,Close=DoubleRight,Delete=DoubleRight,Undo=DoubleRight,Star=DoubleRight,OffScreenOne=DoubleRight,Down=DoubleRight,OpenExternal=DoubleRight;',
    '@/utils/taskAgentErrors': await readFile(new URL('../src/utils/taskAgentErrors.js', import.meta.url), 'utf8'),
    '@/api/taskAgent': 'export const taskAgentAPI=(action,payload)=>globalThis.__taskAgentAPI(action,payload)',
    '@/utils/common': 'export const getChatModelOptions=()=>globalThis.__modelOptions',
    '@/utils/modelPreferences': 'export const validModelPair=(options,provider,model)=>options.some(p=>p.value===provider&&p.children.some(m=>m.value===model))',
    '@/stores/modelCatalog': 'export const useModelCatalogStore=()=>({ensureLoaded:async()=>{}})',
    '@/stores/userSettings': 'export const useUserSettingsStore=()=>({setting:{data:{model_preferences:{default:{model_provider:"Local",model:"mock"}}}}})',
    '@/utils/taskAgentPresentation': await readFile(new URL('../src/utils/taskAgentPresentation.js', import.meta.url), 'utf8'),
    'ant-design-vue': 'export const message={error:value=>globalThis.__errors.push(value)}',
  }
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'task-workbench-test', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }],
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  const originalWindow = globalThis.window
  const pollTimers = new Map(), focusListeners = new Map()
  globalThis.window = { ...originalWindow,
    setTimeout: (callback, ms) => { if (scope === 'scheduled-refresh' && ms === 5000) { const id = Symbol(); pollTimers.set(id, callback); return id }; return setTimeout(callback, ms) },
    clearTimeout: id => { if (pollTimers.has(id)) pollTimers.delete(id); else clearTimeout(id) },
    addEventListener: (name, callback) => focusListeners.set(name, callback),
    removeEventListener: name => focusListeners.delete(name),
  }
  let app
  try {
    const calls = []
    const projectDeletion = ref(null)
    let rejectModel = true
    let recentTasks = scope === 'scheduled-refresh' ? [] : [{ tid: 'old-task', title: '旧任务', goal: '已有目标', status: 'COMPLETED', updated_at: '2026-11-02T01:00:00Z' }]
    globalThis.__errors = []
    globalThis.__modelOptions = [{ value: 'Local', children: [{ value: 'mock', label: 'Mock model' }, { value: 'profile-model', label: 'Profile model' }] }]
    globalThis.__taskAgentAPI = async (action, payload) => {
      calls.push({ action, payload })
      if (action === 'mcp_tools') return { status: 200, data: { tools: [{ tool_id: 'mcp__srv__echo__1111', namespaced_name: 'mcp__srv__echo__1111', server_id: 'srv', server_name: 'Demo Server', name: 'echo', title: 'Echo Tool' }, { tool_id: 'mcp__srv__read__2222', namespaced_name: 'mcp__srv__read__2222', server_id: 'srv', server_name: 'Demo Server', name: 'read', title: 'Read Tool' }] } }
      if (action === 'profiles' && scope === 'profile-default') return { status: 200, data: { agents: [{ agent_id: 'configured', name: 'Configured Agent', permission_mode: 'ask', model_provider: 'Local', model: 'profile-model', reasoning_effort: 'low', mcp_tool_ids: ['mcp__srv__echo__1111'] }, { agent_id: 'general', name: 'General Agent', permission_mode: 'auto', mcp_tool_ids: [] }] } }
      if (action === 'project') return { status: 200, data: { project_id: 'project-one', name: 'Project context', roots: ['E:/project'], folders: [{ id: '0', path: 'E:/project', available: true }] } }
      if (action === 'create' && rejectModel) return { status: 400, data: { model_failure: { category: 'credentials_missing' } } }
      if (action === 'create') return { status: 200, data: { task: { tid: 'new-task' } } }
      return { status: 200, data: { sync_error: false, tasks: structuredClone(recentTasks) } }
    }
    const component = (await server.ssrLoadModule('/task-agent-workbench-test.js')).default
    const messages = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
    const router = createRouter({ history: createMemoryHistory(), routes: [
      { path: '/', name: 'taskAgentWorkbench', component: { render: () => null } },
      { path: '/projects/:projectId', name: 'taskAgentProject', component: { render: () => null } },
      { path: '/tasks', name: 'taskAgentTasks', component: { render: () => null } },
      { path: '/task/:taskId', name: 'taskAgentDetail', component: { render: () => null } },
      { path: '/skills', name: 'taskAgentSkills', component: { render: () => null } },
      { path: '/mcp', name: 'taskAgentMCP', component: { render: () => null } },
      { path: '/settings', name: 'settings', component: { render: () => null } },
    ] })
    await router.push(scope === 'profile-default' ? '/?agent_id=configured' : onProjectPage ? '/projects/project-one' : '/')
    await router.isReady()
    app = renderer().createApp({ render: () => h(component) })
    app.provide('taskAgentProjectDeletion', projectDeletion)
    app.use(router)
    app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } }))
    app.component('ATextarea', { props: ['value'], emits: ['update:value'], setup: (props, { emit, attrs }) => () => h('ATextarea', { ...attrs, value: props.value, 'onUpdate:value': value => emit('update:value', value) }) })
    app.component('APopover', { inheritAttrs: false, setup: (_props, { attrs, slots }) => () => h('APopover', attrs, [slots.default?.(), ...(attrs.open ? [slots.content?.()] : [])]) })
    app.component('ACheckbox', { inheritAttrs: false, setup: (_props, { attrs, slots }) => () => h('ACheckbox', attrs, slots.default?.()) })
    for (const name of ['AButton', 'ATooltip', 'ASpin', 'AEmpty', 'ASelect', 'AAlert', 'AInput', 'ASpace']) {
      app.component(name, { inheritAttrs: false, setup: (_props, { attrs, slots }) => () => h(name, attrs, slots.default?.()) })
    }
    const root = { children: [] }
    app.mount(root)
    await flush()
    await flush()
    assert.match(textOf(root), onProjectPage ? /Project context/ : /今天要完成什么/)
    if (scope === 'scheduled-refresh') {
      const tick = async () => { assert.equal(pollTimers.size, 1); const [id, callback] = [...pollTimers][0]; pollTimers.delete(id); callback(); await flush(); await flush() }
      assert.equal(findAll(root, node => node.props?.class === 'recent-task').length, 0)
      assert.equal(pollTimers.size, 1, 'an empty workbench keeps polling for scheduled tasks')
      recentTasks = [{ tid: 'scheduled', title: '定时启动的任务', status: 'PROCESSING' }]
      await tick()
      assert.match(textOf(root), /定时启动的任务/)
      recentTasks[0].status = 'COMPLETED'
      await tick()
      assert.match(textOf(root), /已完成/)
      assert.equal(pollTimers.size, 1, 'completed lists keep polling')
      recentTasks = []
      await tick()
      assert.equal(findAll(root, node => node.props?.class === 'recent-task').length, 0)
      recentTasks = [{ tid: 'next-scheduled', title: '恢复窗口后出现的任务', status: 'COMPLETED' }]
      focusListeners.get('focus')(); await flush(); await flush()
      assert.match(textOf(root), /恢复窗口后出现的任务/)
      assert.equal(calls.filter(call => call.action === 'list').at(-1).payload.summary, true)
      assert.equal(calls.filter(call => call.action === 'list').at(-1).payload.sort_by, 'updated_at')
      recentTasks = null
      await tick()
      assert.match(textOf(root), /恢复窗口后出现的任务/)
      assert.equal(findAll(root, node => node.props?.class === 'sync-notice').length, 1)
      recentTasks = []
      await tick()
      assert.equal(findAll(root, node => node.props?.class === 'sync-notice').length, 0)
    } else assert.match(textOf(root), /旧任务/)
    assert.doesNotMatch(textOf(root), /执行引擎|vv-agent|App Server|Contract/)
    assert.equal(findAll(root, node => node.type === 'ProjectWorkspace').length, onProjectPage ? 1 : 0)
    if (onProjectPage) {
      const back = findAll(root, node => node.type === 'a' && node.props.class === 'project-back')[0]
      assert.equal(back.props.href, '/')
      assert.match(textOf(back), /工作台/)
      assert.doesNotMatch(textOf(root), /描述目标，Agent 会在这些项目目录中执行任务并保存修改/)
      const edit = findAll(root, node => node.type === 'AButton' && node.props['aria-label'] === '编辑项目')[0]
      assert(edit);assert.doesNotMatch(textOf(edit), /编辑项目/)
      const separator = () => findAll(root, node => node.props?.role === 'separator')[0]
      assert.equal(separator().props['aria-valuenow'],45)
      separator().props.onKeydown({key:'ArrowRight',preventDefault(){}});await nextTick()
      assert.equal(separator().props['aria-valuenow'],47)
      const search = findAll(root, node => node.type === 'AInput')[0]
      search.props['onUpdate:value']('报告');await new Promise(resolve=>setTimeout(resolve,300));await flush()
      const query = calls.filter(call=>call.action==='list').at(-1).payload
      assert.equal(query.search,'报告');assert.equal(query.project_id,'project-one');assert.equal(query.limit,20)
      search.props['onUpdate:value']('');await new Promise(resolve=>setTimeout(resolve,300));await flush()
      assert.equal(calls.filter(call=>call.action==='list').at(-1).payload.search,undefined)
    }
    if (!onProjectPage) assert.equal(findAll(root, node => node.type === 'ProjectPicker')[0].props.value, '')
    if (['project-picker', 'picker-reset'].includes(scope)) {
      findAll(root, node => node.type === 'ATextarea')[0].props['onUpdate:value']('保留已输入的目标')
      const picker = findAll(root, node => node.type === 'ProjectPicker')[0]
      picker.props.onChange('project-one'); await flush(); await flush()
      assert.equal(findAll(root, node => node.type === 'ATextarea')[0].props.value, '保留已输入的目标')
      assert.equal(findAll(root, node => node.type === 'ProjectWorkspace').length, 0)
      if (scope === 'picker-reset') {
        projectDeletion.value={project_id:'project-one',task_ids:['old-task']};await flush();await flush()
        assert.equal(findAll(root,node=>node.type==='ProjectPicker')[0].props.value,'')
        assert.equal(findAll(root,node=>node.type==='ATextarea')[0].props.value,'保留已输入的目标')
      }
    }

    const permissions = findAll(root, node => node.type === 'Permissions')[0]
    assert.equal(permissions.props.value, scope === 'profile-default' ? 'ask' : 'auto')
    permissions.props.onChange('full')
    await nextTick()
    const input = findAll(root, node => node.type === 'ATextarea')[0]
    input.props['onUpdate:value']('整理测试报告')
    await nextTick()
    const send = findAll(root, node => node.type === 'AButton' && String(node.props.class).includes('send-task'))[0]
    await send.props.onClick()
    await flush()
    assert.equal(findAll(root, node => node.type === 'ModelError')[0].props.category, 'credentials_missing')
    assert.equal(router.currentRoute.value.name, onProjectPage ? 'taskAgentProject' : 'taskAgentWorkbench')
    rejectModel = false
    await send.props.onClick()
    await flush()
    const created = calls.find(call => call.action === 'create')
    assert.equal(created.payload.goal, '整理测试报告')
    assert.equal(created.payload.model_provider, 'Local')
    assert.equal(created.payload.model, scope === 'profile-default' ? 'profile-model' : 'mock')
    if (scope === 'profile-default') { assert.equal(created.payload.agent_id, 'configured'); assert.equal(created.payload.reasoning_effort, 'low') }
    assert.equal(created.payload.permission_mode, 'full')
    assert.equal(created.payload.project_id, withProject ? 'project-one' : undefined)
    assert(calls.some(call => call.action === 'list' && call.payload.project_id === (withProject ? 'project-one' : undefined)))
    assert.equal(router.currentRoute.value.name, 'taskAgentDetail')
    assert.equal(router.currentRoute.value.params.taskId, 'new-task')
    assert.deepEqual(globalThis.__errors, [])
    app.unmount()
    if (scope === 'scheduled-refresh') { assert.equal(pollTimers.size, 0); assert.equal(focusListeners.size, 0) }
    app = null
  } finally {
    app?.unmount()
    await server.close()
    delete globalThis.__taskAgentAPI
    delete globalThis.__modelOptions
    delete globalThis.__errors
    globalThis.window = originalWindow
  }
})


test('project editor uses the native picker, keeps cancelled selections and submits ordered roots', async () => {
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    '/project-editor-test.js': await componentSource('../src/views/Workspace/TaskAgent/TaskAgentProjectEditor.vue', 'project-editor'),
    '@/icons': 'export const FolderOpen={render:()=>null},Plus=FolderOpen,Close=FolderOpen; export const Refresh=FolderOpen,Delete=FolderOpen,Undo=FolderOpen,Star=FolderOpen,OffScreenOne=FolderOpen,Down=FolderOpen,OpenExternal=FolderOpen;',
    '@/api/taskAgent': 'export const taskAgentAPI=(action,payload)=>globalThis.__projectAPI(action,payload)',
  }
  const server = await createServer({configFile:false,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{name:'project-editor-test',resolveId:id=> Object.hasOwn(modules,id)?id:undefined,load:id=>modules[id]}],server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true},appType:'custom'})
  const originalWindow = globalThis.window
  let app
  try {
    const choices = ['E:/first folder', '', 'E:/second folder', 'E:/first folder']
    const calls = [], saved = []
    globalThis.window = {pywebview:{api:{open_folder_dialog:async()=>choices.shift()}}}
    globalThis.__projectAPI = async(action,payload)=>{calls.push({action,payload});return{status:200,data:{...payload,name:'second folder'}}}
    const component=(await server.ssrLoadModule('/project-editor-test.js')).default
    const messages=JSON.parse(await readFile(new URL('../src/locales/zh-CN.json',import.meta.url),'utf8'))
    app=renderer().createApp({render:()=>h(component,{open:true,onSaved:project=>saved.push(project)})})
    app.use(createI18n({legacy:false,locale:'zh-CN',messages:{'zh-CN':messages}}))
    for(const name of ['AModal','AForm','AFormItem','AInput','AButton','AAlert','ATooltip'])app.component(name,{inheritAttrs:false,setup:(_,{attrs,slots})=>()=>h(name,attrs,slots.default?.())})
    const root={children:[]};app.mount(root);await flush()
    const add=()=>findAll(root,node=>node.type==='AButton'&&node.props.class==='add-project-folder')[0]
    assert.equal(findAll(root,node=>node.type==='AModal')[0].props['ok-button-props'].disabled,true)
    for (let index=0;index<4;index++) {await add().props.onClick();await flush()}
    assert.equal(findAll(root,node=>node.props?.class==='project-folder-row').length,2)
    const primary=findAll(root,node=>node.type==='AButton'&&String(node.props?.['aria-label'] || '').includes('设为默认'))[0]
    primary.props.onClick();await flush()
    assert.equal(findAll(root,node=>node.type==='AInput')[0].props.placeholder,'second folder')
    await findAll(root,node=>node.type==='AModal')[0].props.onOk();await flush()
    assert.deepEqual(calls[0].payload.roots,['E:/second folder','E:/first folder'])
    assert.equal(calls[0].payload.name,'')
    assert.equal(saved[0].name,'second folder')
  } finally {app?.unmount();await server.close();globalThis.window=originalWindow;delete globalThis.__projectAPI}
})

test('sidebar expands project tasks, paginates, pins and keeps task navigation in the project', async () => {
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    '/project-navigation-test.js': (await componentSource('../src/views/Workspace/TaskAgent/TaskAgentProjectNavigation.vue', 'project-navigation')).replaceAll("'ant-design-vue'", "'virtual:project-antd'"),
    '@/icons': 'export const FolderOpen={render:()=>null},Plus=FolderOpen,Down=FolderOpen,Edit=FolderOpen,ListOne=FolderOpen,LoadingFour=FolderOpen,Refresh=FolderOpen,Delete=FolderOpen; export const Close=FolderOpen,Undo=FolderOpen,Star=FolderOpen,OffScreenOne=FolderOpen,OpenExternal=FolderOpen;',
    '@/api/taskAgent': 'export const taskAgentAPI=(action,payload)=>globalThis.__navigationAPI(action,payload)',
    'virtual:project-antd': 'import {ref} from "vue";export const theme={useToken:()=>({token:ref({})})},message={success:()=>{}}',
    '@/utils/taskAgentTimeline': await readFile(new URL('../src/utils/taskAgentTimeline.js', import.meta.url), 'utf8'),
    '@/utils/taskAgentPresentation': await readFile(new URL('../src/utils/taskAgentPresentation.js', import.meta.url), 'utf8'),
    '@/views/Workspace/TaskAgent/TaskAgentProjectEditor.vue': 'import {h} from "vue";export default {props:["open","project"],setup:props=>()=>h("ProjectEditor",{open:props.open,project:props.project})}',
  }
  const server = await createServer({configFile:false,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{name:'project-navigation-test',resolveId:id=> Object.hasOwn(modules,id)?id:undefined,load:id=>modules[id]}],server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true},appType:'custom'})
  const originalWindow = globalThis.window, storageDescriptor = Object.getOwnPropertyDescriptor(globalThis, 'localStorage')
  const storage = new Map(), timers = new Map()
  let app, timerId = 0
  try {
    Object.defineProperty(globalThis,'localStorage',{configurable:true,value:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)}})
    globalThis.window={setTimeout:fn=>{timers.set(++timerId,fn);return timerId},clearTimeout:id=>timers.delete(id)}
    const calls = [], active = ref('p1')
    const projects = [{project_id:'p1',name:'前端工程',updated_at:'v1',task_count:7,roots:['E:/app'],folders:[{id:'0',path:'E:/app',available:true}]},{project_id:'p2',name:'后端工程',updated_at:'v2',task_count:0,roots:['E:/api'],folders:[{id:'0',path:'E:/api',available:true}]}]
    const tasks = Array.from({length:7},(_,index)=>({tid:`task-${index}`,title:`项目任务 ${index}`,status:'COMPLETED'}))
    let rejectTasks = false
    globalThis.__navigationAPI=async(action,payload)=>{
      calls.push({action,payload})
      if(action==='projects')return{status:200,data:{projects}}
      if(rejectTasks && payload.project_id==='p2')return{status:503}
      return{status:200,data:{tasks:payload.project_id==='p1'?tasks.slice(payload.offset,payload.offset+payload.limit):[],sync_error:false}}
    }
    const component=(await server.ssrLoadModule('/project-navigation-test.js')).default
    const messages=JSON.parse(await readFile(new URL('../src/locales/zh-CN.json',import.meta.url),'utf8'))
    const router=createRouter({history:createMemoryHistory(),routes:[{path:'/',name:'taskAgentWorkbench',component:{render:()=>null}},{path:'/projects/:projectId',name:'taskAgentProject',component:{render:()=>null}},{path:'/tasks',name:'taskAgentTasks',component:{render:()=>null}},{path:'/task/:taskId',name:'taskAgentDetail',component:{render:()=>null}}]})
    await router.push('/');await router.isReady()
    app=renderer().createApp({render:()=>h(component,{activeProjectId:active.value})})
    app.use(router);app.use(createI18n({legacy:false,locale:'zh-CN',messages:{'zh-CN':messages}}))
    app.component('APopover',{inheritAttrs:false,setup:(_,{attrs,slots})=>()=>h('Popover',attrs,[slots.default?.(),slots.content?.()])})
    for(const name of ['AButton','AModal','AAlert'])app.component(name,{inheritAttrs:false,setup:(_,{attrs,slots})=>()=>h(name==='AButton'?'button':name,attrs,[slots.icon?.(),slots.default?.()])})
    const root={children:[]};app.mount(root);await flush();await flush()
    assert.match(textOf(root),/全部 Project/)
    const taskLinks=()=>findAll(root,node=>node.type==='a'&&String(node.props.class).includes('project-task-link'))
    assert.equal(taskLinks().length,5)
    findAll(root,node=>node.type==='button'&&node.props.class==='project-load-more')[0].props.onClick();await flush()
    assert.equal(taskLinks().length,7)
    assert.equal(calls.filter(call=>call.action==='list').at(-1).payload.offset,5)
    assert.equal(taskLinks()[0].props.href,'/task/task-0')
    const pin=findAll(root,node=>node.type==='button'&&node.props['aria-label']==='固定项目')[1]
    pin.props.onClick();await flush()
    assert.deepEqual(JSON.parse(storage.get('task-agent-pinned-projects')),['p2'])
    assert.match(textOf(findAll(root,node=>node.props?.class==='project-tree-group')[0]),/后端工程/)
    rejectTasks=true
    const secondToggle=findAll(root,node=>node.type==='button'&&node.props['aria-label']==='展开或收起 后端工程')[0]
    secondToggle.props.onClick();await flush()
    assert.ok(findAll(root,node=>String(node.props?.['aria-label'] || '').includes('任务加载失败')).length)
    rejectTasks=false
    findAll(root,node=>node.type==='button'&&node.props.class==='project-load-more')[0].props.onClick();await flush()
    assert.match(textOf(root),/暂无任务/)
    const create=findAll(root,node=>node.type==='button'&&node.props['aria-label']==='在 前端工程 中新建任务')[0]
    create.props.onClick();await flush()
    assert.equal(router.currentRoute.value.params.projectId,'p1')
    assert.equal(taskLinks().length,7)
    const quickCards=findAll(root,node=>node.props?.class==='project-quick-card')
    for(const card of quickCards)assert.ok(findAll(card,node=>node.type==='button').every(button=>button.props.type==='text'))
    const modal=()=>findAll(root,node=>node.type==='AModal')[0]
    const deleteButton=()=>findAll(root,node=>node.type==='button'&&node.props.class==='project-card-delete').find(button=>String(button.props?.['aria-label'] || '').includes('删除项目'))
    deleteButton().props.onClick();await flush()
    assert.equal(modal().props.open,true)
    assert.equal(calls.some(call=>call.action==='delete_project'),false)
    modal().props.onCancel();await flush();assert.equal(modal().props.open,false)
    storage.set('task-agent-favorite-tasks',JSON.stringify(['task-0','other']))
    let deleteFailure=true, resolveDelete
    const originalAPI=globalThis.__navigationAPI
    globalThis.__navigationAPI=async(action,payload)=>{
      if(action!=='delete_project')return originalAPI(action,payload)
      calls.push({action,payload})
      if(deleteFailure)return{status:409,data:{deletion_error:'active_task'}}
      await new Promise(resolve=>{resolveDelete=resolve})
      projects.splice(projects.findIndex(project=>project.project_id===payload.project_id),1)
      return{status:200,data:{task_ids:tasks.map(task=>task.tid)}}
    }
    // Pinned p2 is first in the rendered tree; delete p1 from its own card.
    findAll(root,node=>node.props?.class==='project-quick-card').find(card=>textOf(card).includes('前端工程')).children.at(-1).props.onClick()
    await flush();assert.match(textOf(modal()),/全部 7 个任务.*本机目录和文件将保留/)
    await modal().props.onOk();await flush()
    assert.equal(modal().props.open,true)
    assert.match(findAll(root,node=>node.type==='AAlert')[0].props.message,/先停止任务/)
    assert.deepEqual(calls.filter(call=>call.action==='delete_project').at(-1).payload,{project_id:'p1',expected_updated_at:'v1',expected_task_count:7})
    deleteFailure=false
    const firstDelete=modal().props.onOk();await flush()
    await modal().props.onOk();await flush()
    assert.equal(calls.filter(call=>call.action==='delete_project').length,2)
    resolveDelete();await firstDelete;await flush();await flush()
    assert.equal(modal().props.open,false)
    assert.equal(router.currentRoute.value.name,'taskAgentWorkbench')
    assert.deepEqual(JSON.parse(storage.get('task-agent-favorite-tasks')),['other'])
    assert.doesNotMatch(textOf(root),/前端工程/)
    assert.match(textOf(root),/后端工程/)
    projects.splice(0)
    await router.push('/tasks');await router.push('/');await flush();await flush()
    const emptyCreate=findAll(root,node=>node.type==='button'&&textOf(node)==='创建你的第一个 Project')[0]
    assert.ok(emptyCreate,'empty project list offers creation directly')
    emptyCreate.props.onClick();await flush()
    assert.equal(findAll(root,node=>node.type==='ProjectEditor')[0].props.open,true)
    app.unmount();app=null
    assert.equal(timers.size,0)
  } finally {
    app?.unmount();await server.close();globalThis.window=originalWindow
    if(storageDescriptor)Object.defineProperty(globalThis,'localStorage',storageDescriptor);else delete globalThis.localStorage
    delete globalThis.__navigationAPI
  }
})

test('Project picker defaults to standalone and supports choosing, clearing and retrying projects', async () => {
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    '/project-picker-test.js': await componentSource('../src/views/Workspace/TaskAgent/TaskAgentProjectPicker.vue', 'project-picker'),
    '@/icons': 'export const FolderOpen={render:()=>null},CheckOne=FolderOpen,LoadingFour=FolderOpen,Refresh=FolderOpen,Delete=FolderOpen; export const Close=FolderOpen,Undo=FolderOpen,Star=FolderOpen,OffScreenOne=FolderOpen,Down=FolderOpen,OpenExternal=FolderOpen;',
    '@/api/taskAgent': 'export const taskAgentAPI=()=>globalThis.__pickerAPI()',
  }
  const server=await createServer({configFile:false,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{name:'project-picker-test',resolveId:id=> Object.hasOwn(modules,id)?id:undefined,load:id=>modules[id]}],server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true},appType:'custom'})
  let app
  try {
    const value=ref(''), disabled=ref(false)
    let failed=false
    globalThis.__pickerAPI=async()=>failed?{status:503}:{status:200,data:{projects:[{project_id:'p',name:'工程目录',task_count:3}]}}
    const component=(await server.ssrLoadModule('/project-picker-test.js')).default
    app=renderer().createApp({render:()=>h(component,{modelValue:value.value,disabled:disabled.value,'onUpdate:modelValue':next=>{value.value=next}})})
    const messages=JSON.parse(await readFile(new URL('../src/locales/zh-CN.json',import.meta.url),'utf8'))
    app.use(createI18n({legacy:false,locale:'zh-CN',messages:{'zh-CN':messages}}))
    app.component('ADropdown',{inheritAttrs:false,setup:(_,{attrs,slots})=>()=>h('Dropdown',attrs,[slots.default?.(),slots.overlay?.()])})
    for(const name of ['AMenu','AMenuItem','AMenuDivider'])app.component(name,{inheritAttrs:false,setup:(_,{attrs,slots})=>()=>h(name,attrs,slots.default?.())})
    const root={children:[]};app.mount(root);await flush()
    const menu=()=>findAll(root,node=>node.type==='AMenu')[0]
    const trigger=()=>findAll(root,node=>node.type==='button')[0]
    assert.deepEqual(menu().props['selected-keys'],['standalone'])
    assert.match(textOf(root),/不在 Project 中.*创建独立任务/)
    menu().props.onClick({key:'project:p'});await flush()
    assert.equal(value.value,'p');assert.match(textOf(trigger()),/工程目录/)
    disabled.value=true;await flush()
    menu().props.onClick({key:'standalone'});await flush();assert.equal(value.value,'p')
    disabled.value=false;await flush()
    menu().props.onClick({key:'standalone'});await flush();assert.equal(value.value,'')
    failed=true;findAll(root,node=>node.type==='Dropdown')[0].props.onOpenChange(true);await flush()
    assert.match(textOf(root),/项目暂时无法读取/)
    failed=false;menu().props.onClick({key:'retry'});await flush()
    assert.doesNotMatch(textOf(root),/项目暂时无法读取/)
  } finally {app?.unmount();await server.close();delete globalThis.__pickerAPI}
})

test('workbench MCP selector supports Agent defaults, explicit empty and custom overrides, reset, Agent switch and inputId rotation while preserving goal and attachments', async () => {
  const emptyComponent = 'export default { render: () => null }'
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    '/task-agent-workbench-mcp-test.js': await componentSource('../src/views/Workspace/TaskAgent/TaskAgentWorkbench.vue', 'task-workbench-mcp'),
    '@/components/ModelPicker.vue': emptyComponent,
    '@/components/taskAgent/AgentPicker.vue': 'import {h} from "vue";export default{props:["modelValue","disabled"],emits:["update:modelValue","change"],setup:(props,{emit})=>()=>h("AgentPicker",{value:props.modelValue,disabled:props.disabled,onChange:value=>{emit("update:modelValue",value);emit("change",value)}})}',
    '@/views/Workspace/TaskAgent/TaskAgentProjectEditor.vue': emptyComponent,
    '@/views/Workspace/TaskAgent/TaskAgentProjectPicker.vue': emptyComponent,
    '@/views/Workspace/TaskAgent/TaskAgentWorkspace.vue': emptyComponent,
    '@/views/Workspace/TaskAgent/TaskAgentPermissions.vue': emptyComponent,
    '@/views/Workspace/TaskAgent/TaskAgentModelError.vue': emptyComponent,
    '@/components/workspace/UploaderFieldUse.vue': emptyComponent,
    '@/components/workspace/AttachmentsList.vue': emptyComponent,
    '@/icons': 'export const DoubleRight={render:()=>null},Link=DoubleRight,Robot=DoubleRight,Send=DoubleRight,MenuUnfoldOne=DoubleRight,Edit=DoubleRight,Search=DoubleRight,Tool=DoubleRight; export const Refresh=DoubleRight,Close=DoubleRight,Delete=DoubleRight,Undo=DoubleRight,Star=DoubleRight,OffScreenOne=DoubleRight,Down=DoubleRight,OpenExternal=DoubleRight;',
    '@/api/taskAgent': 'export const taskAgentAPI=(action,payload)=>globalThis.__workbenchMcpAPI(action,payload)',
    '@/utils/taskAgentErrors': await readFile(new URL('../src/utils/taskAgentErrors.js', import.meta.url), 'utf8'),
    '@/utils/common': 'export const getChatModelOptions=()=>globalThis.__modelOptions',
    '@/utils/modelPreferences': 'export const validModelPair=()=>true',
    '@/stores/modelCatalog': 'export const useModelCatalogStore=()=>({ensureLoaded:async()=>{}})',
    '@/stores/userSettings': 'export const useUserSettingsStore=()=>({setting:{data:{model_preferences:{default:{model_provider:"Local",model:"mock"}}}}})',
    '@/utils/taskAgentPresentation': await readFile(new URL('../src/utils/taskAgentPresentation.js', import.meta.url), 'utf8'),
    'ant-design-vue': 'export const message={error:()=>{},warning:()=>{}}',
  }
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'task-workbench-mcp-test', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }],
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  const originalWindow = globalThis.window
  globalThis.window = { ...originalWindow, setTimeout, clearTimeout }
  let app
  try {
    const calls = []
    let availableTools = [
      { tool_id: 'mcp__srv__echo__1111', namespaced_name: 'mcp__srv__echo__1111', server_id: 'srv', server_name: 'Demo Server', name: 'echo', title: 'Echo Tool' },
      { tool_id: 'mcp__srv__write__2222', namespaced_name: 'mcp__srv__write__2222', server_id: 'srv', server_name: 'Demo Server', name: 'write', title: 'Write Tool' },
    ]
    globalThis.__modelOptions = [{ value: 'Local', children: [{ value: 'mock', label: 'Mock model' }] }]
    globalThis.__workbenchMcpAPI = async (action, payload) => {
      calls.push({ action, payload })
      if (action === 'mcp_tools') return { status: 200, data: { tools: availableTools } }
      if (action === 'profiles') return { status: 200, data: { agents: [
        { agent_id: 'agent-a', name: 'Agent A', permission_mode: 'auto', mcp_tool_ids: ['mcp__srv__echo__1111'] },
        { agent_id: 'agent-b', name: 'Agent B', permission_mode: 'auto', mcp_tool_ids: ['mcp__srv__write__2222', 'mcp__srv__missing__9999'] },
      ] } }
      if (action === 'create') return { status: 200, data: { task: { tid: 'created-task' } } }
      return { status: 200, data: { sync_error: false, tasks: [] } }
    }
    const component = (await server.ssrLoadModule('/task-agent-workbench-mcp-test.js')).default
    const messages = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/', name: 'taskAgentWorkbench', component: { render: () => null } },
        { path: '/mcp', name: 'taskAgentMCP', component: { render: () => null } },
        { path: '/tasks', name: 'taskAgentTasks', component: { render: () => null } },
        { path: '/tasks/:taskId', name: 'taskAgentDetail', component: { render: () => null } },
        { path: '/settings', name: 'settings', component: { render: () => null } },
      ],
    })
    await router.push('/?agent_id=agent-a')
    await router.isReady()
    app = renderer().createApp({ render: () => h(component) })
    app.use(router)
    app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } }))
    app.component('ATextarea', { props: ['value'], emits: ['update:value'], setup: (props, { emit, attrs }) => () => h('ATextarea', { ...attrs, value: props.value, 'onUpdate:value': value => emit('update:value', value) }) })
    app.component('APopover', { inheritAttrs: false, setup: (_props, { attrs, slots }) => () => h('APopover', attrs, [slots.default?.(), slots.content?.()]) })
    app.component('ACheckbox', { inheritAttrs: false, setup: (_props, { attrs, slots }) => () => h('ACheckbox', attrs, slots.default?.()) })
    for (const name of ['AButton', 'ATooltip', 'ASpin', 'AEmpty', 'ASelect', 'AAlert', 'AInput', 'ASpace']) {
      app.component(name, { inheritAttrs: false, setup: (_props, { attrs, slots }) => () => h(name, attrs, slots.default?.()) })
    }
    const root = { children: [] }
    app.mount(root)
    await flush(); await flush()

    const textarea = () => findAll(root, node => node.type === 'ATextarea')[0]
    const sendBtn = () => findAll(root, node => node.type === 'AButton' && String(node.props.class).includes('send-task'))[0]
    textarea().props['onUpdate:value']('测试默认与自定义 MCP')
    await flush()

    // 1. Default Agent A selection: omits mcp_tool_ids
    await sendBtn().props.onClick()
    await flush()
    const firstCreate = calls.filter(c => c.action === 'create').at(-1).payload
    assert.equal(Object.hasOwn(firstCreate, 'mcp_tool_ids'), false)

    // Restore goal for next test
    await router.push('/?agent_id=agent-a')
    textarea().props['onUpdate:value']('保留的草稿内容')
    await flush()

    // 2. Clear all -> sends explicit []
    const clearBtn = () => findAll(root, node => node.type === 'AButton' && String(node.props?.['aria-label'] || '').includes('清空全部'))[0]
    clearBtn().props.onClick()
    await flush()
    assert.equal(textarea().props.value, '保留的草稿内容')
    await sendBtn().props.onClick()
    await flush()
    const secondCreate = calls.filter(c => c.action === 'create').at(-1).payload
    assert.deepEqual(secondCreate.mcp_tool_ids, [])
    assert.notEqual(secondCreate.input_id, firstCreate.input_id)

    // 3. Toggle custom tool -> sends explicit non-empty array, then reset to default
    textarea().props['onUpdate:value']('自定义工具调用')
    await flush()
    const checkboxes = () => findAll(root, node => node.type === 'ACheckbox')
    checkboxes()[1].props.onChange()
    await flush()
    const resetBtn = () => findAll(root, node => node.type === 'AButton' && String(node.props?.['aria-label'] || '').includes('恢复 Agent 默认'))[0]
    assert.ok(resetBtn())
    await sendBtn().props.onClick()
    await flush()
    const thirdCreate = calls.filter(c => c.action === 'create').at(-1).payload
    assert.deepEqual(thirdCreate.mcp_tool_ids, ['mcp__srv__echo__1111', 'mcp__srv__write__2222'])

    // 4. Switch to Agent B which has an unavailable tool -> blocks submit until removed, and resets override to Agent B defaults
    textarea().props['onUpdate:value']('切换 Agent 保留输入')
    await flush()
    const agentSelect = findAll(root, node => node.type === 'AgentPicker')[0]
    agentSelect.props.onChange('agent-b')
    await flush()
    assert.equal(textarea().props.value, '切换 Agent 保留输入')
    assert.equal(sendBtn().props.disabled, true)
    const removeBadBtn = findAll(root, node => node.type === 'AButton' && String(node.props?.['aria-label'] || '').includes('移除不可用项'))[0]
    assert.ok(removeBadBtn)
    removeBadBtn.props.onClick()
    await flush()
    assert.equal(sendBtn().props.disabled, false)
  } finally {
    app?.unmount(); await server.close(); globalThis.window = originalWindow
    delete globalThis.__workbenchMcpAPI
  }
})
