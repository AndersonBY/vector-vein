import assert from 'node:assert/strict'
import test from 'node:test'
import {readFile} from 'node:fs/promises'
import {fileURLToPath} from 'node:url'
import {createRenderer,h,nextTick,ref} from 'vue'
import {createI18n} from 'vue-i18n'
import {parse,compileScript} from 'vue/compiler-sfc'
import {createServer} from 'vite'
import {createTemplateData as textSearch} from '../src/components/nodes/tools/TextSearch.js'
import {createTemplateData as imageSearch} from '../src/components/nodes/tools/ImageSearch.js'

const flush=async()=>{for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));await nextTick()}
async function editor(filename,initial,run,extraProps={}){
 const state={errors:[]};globalThis.__embeddingTest=state
 const file=fileURLToPath(new URL('../src/components/settings/'+filename,import.meta.url))
 const {descriptor}=parse(await readFile(file,'utf8'),{filename:file})
 const source=compileScript(descriptor,{id:'embedding-settings'}).content.replaceAll("'ant-design-vue'","'virtual:messages'").replaceAll('"@/components/settings/EmbeddingBackendSettings.vue"',"'virtual:child'").replaceAll('"@/components/QuestionPopover.vue"',"'virtual:child'").replaceAll("'@/components/IconButton.vue'", "'virtual:child'").replaceAll("'./RetrievalModelTest.vue'", "'virtual:child'").replaceAll("'@/utils/util'","'virtual:util'")
 const modules={'/embedding-test.js':source,'virtual:messages':'export const message={error:value=>globalThis.__embeddingTest.errors.push(value)}','virtual:util':'export const deepCopy=value=>JSON.parse(JSON.stringify(value))','virtual:child':'export default {render:()=>null}'}
 const server=await createServer({configFile:false,root:fileURLToPath(new URL('..',import.meta.url)),plugins:[{name:'embedding-fixture',resolveId:id=>Object.hasOwn(modules,id)?id:undefined,load:id=>modules[id]}],resolve:{alias:{'@':fileURLToPath(new URL('../src',import.meta.url))}},server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true},appType:'custom'})
 let app,vm
 try{
  const component=(await server.ssrLoadModule('/embedding-test.js')).default
  const model=ref(initial)
  const wrapper={...component,setup(props,context){vm=component.setup(props,context);return()=>h('div')}}
  const renderer=createRenderer({createElement:()=>({}),createText:()=>({}),createComment:()=>({}),insert(){},remove(){},setText(){},setElementText(){},patchProp(){},parentNode:()=>null,nextSibling:()=>null})
  app=renderer.createApp({render:()=>h(wrapper,{modelValue:model.value,...extraProps,endpoints:[{id:'a'},{id:'b'}],'onUpdate:modelValue':value=>{model.value=value}})})
  const messages=JSON.parse(await readFile(new URL('../src/locales/zh-CN.json',import.meta.url),'utf8'))
  app.use(createI18n({legacy:false,locale:'zh-CN',messages:{'zh-CN':messages}}));app.mount({});await flush()
  await run(vm,model,state)
 }finally{app?.unmount();await server.close();delete globalThis.__embeddingTest}
}

test('sparse embedding settings initialize all seven provider tabs',async()=>{
 await editor('EmbeddingTabsSettings.vue',{openai:{models:{kept:{id:'kept'}}}},async(_vm,model)=>{
  for(const key of ['openai','cohere','jina','voyage','siliconflow','local','custom'])assert.ok(model.value[key].models,key)
  assert.equal(model.value.openai.models.kept.id,'kept')
 })
})

test('missing embedding backend can initialize and accept its first model',async()=>{
 await editor('EmbeddingBackendSettings.vue',undefined,async(vm,model)=>{
  assert.deepEqual(model.value.models,{})
  assert.equal(model.value.default_endpoint,null)
  vm.addNewModel();vm.modelEditKey.value='embed-first';vm.modelForm.id='actual-model';vm.modelForm.protocol='cohere_embed_v2'
  vm.addEndpoint();vm.endpointModelForm.endpoint_id='a';vm.saveEndpoint();vm.saveModel()
  assert.equal(model.value.models['embed-first'].id,'actual-model')
  assert.deepEqual(model.value.models['embed-first'].endpoints,['a'])
 })
})

test('editing embedding endpoint replaces it and duplicate keys cannot overwrite saved models',async()=>{
 const existing={models:{first:{id:'first',endpoints:['a'],enabled:false,protocol:'cohere_embed_v2',dimensions:512,batch_size:8}},default_endpoint:'a'}
 await editor('EmbeddingBackendSettings.vue',existing,async(vm,model,state)=>{
  vm.editModel(model.value.models.first,'first');vm.editEndpoint(0);vm.endpointModelForm.endpoint_id='b';vm.endpointModelForm.model_id='alias';vm.saveEndpoint()
  assert.equal(vm.modelForm.endpoints.length,1)
  vm.saveModel();assert.deepEqual(model.value.models.first.endpoints,[{endpoint_id:'b',model_id:'alias'}]);assert.equal(model.value.models.first.batch_size,8)
  vm.addNewModel();vm.modelEditKey.value='first';vm.modelForm.id='replacement';vm.saveModel()
  assert.equal(model.value.models.first.id,'first');assert.equal(vm.modelFormModalOpen.value,true);assert.match(state.errors.at(-1),/已存在/)
 })
})

test('workflow search choices expose DeepSeek and remove retired engines',()=>{
 assert.deepEqual(textSearch().template.search_engine.options.map(item=>item.value),['deepseek','jina.ai'])
 assert.equal(imageSearch().template.search_engine.value,'pexels')
 assert.deepEqual(imageSearch().template.search_engine.options.map(item=>item.value),['pexels'])
})


test('rerank editor offers all protocols and persists mapping without embedding dimensions', async()=>{
 await editor('EmbeddingBackendSettings.vue',{models:{},default_endpoint:null},async(vm,model)=>{
  assert.deepEqual(vm.protocolOptions.value.map(option=>option.value),['cohere_rerank_v2','jina_rerank_v1','voyage_rerank_v1','siliconflow','custom_json_http'])
  vm.addNewModel(); vm.modelEditKey.value='rerank-key'; vm.modelForm.id='runtime-model'; vm.modelForm.protocol='custom_json_http'
  vm.modelForm.request_mapping_json=JSON.stringify({method:'POST',path:'/v1/rerank'})
  vm.modelForm.response_mapping_json=JSON.stringify({results_path:'$.results[*]',field_map:{index:'index',relevance_score:'relevance_score'}})
  vm.addEndpoint(); vm.endpointModelForm.endpoint_id='b'; vm.endpointModelForm.model_id='alias'; vm.saveEndpoint(); vm.saveModel()
  const saved=JSON.parse(JSON.stringify(model.value))
  assert.equal(saved.models['rerank-key'].id,'runtime-model')
  assert.equal(saved.models['rerank-key'].protocol,'custom_json_http')
  assert.equal(Object.hasOwn(saved.models['rerank-key'],'dimensions'),false)
  assert.deepEqual(saved.models['rerank-key'].endpoints,[{endpoint_id:'b',model_id:'alias'}])
  assert.equal(saved.models['rerank-key'].request_mapping.path,'/v1/rerank')
  assert.equal(saved.models['rerank-key'].response_mapping.results_path,'$.results[*]')
 },{kind:'rerank'})
})
