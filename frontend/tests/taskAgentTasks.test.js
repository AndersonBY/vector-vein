import { iconButtonFixture } from './taskAgentButtonFixture.js'
import assert from 'node:assert/strict'
import test from 'node:test'
import {readFile} from 'node:fs/promises'
import {fileURLToPath} from 'node:url'
import {createRenderer,h,nextTick,reactive} from 'vue'
import {createI18n} from 'vue-i18n'
import {parse,compileScript} from 'vue/compiler-sfc'
import {createServer} from 'vite'

const flush=async()=>{for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));await nextTick()}
const deferred=()=>{let resolve;const promise=new Promise(yes=>{resolve=yes});return{promise,resolve}}
const copy=value=>JSON.parse(JSON.stringify(value))
async function catalog(run,query={}){
 const oldWindow=globalThis.window,storageDescriptor=Object.getOwnPropertyDescriptor(globalThis,'localStorage')
 const storage=new Map(),timers=new Map()
 const state={route:reactive({name:'taskAgentTasks',query,params:{}}),calls:[],replaced:[],pushed:[],request:async(action,payload)=>action==='project'?{status:200,data:{project_id:payload.project_id,name:'Project'}}:{status:200,data:{tasks:[{tid:payload.search||'task',status:'COMPLETED',title:'Title',updated_at:'v1'}],total:135,agents:[{agent_id:'general',name:''}],sync_error:false}}}
 globalThis.__taskCatalog=state
 globalThis.window={setTimeout:fn=>{const id=Symbol();timers.set(id,fn);return id},clearTimeout:id=>timers.delete(id)}
 Object.defineProperty(globalThis,'localStorage',{configurable:true,value:{getItem:key=>storage.get(key)??null,setItem:(key,value)=>storage.set(key,value)}})
 const filename=fileURLToPath(new URL('../src/views/Workspace/TaskAgent/TaskAgentTasks.vue',import.meta.url))
 const {descriptor}=parse(await readFile(filename,'utf8'),{filename})
 const script=compileScript(descriptor,{id:'task-catalog'}).content.replace("'@/components/IconButton.vue'", "'virtual:icon-button'").replaceAll("'vue-router'","'virtual:router'").replaceAll("'@/api/taskAgent'","'virtual:task-api'").replaceAll("'ant-design-vue'","'virtual:antd'").replaceAll("'@/components/taskAgent/AgentPicker.vue'","'virtual:agent-picker'")
 const modules={
    'virtual:icon-button': iconButtonFixture,
  '/task-catalog.js':script,
  'virtual:agent-picker': 'export default { render: () => null }',
  'virtual:antd':'export const message={success:()=>{},error:()=>{}}',
  'virtual:router':'export const useRoute=()=>globalThis.__taskCatalog.route;export const useRouter=()=>({push:async target=>globalThis.__taskCatalog.pushed.push(target),replace:async target=>{const state=globalThis.__taskCatalog;state.replaced.push(target);state.route.query=target.query}})',
  'virtual:task-api':'export const taskAgentAPI=(action,payload)=>{const state=globalThis.__taskCatalog;state.calls.push({action,payload:JSON.parse(JSON.stringify(payload||{}))});return state.request(action,payload)}',
  '@/icons':'export const Plus={render:()=>null},Search=Plus,Robot=Plus,Control=Plus,ListOne=Plus,ViewGridCard=Plus,PreviewOpen=Plus,PreviewCloseOne=Plus,Star=Plus,Delete=Plus; export const Refresh=Plus,Close=Plus,Undo=Plus,OffScreenOne=Plus,Down=Plus,OpenExternal=Plus;',
 }
 const server=await createServer({configFile:false,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{name:'task-catalog-fixture',resolveId:id=> Object.hasOwn(modules,id)?id:undefined,load:id=>modules[id]}],resolve:{alias:{'@':fileURLToPath(new URL('../src',import.meta.url))}},server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true},appType:'custom'})
 let app,vm
 try{
  const component=(await server.ssrLoadModule('/task-catalog.js')).default
  const renderer=createRenderer({createElement:()=>({}),createText:()=>({}),createComment:()=>({}),insert(){},remove(){},setText(){},setElementText(){},patchProp(){},parentNode:()=>null,nextSibling:()=>null})
  app=renderer.createApp({setup(props,context){vm=component.setup(props,context);return()=>h('div')}})
  const messages=JSON.parse(await readFile(new URL('../src/locales/zh-CN.json',import.meta.url),'utf8'))
  app.use(createI18n({legacy:false,locale:'zh-CN',messages:{'zh-CN':messages}}));app.mount({});await flush()
  await run(vm,state,storage,timers,()=>{app.unmount();app=null})
 }finally{app?.unmount();await server.close();delete globalThis.__taskCatalog;globalThis.window=oldWindow;if(storageDescriptor)Object.defineProperty(globalThis,'localStorage',storageDescriptor);else delete globalThis.localStorage}
}

