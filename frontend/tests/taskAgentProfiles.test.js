import { iconButtonFixture } from './taskAgentButtonFixture.js'
import assert from 'node:assert/strict'
import test from 'node:test'
import {readFile} from 'node:fs/promises'
import {fileURLToPath} from 'node:url'
import {createRenderer,h,nextTick,reactive} from 'vue'
import {createI18n} from 'vue-i18n'
import {parse,compileScript} from 'vue/compiler-sfc'
import {createServer} from 'vite'

const flush=async()=>{for(let i=0;i<6;i++)await new Promise(resolve=>setImmediate(resolve));await nextTick()}
const deferred=()=>{let resolve;const promise=new Promise(yes=>{resolve=yes});return{promise,resolve}}
const profile=(id,name=id)=>({agent_id:id,name,instructions:'核对资料并保存报告。',description:'用途说明',max_cycles:40,allow_shell:true,allow_sub_agents:true,allow_file_writes:true,permission_mode:'auto',workflow_ids:[],model_provider:'',model:'',reasoning_effort:'default'})

async function editor(run,{creating=false}={}){
 const previous=globalThis.__profileEditor,previousWindow=globalThis.window
 const state={route:reactive({name:creating?'taskAgentCreate':'taskAgentEdit',params:creating?{}:{agentId:'one'},query:{}}),replaced:[],calls:[],successes:[],request:async(action,payload)=>action==='workflows'?{status:200,data:{workflows:[]}}:action==='skills'?{status:200,data:{skills:[]}}:action==='mcp_tools'?{status:200,data:{tools:[]}}:{status:200,data:profile(payload.agent_id)}}
 globalThis.__profileEditor=state;globalThis.window={confirm:()=>false,addEventListener(){},removeEventListener(){}}
 const filename=fileURLToPath(new URL('../src/views/Workspace/TaskAgent/TaskAgentAgentDetail.vue',import.meta.url))
 const {descriptor}=parse(await readFile(filename,'utf8'),{filename})
 const script=compileScript(descriptor,{id:'profile-editor'}).content.replaceAll("'vue-router'","'virtual:router'").replaceAll("'ant-design-vue'","'virtual:messages'").replaceAll("'@/components/ModelPicker.vue'","'virtual:child'").replaceAll("'./TaskAgentPermissions.vue'","'virtual:child'").replaceAll("'./TaskAgentModelError.vue'","'virtual:child'")
 const modules={
    '@/components/IconButton.vue': iconButtonFixture,
  '/profile-editor.js':script,
  'virtual:router':'export const useRoute=()=>globalThis.__profileEditor.route;export const useRouter=()=>({replace:target=>{const s=globalThis.__profileEditor;s.replaced.push(target);s.leaveAtReplace=s.leave();return Promise.resolve()}});export const onBeforeRouteLeave=fn=>{globalThis.__profileEditor.leave=fn};export const onBeforeRouteUpdate=fn=>{globalThis.__profileEditor.update=fn}',
  'virtual:messages':'export const message={success:x=>globalThis.__profileEditor.successes.push(x)}',
  'virtual:child':'export default {render:()=>null}',
  '@/components/taskAgent/KnowledgeBasePicker.vue':'export default {render:()=>null}',
  '@/api/taskAgent':'export const taskAgentAPI=(a,p={})=>{const s=globalThis.__profileEditor;s.calls.push({action:a,payload:p});return s.request(a,p)}',
  '@/utils/taskAgentErrors': await readFile(new URL('../src/utils/taskAgentErrors.js', import.meta.url), 'utf8'),
  '@/utils/common':'export const getChatModelOptions=()=>[]',
  '@/utils/modelPreferences':'export const validModelPair=()=>false',
  '@/stores/modelCatalog':'export const useModelCatalogStore=()=>({ensureLoaded:async()=>{}})',
  '@/icons':'export const Left={render:()=>null},Robot=Left,Save=Left,PlayOne=Left,Copy=Left,User=Left,Setting=Left,Tool=Left,Code=Left,CheckOne=Left; export const Refresh=Left,Close=Left,Delete=Left,Undo=Left,Star=Left,OffScreenOne=Left,Down=Left,OpenExternal=Left;',
 }
 const server=await createServer({configFile:false,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{name:'profile-editor-fixture',resolveId:id=> Object.hasOwn(modules,id)?id:undefined,load:id=>modules[id]}],server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true},appType:'custom'})
 let app,vm
 try{
  const component=(await server.ssrLoadModule('/profile-editor.js')).default
  const renderer=createRenderer({createElement:()=>({}),createText:()=>({}),createComment:()=>({}),insert(){},remove(){},setText(){},setElementText(){},patchProp(){},parentNode:()=>null,nextSibling:()=>null})
  app=renderer.createApp({setup(props,context){vm=component.setup(props,context);return()=>h('div')}})
  const messages=JSON.parse(await readFile(new URL('../src/locales/zh-CN.json',import.meta.url),'utf8'))
  app.use(createI18n({legacy:false,locale:'zh-CN',messages:{'zh-CN':messages}}));app.mount({});await flush()
  vm.form.value={validate:async()=>{},scrollToField(){}}
  await run(vm,state)
 }finally{app?.unmount();await server.close();globalThis.__profileEditor=previous;globalThis.window=previousWindow}
}

test('Agent editor keeps failed drafts, guards unsaved navigation and leaves after a successful create',async()=>{
 await editor(async(vm,state)=>{
  vm.draft.value.name='新建资料助手';vm.draft.value.instructions='核实来源并交付报告。'
  assert.equal(vm.cycleLimitEnabled.value,false);assert.equal(vm.draft.value.max_cycles,0)
  vm.cycleLimitEnabled.value=true;assert.equal(vm.draft.value.max_cycles,50)
  vm.draft.value.max_cycles=1200;vm.cycleLimitEnabled.value=false
  assert.equal(vm.draft.value.max_cycles,0)
  vm.cycleLimitEnabled.value=true;assert.equal(vm.draft.value.max_cycles,1200)
  vm.cycleLimitEnabled.value=false
  await flush();assert.equal(vm.dirty.value,true);assert.equal(state.leave(),false)
  state.request=async()=>({status:503,data:{}})
  await vm.save();assert.equal(vm.draft.value.name,'新建资料助手');assert.equal(vm.dirty.value,true);assert.ok(vm.saveError.value);assert.equal(state.replaced.length,0)
  state.request=async(_action,payload)=>({status:200,data:{...payload,updated_at:'2026-11-05T12:00:00Z'}})
  await vm.save();assert.equal(vm.dirty.value,false);assert.equal(state.replaced[0].name,'taskAgentEdit');assert.equal(state.leaveAtReplace,true);assert.equal(state.successes.length,1)
  assert.equal(state.calls.filter(call=>call.action==='save_profile').at(-1).payload.max_cycles,0)
 },{creating:true})
})

test('Agent editor preserves knowledge mounts through loading, failed saves and successful saves',async()=>{
 await editor(async(vm,state)=>{
  const ids=['kb-one','kb-two']
  state.request=async(action,payload)=>action==='workflows'?{status:200,data:{workflows:[]}}:action==='skills'?{status:200,data:{skills:[]}}:action==='mcp_tools'?{status:200,data:{tools:[]}}:action==='save_profile'?{status:503}:{status:200,data:{...profile(payload.agent_id),knowledge_base_ids:ids}}
  await vm.load()
  assert.deepEqual(vm.draft.value.knowledge_base_ids,ids)
  vm.draft.value.knowledge_base_ids.pop()
  assert.deepEqual(ids,['kb-one','kb-two'],'editing mounts does not mutate the loaded profile')
  await vm.save()
  assert.deepEqual(vm.draft.value.knowledge_base_ids,['kb-one'])
  assert.deepEqual(state.calls.filter(call=>call.action==='save_profile').at(-1).payload.knowledge_base_ids,['kb-one'])
  state.request=async(_action,payload)=>({status:200,data:{...payload,updated_at:'new'}})
  await vm.save()
  assert.deepEqual(vm.draft.value.knowledge_base_ids,['kb-one'])
  assert.equal(vm.dirty.value,false)
 })
})