test('task catalog restores route filters and queries the full paginated scope',async()=>{
 await catalog(async(vm,state)=>{
  assert.equal(vm.total.value,135)
  assert.deepEqual(state.calls.find(call=>call.action==='list').payload,{limit:10,offset:20,search:'old',project_id:'p',agent_id:'one',statuses:['FAILED'],sort_by:'created_at',sort_order:'desc',summary:true})
  assert.equal(vm.project.value.name,'Project')
  assert.deepEqual(copy(vm.createRoute.value),{name:'taskAgentProject',params:{projectId:'p'},query:{agent_id:'one'}})
  await vm.tableChange({current:2,pageSize:20},{status:['COMPLETED']},{columnKey:'updated_at',order:'ascend'});await flush()
  assert.equal(state.calls.at(-1).payload.offset,20)
  assert.equal(state.calls.at(-1).payload.limit,20)
  assert.equal(state.calls.at(-1).payload.sort_by,'updated_at')
  assert.equal(state.calls.at(-1).payload.sort_order,'asc')
  vm.search.value='Needle';await new Promise(resolve=>setTimeout(resolve,230));await flush()
  const payload=state.calls.at(-1).payload
  assert.equal(payload.search,'Needle');assert.equal(payload.offset,0);assert.equal(payload.project_id,'p');assert.equal(payload.agent_id,'one')
  assert.deepEqual(payload.statuses,['COMPLETED'])
  assert.equal(vm.dateLabel(null),'—')
 },{page:'3',search:'old',project_id:'p',agent_id:'one',status:'FAILED'})
})

test('hidden task catalog queries hidden history and restores tasks with a fresh identity',async()=>{
 await catalog(async(vm,state)=>{
  assert.equal(vm.visibility.value,'hidden')
  assert.equal(state.calls.find(call=>call.action==='list').payload.visibility,'hidden')
  await vm.toggleHidden({tid:'hidden-task',hidden:1,updated_at:'v2'})
  assert.deepEqual(state.calls.find(call=>call.action==='set_hidden').payload,{task_id:'hidden-task',hidden:false,expected_updated_at:'v2'})
  assert.equal(vm.changingVisibility.value,null)
  state.request=async()=>{throw Error('Synthetic failure')}
  await vm.toggleHidden({tid:'hidden-task',hidden:1,updated_at:'v2'})
  assert.equal(vm.changingVisibility.value,null)
 },{visibility:'hidden'})
})

test('task catalog ignores late results, retries failures and stops polling on unmount',async()=>{
 await catalog(async(vm,state,_storage,timers,unmount)=>{
  const late=deferred()
  state.request=async(_action,payload)=>payload.search==='slow'?late.promise:{status:200,data:{tasks:[{tid:'fast',status:'PROCESSING'}],total:1,agents:[]}}
  state.route.query={search:'slow'};await flush()
  state.route.query={search:'fast'};await flush()
  assert.equal(vm.tasks.value[0].tid,'fast')
  late.resolve({status:200,data:{tasks:[{tid:'stale'}],total:1,agents:[]}});await flush()
  assert.equal(vm.tasks.value[0].tid,'fast')
  state.request=async()=>({status:503});await vm.loadTasks();assert.equal(vm.failed.value,true);assert.equal(vm.loading.value,false)
  state.request=async()=>({status:200,data:{tasks:[],total:0,agents:[]}});await vm.loadTasks();assert.equal(vm.failed.value,false)
  assert.equal(timers.size,0)
  state.request=async()=>({status:200,data:{tasks:[{tid:'active',status:'PROCESSING'}],total:1,agents:[]}});await vm.loadTasks();assert.equal(timers.size,1)
  unmount();assert.equal(timers.size,0)
 })
})