test('Agent editor refuses to save more than twenty knowledge mounts',async()=>{
 await editor(async(vm,state)=>{
  vm.draft.value.knowledge_base_ids=Array.from({length:21},(_,i)=>`kb-${i}`)
  await vm.save()
  assert.equal(vm.capabilityTab.value,'knowledge')
  assert.match(vm.saveError.value,/21.*20/)
  assert.equal(state.calls.some(call=>call.action==='save_profile'),false)
 })
})

test('Agent editor discards late profile responses after route changes and preserves recoverable load errors',async()=>{
 await editor(async(vm,state)=>{
  const late=deferred()
  state.request=(action,payload)=>action==='workflows'?Promise.resolve({status:200,data:{workflows:[]}}):action==='skills'?Promise.resolve({status:200,data:{skills:[]}}):action==='mcp_tools'?Promise.resolve({status:200,data:{tools:[]}}):payload.agent_id==='two'?late.promise:Promise.resolve({status:200,data:profile(payload.agent_id)})
  state.route.params.agentId='two';await flush();assert.equal(vm.loading.value,true)
  state.route.params.agentId='three';await flush();assert.equal(vm.draft.value.agent_id,'three')
  late.resolve({status:200,data:profile('two')});await flush();assert.equal(vm.draft.value.agent_id,'three')
  state.request=async()=>({status:503,data:{}});state.route.params.agentId='failed';await flush();assert.equal(vm.failed.value,true);assert.equal(vm.draft.value,null)
  state.request=async(action,payload)=>action==='workflows'?{status:200,data:{workflows:[]}}:action==='skills'?{status:200,data:{skills:[]}}:action==='mcp_tools'?{status:200,data:{tools:[]}}:{status:200,data:profile(payload.agent_id)}
  await vm.load();assert.equal(vm.failed.value,false);assert.equal(vm.draft.value.agent_id,'failed')
 })
})

test('Agent editor validates Skills and MCP selections, preserves unavailable items until removed and maps integration errors',async()=>{
 await editor(async(vm,state)=>{
  state.request=async(action,payload)=>{
   if(action==='workflows')return{status:200,data:{workflows:[{workflow_id:'wf1',title:'Flow 1'}]}}
   if(action==='skills')return{status:200,data:{skills:[{skill_id:'sk1',name:'writer',description:'Writer skill',enabled:true},{skill_id:'sk2',name:'writer',description:'Duplicate name skill',enabled:true},{skill_id:'sk_disabled',name:'off_skill',description:'Disabled',enabled:false}]}}
   if(action==='mcp_tools')return{status:200,data:{tools:[{tool_id:'mcp__srv__echo__1234',namespaced_name:'mcp__srv__echo__1234',server_id:'srv',server_name:'Demo Server',name:'echo',title:'Echo Tool'}]}}
   if(action==='profile')return{status:200,data:{...profile(payload.agent_id),skill_ids:['sk1','sk_missing'],mcp_tool_ids:['mcp__srv__echo__1234','mcp__srv__stale__9999']}}
   return{status:200,data:{...payload,updated_at:'2026-11-06T00:00:00Z'}}
  }
  await vm.load()
  assert.deepEqual(vm.draft.value.skill_ids,['sk1','sk_missing'])
  assert.deepEqual(vm.draft.value.mcp_tool_ids,['mcp__srv__echo__1234','mcp__srv__stale__9999'])
  assert.deepEqual(vm.unavailableSkillIds.value,['sk_missing'])
  assert.deepEqual(vm.unavailableMcpToolIds.value,['mcp__srv__stale__9999'])
  await vm.save()
  assert.equal(vm.capabilityTab.value,'skills')
  assert.match(vm.saveError.value,/技能/)
  vm.removeUnavailableSkills()
  assert.deepEqual(vm.draft.value.skill_ids,['sk1'])
  await vm.save()
  assert.equal(vm.capabilityTab.value,'mcp')
  assert.match(vm.saveError.value,/MCP/)
  vm.removeUnavailableMcpTools()
  assert.deepEqual(vm.draft.value.mcp_tool_ids,['mcp__srv__echo__1234'])
  vm.draft.value.skill_ids=['sk1','sk2']
  await vm.save()
  assert.equal(vm.capabilityTab.value,'skills')
  assert.match(vm.saveError.value,/writer/)
  vm.draft.value.skill_ids=['sk1']
  state.request=async(action)=>action==='save_profile'?{status:400,data:{integration_error:{kind:'mcp',code:'mcp_server_stale'}}}:{status:200,data:{}}
  await vm.save()
  assert.equal(vm.capabilityTab.value,'mcp')
  assert.match(vm.saveError.value,/重新测试|配置已变更/)
 })
})

test('Built-in general Agent is editable, defaults localized name/description when blank, allows empty instructions, and preserves agent_id=general on save',async()=>{
 await editor(async(vm,state)=>{
  state.request=async(action,payload)=>{
   if(action==='workflows')return{status:200,data:{workflows:[]}}
   if(action==='skills')return{status:200,data:{skills:[{skill_id:'sk_gen',name:'gen-skill',description:'General skill',enabled:true}]}}
   if(action==='mcp_tools')return{status:200,data:{tools:[]}}
   if(action==='profile'&&payload.agent_id==='general'){
    return{status:200,data:{agent_id:'general',name:'',description:'',instructions:'',max_cycles:0,allow_shell:true,allow_sub_agents:true,allow_file_writes:true,permission_mode:'auto',workflow_ids:[],skill_ids:[],mcp_tool_ids:[],model_provider:'',model:'',reasoning_effort:'default'}}
   }
   return{status:200,data:{...payload,updated_at:'2026-11-06T01:00:00Z'}}
  }
  state.route.params.agentId='general'
  await flush()
  assert.equal(vm.isBuiltinGeneral.value,true)
  assert.equal(vm.draft.value.agent_id,'general')
  assert.equal(vm.draft.value.name,'通用 Agent')
  assert.equal(vm.draft.value.description,'读取资料、规划步骤，按目标完成任务并交付文件。')
  assert.equal(vm.draft.value.instructions,'')
  assert.equal(vm.rules.value.instructions.some(r=>r.required),false,'instructions must be optional for built-in general')

  // Edit general Agent capabilities and save with empty instructions
  vm.draft.value.skill_ids=['sk_gen']
  vm.draft.value.allow_shell=false
  await flush()
  assert.equal(vm.dirty.value,true)
  await vm.save()
  assert.equal(vm.dirty.value,false)
  const saved=state.calls.filter(c=>c.action==='save_profile').at(-1)
  assert.ok(saved)
  assert.equal(saved.payload.agent_id,'general')
  assert.equal(saved.payload.instructions,'')
  assert.deepEqual(saved.payload.skill_ids,['sk_gen'])
  assert.equal(saved.payload.allow_shell,false)

  // Normal non-general Agent still requires instructions
  state.route.params.agentId='custom-agent'
  await flush()
  assert.equal(vm.isBuiltinGeneral.value,false)
  assert.equal(vm.rules.value.instructions.some(r=>r.required),true,'instructions must remain required for normal Agents')
 })
})