test('task catalog saves favorites and view choices locally and clamps empty pages',async()=>{
 await catalog(async(vm,state,storage)=>{
  vm.toggleFavorite({tid:'one'});assert.equal(vm.isFavorite({tid:'one'}),true)
  vm.selected.value=['one','two'];vm.favoriteSelected()
  assert.deepEqual(JSON.parse(storage.get('task-agent-favorite-tasks')),['one','two'])
  assert.deepEqual(vm.selected.value,[])
  await vm.changeView('card');await flush();assert.equal(vm.view.value,'card');assert.equal(storage.get('task-agent-task-view'),'card')
  vm.toggleFavorite({tid:'one'});assert.equal(vm.isFavorite({tid:'one'}),false)
  state.request=async()=>({status:200,data:{tasks:[],total:0,agents:[]}})
  state.route.query={page:'99'};await flush();await flush()
  assert.equal(vm.page.value,1)
  assert.equal(state.route.query.page,undefined)
 })
})

test('task deletion requires confirmation, retains failures, prevents duplicate submits and clears local state',async()=>{
 await catalog(async(vm,state,storage)=>{
  const target={tid:'one',title:'Delete me',updated_at:'v1'}
  vm.toggleFavorite(target);vm.selected.value=['one','two']
  vm.askDelete(target)
  assert.equal(state.calls.some(call=>call.action==='delete_task'),false)
  vm.pendingDelete.value=null;await vm.confirmDelete()
  assert.equal(state.calls.some(call=>call.action==='delete_task'),false)
  vm.askDelete(target)
  const original=state.request
  state.request=async(action,payload)=>action==='delete_task'?{status:409,data:{deletion_error:'active_task'}}:original(action,payload)
  await vm.confirmDelete()
  assert.equal(vm.deleteError.value,'active_task');assert.equal(vm.pendingDelete.value.tid,'one');assert.equal(vm.deleting.value,false)
  assert.deepEqual(state.calls.find(call=>call.action==='delete_task').payload,{task_id:'one',expected_updated_at:'v1'})
  const pending=deferred()
  state.request=async(action,payload)=>action==='delete_task'?pending.promise:original(action,payload)
  const before=state.calls.filter(call=>call.action==='delete_task').length
  const first=vm.confirmDelete();await vm.confirmDelete()
  assert.equal(state.calls.filter(call=>call.action==='delete_task').length,before+1)
  assert.equal(vm.deleting.value,true)
  pending.resolve({status:200,data:{deleted:true,task_ids:['one']}});await first
  assert.equal(vm.pendingDelete.value,null);assert.equal(vm.deleting.value,false)
  assert.deepEqual(JSON.parse(storage.get('task-agent-favorite-tasks')),[])
  assert.deepEqual(copy(vm.selected.value),[])
  assert.equal(state.calls.at(-1).action,'list')
 })
})


test('project deletion refreshes a visible global catalog and clears its favorites',async()=>{
 await catalog(async(vm,state,storage)=>{
  vm.toggleFavorite({tid:'removed'});vm.toggleFavorite({tid:'keep'})
  const before=state.calls.filter(call=>call.action==='list').length
  vm.projectDeletion.value={project_id:'p',task_ids:['removed']};await flush()
  assert.equal(state.calls.filter(call=>call.action==='list').length,before+1)
  assert.deepEqual(JSON.parse(storage.get('task-agent-favorite-tasks')),['keep'])
 })
})

test('task rows and cards navigate while controls, links, selection and modified clicks stay independent', async () => {
 await catalog(async (vm, state) => {
  const task = {tid:'task_with_id'}
  const click = {button:0,target:{closest:()=>null}}
  await vm.openTask(task, click)
  assert.deepEqual(copy(state.pushed), [{name:'taskAgentDetail',params:{taskId:'task_with_id'}}])
  for (const patch of [{defaultPrevented:true},{button:1},{ctrlKey:true},{metaKey:true},{shiftKey:true},{altKey:true},
    {target:{closest:()=>({tagName:'BUTTON'})}}, {target:{closest:()=>({tagName:'A'})}}, {target:{closest:()=>({tagName:'INPUT'})}}]) {
   await vm.openTask(task, {...click,...patch})
  }
  assert.equal(state.pushed.length,1)
 })
})