test('Skill detail openSkillDirectory passes exact skill_id and historical version, and surfaces localized errors on failure',async()=>{
 const previous=globalThis.__skillDetailTest,previousWindow=globalThis.window
 const state={
  route:reactive({name:'taskAgentSkillDetail',params:{skillId:'sk_1'},query:{}}),
  calls:[],errors:[],
  request:async(action,payload)=>{
   if(action==='skill')return{status:200,data:{skill_id:payload.skill_id,name:'demo-skill',description:'Demo',version:2,enabled:true,content:'---\nname: demo-skill\ndescription: Demo\n---\n\n# Demo\n'}}
   if(action==='skill_files')return{status:200,data:{name:'demo-skill',description:'Demo',version:payload.version||2,files:[{path:'SKILL.md',size:42}],limited:false}}
   if(action==='skill_preview_file')return{status:200,data:{kind:'text',text:'---\nname: demo-skill\ndescription: Demo\n---\n\n# Demo\n'}}
   if(action==='open_skill_directory')return{status:200,data:{opened:true}}
   return{status:200,data:{}}
  }
 }
 globalThis.__skillDetailTest=state;globalThis.window={confirm:()=>true,addEventListener(){},removeEventListener(){}}
 const filename=fileURLToPath(new URL('../src/views/Workspace/TaskAgent/TaskAgentSkillDetail.vue',import.meta.url))
 const {descriptor}=parse(await readFile(filename,'utf8'),{filename})
 const script=compileScript(descriptor,{id:'skill-detail-test'}).content.replaceAll("'vue-router'","'virtual:router'").replaceAll("'ant-design-vue'","'virtual:messages'")
 const modules={
    '@/components/IconButton.vue': iconButtonFixture,
  '/skill-detail-test.js':script,
  'virtual:router':'export const useRoute=()=>globalThis.__skillDetailTest.route;export const useRouter=()=>({replace:()=>Promise.resolve(),push:()=>Promise.resolve()});export const onBeforeRouteLeave=()=>{};export const onBeforeRouteUpdate=()=>{}',
  'virtual:messages':'export const message={success(){},error:x=>globalThis.__skillDetailTest.errors.push(x)};export const Modal={confirm(){}}',
  '@/api/taskAgent':'export const taskAgentAPI=(a,p={})=>{const s=globalThis.__skillDetailTest;s.calls.push({action:a,payload:p});return s.request(a,p)}',
  '@/utils/taskAgentErrors':await readFile(new URL('../src/utils/taskAgentErrors.js',import.meta.url),'utf8'),
  '@/utils/taskAgentPresentation':'export const formatTaskTime=x=>x||""',
  '@/utils/taskAgentTimeline':'export const fileSize=x=>String(x||0)',
  '@/icons':'export const Left={render:()=>null},BookOpen=Left,Save=Left,Delete=Left,DocDetail=Left,Refresh=Left,FolderOpen=Left; export const Close=Left,Undo=Left,Star=Left,OffScreenOne=Left,Down=Left,OpenExternal=Left;',
 }
 const server=await createServer({configFile:false,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{name:'skill-detail-fixture',resolveId:id=> Object.hasOwn(modules,id)?id:undefined,load:id=>modules[id]}],server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true},appType:'custom'})
 let app,vm
 try{
  const component=(await server.ssrLoadModule('/skill-detail-test.js')).default
  const renderer=createRenderer({createElement:()=>({}),createText:()=>({}),createComment:()=>({}),insert(){},remove(){},setText(){},setElementText(){},patchProp(){},parentNode:()=>null,nextSibling:()=>null})
  app=renderer.createApp({setup(props,context){vm=component.setup(props,context);return()=>h('div')}})
  const messages=JSON.parse(await readFile(new URL('../src/locales/zh-CN.json',import.meta.url),'utf8'))
  app.use(createI18n({legacy:false,locale:'zh-CN',messages:{'zh-CN':messages}}));app.mount({});await flush()

  // Current skill detail: openSkillDirectory sends only skill_id
  assert.equal(vm.creating.value,false)
  assert.equal(vm.readonlyView.value,false)
  await vm.openSkillDirectory()
  assert.deepEqual(state.calls.filter(c=>c.action==='open_skill_directory').at(-1)?.payload,{skill_id:'sk_1'})

  // Historical revision (?version=1): readonlyView is true, openSkillDirectory sends { skill_id, version: 1 }
  state.route.query={version:'1'}
  await flush()
  assert.equal(vm.isHistoricalInspection.value,true)
  assert.equal(vm.readonlyView.value,true)
  await vm.openSkillDirectory()
  assert.deepEqual(state.calls.filter(c=>c.action==='open_skill_directory').at(-1)?.payload,{skill_id:'sk_1',version:1})

  // Failed open_skill_directory surfaces localized error
  state.request=async(action)=>action==='open_skill_directory'?{status:500,data:{opened:false}}:{status:200,data:{}}
  await vm.openSkillDirectory()
  assert.equal(state.errors.length,1)
  assert.match(state.errors[0],/无法打开|目录|不存在|失败|skill_open_directory_failed/)

  // Create mode: openSkillDirectory is a no-op
  const countBefore=state.calls.filter(c=>c.action==='open_skill_directory').length
  state.route.name='taskAgentSkillCreate'
  state.route.params={}
  state.route.query={}
  await flush()
  assert.equal(vm.creating.value,true)
  await vm.openSkillDirectory()
  assert.equal(state.calls.filter(c=>c.action==='open_skill_directory').length,countBefore)
 }finally{app?.unmount();await server.close();globalThis.__skillDetailTest=previous;globalThis.window=previousWindow}
})
