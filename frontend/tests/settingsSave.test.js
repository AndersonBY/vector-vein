import assert from 'node:assert/strict'
import test from 'node:test'
import {fileURLToPath} from 'node:url'
import {readFile} from 'node:fs/promises'
import {createRenderer, h, nextTick, reactive, ref, ssrContextKey} from 'vue'
import {createI18n} from 'vue-i18n'
import {createServer} from 'vite'
import vue from '@vitejs/plugin-vue'

const copy = value => JSON.parse(JSON.stringify(value))
const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); await nextTick() }
const deferred = () => { let resolve; const promise = new Promise(a => { resolve = a }); return {promise,resolve} }

test('settings and endpoint editor share durable save, retain failed drafts and guard unsaved navigation', async () => {
  const oldWindow = globalThis.window, oldHarness = globalThis.__settingsSave
  const initial = {llm_settings:{endpoints:[{id:'first',api_base:'http://localhost:1/v1',credentials:{}},
    {id:'second',api_base:'http://localhost:2/v1',credentials:{}}],backends:{local:{models:{}}}},
    custom_llms:{},model_preferences:{},shortcuts:{},api:{enabled:false}}
  const state = {stored:copy(initial),calls:[],errors:[],successes:[],confirms:[],leave:null,published:[],catalog:[]}
  state.store = reactive({theme:ref('default'),setSetting:value=>state.published.push(copy(value))})
  state.request = async (action,payload) => {
    if (action==='get_default_settings') return {status:200,data:copy(initial)}
    if (action==='get') return {status:200,data:{id:1,data:copy(state.stored)}}
    if (action==='list_microphones') return {status:200,data:[]}
    state.calls.push(copy(payload))
    state.stored=copy(payload.data)
    return {status:200,data:{id:1,data:copy(state.stored)}}
  }
  globalThis.__settingsSave=state
  globalThis.window={confirm:()=>false}
  const server=await createServer({configFile:false,root:fileURLToPath(new URL('..',import.meta.url)),
    plugins:[vue(),{name:'settings-save-fixtures',enforce:'pre',
      transform(source,id) {
        if (!id.endsWith('.vue')) return
        return source.replace(/from (['"])ant-design-vue\1/g,'from "virtual:save-ant"')
          .replace(/from (['"])vue-router\1/g,'from "virtual:save-router"')
          .replaceAll('@/api/user','virtual:save-api')
          .replaceAll('@/stores/userSettings','virtual:save-store')
          .replaceAll('@/stores/modelCatalog','virtual:save-catalog')
          .replaceAll('@/utils/common','virtual:save-common')
          .replaceAll('@/utils/util','virtual:save-util')
          .replace(/from (['"])@\/components\/(?!settings\/EndpointSettings\.vue)[^'"]+\.vue\1/g,'from "virtual:save-child"')
      },
      resolveId(id) {
        if (id.startsWith('virtual:save-')) return '\0'+id.slice(8)
        if (id==='@/api/user') return '\0save-api'
        if (id==='@/stores/userSettings') return '\0save-store'
        if (id==='@/stores/modelCatalog') return '\0save-catalog'
        if (id==='@/utils/common') return '\0save-common'
        if (id==='@/utils/util') return '\0save-util'
        if (id.startsWith('@/components/') && !id.endsWith('/EndpointSettings.vue')) return '\0save-child'
      },load(id) {
        if (id==='\0save-ant') return 'export const message={error:x=>globalThis.__settingsSave.errors.push(x),success:x=>globalThis.__settingsSave.successes.push(x)};export const Modal={confirm:x=>globalThis.__settingsSave.confirms.push(x)}'
        if (id==='\0save-router') return 'export const onBeforeRouteLeave=fn=>{globalThis.__settingsSave.leave=fn}'
        if (id==='\0save-api') return 'export const settingAPI=(a,p)=>globalThis.__settingsSave.request(a,p);export const hardwareAPI=settingAPI'
        if (id==='\0save-store') return 'export const useUserSettingsStore=()=>globalThis.__settingsSave.store'
        if (id==='\0save-catalog') return 'export const useModelCatalogStore=()=>({setPayloadFromSettings:x=>globalThis.__settingsSave.catalog.push(x)})'
        if (id==='\0save-common') return 'export const getChatModelOptions=()=>[]'
        if (id==='\0save-util') return 'export const deepCopy=x=>JSON.parse(JSON.stringify(x));export const hashObject=x=>JSON.stringify(x)'
        if (id==='\0save-child') return 'export default {render:()=>null}'
      }}],resolve:{alias:{'@':fileURLToPath(new URL('../src',import.meta.url))}},
    server:{middlewareMode:true,hmr:false,ws:false},optimizeDeps:{noDiscovery:true},appType:'custom'})
  let app, page, editor
  try {
    const settings=(await server.ssrLoadModule('/src/views/Settings.vue')).default
    const endpoint=(await server.ssrLoadModule('/src/components/settings/EndpointSettings.vue')).default
    const editorRoot={...endpoint,setup(props,context){editor=endpoint.setup(props,context);return ()=>h('div')}}
    const renderer=createRenderer({createElement:()=>({}),createText:()=>({}),createComment:()=>({}),
      insert(){},remove(){},setText(){},setElementText(){},patchProp(){},parentNode:()=>null,nextSibling:()=>null})
    app=renderer.createApp({setup(props,context){
      page=settings.setup(props,context)
      return ()=>page.settingForm.data.llm_settings ? h(editorRoot,{
        ref:page.endpointEditor,endpoints:page.settingForm.data.llm_settings.endpoints,
        localModels:page.settingForm.data.llm_settings.backends.local,modelFamilyMap:page.settingForm.data.custom_llms,
        saveSettings:page.saveSetting,saving:page.saving.value,onDirty:value=>{page.endpointDraftDirty.value=value},
      }):h('div')
    }})
    app.provide(ssrContextKey,{})
    app.use(createI18n({legacy:false,locale:'en',messages:{en:JSON.parse(await readFile(new URL('../src/locales/en-US.json',import.meta.url),'utf8'))}}))
    app.mount({})
    await flush()
    assert.equal(page.unsavedChanges.value,false)
    editor.switchEndpoint(page.settingForm.data.llm_settings.endpoints[0],0)
    editor.endpointForm.api_base=''
    await flush()
    assert.equal(page.unsavedChanges.value,true)
    assert.equal(state.leave(),false)
    assert.equal(await page.saveSetting(),false)
    assert.equal(state.calls.length,0)
    editor.endpointForm.api_base='http://localhost:3/v1'
    editor.endpointForm.credentials='{broken'
    assert.equal(await page.saveSetting(),false)
    assert.equal(editor.endpointForm.credentials,'{broken')
    assert.equal(state.calls.length,0)
    editor.endpointForm.credentials='{}'
    editor.endpointForm.id='second'
    assert.equal(await page.saveSetting(),false)
    assert.equal(state.calls.length,0)
    editor.endpointForm.id='first'
    const before=copy(page.settingForm.data.llm_settings.endpoints)
    const failure=deferred()
    state.request=async (action,payload)=>{assert.equal(action,'update');state.calls.push(copy(payload));return failure.promise}
    const saving=page.saveSetting()
    await flush()
    assert.equal(page.saving.value,true)
    assert.equal(state.calls.at(-1).data.llm_settings.endpoints[0].api_base,'http://localhost:3/v1')
    assert.deepEqual(copy(page.settingForm.data.llm_settings.endpoints),before,'failed submissions never alter the saved list')
    const count=state.calls.length
    assert.equal(await page.saveSetting(),false)
    editor.addNewEndpoint()
    assert.equal(state.calls.length,count)
    failure.resolve({status:503})
    assert.equal(await saving,false)
    assert.equal(editor.endpointForm.api_base,'http://localhost:3/v1')
    assert.equal(editor.endpointFormStatus.value,'edit')
    assert.equal(state.catalog.length,0,'failed saves cannot publish the settings catalog')
    assert.equal(page.unsavedChanges.value,true)
    const success=deferred()
    state.request=async (action,payload)=>{state.calls.push(copy(payload));return success.promise}
    const retry=editor.props.saveSettings()
    await flush()
    assert.equal(state.calls.at(-1).data.llm_settings.endpoints.length,2)
    // Other sections may be edited while a request is pending; their edits must remain dirty.
    page.settingForm.data.agent={auto_title:true}
    success.resolve({status:200,data:{id:1,data:copy(state.calls.at(-1).data)}})
    assert.equal(await retry,true)
    await flush()
    assert.equal(editor.endpointFormStatus.value,'')
    assert.equal(page.settingForm.data.llm_settings.endpoints[0].api_base,'http://localhost:3/v1')
    assert.equal(page.unsavedChanges.value,true)
    assert.equal(state.catalog.length,1)
    state.request=async (action,payload)=>{state.calls.push(copy(payload));state.stored=copy(payload.data);return {status:200,data:{id:1,data:copy(state.stored)}}}
    await page.saveSetting()
    await flush()
    assert.equal(page.unsavedChanges.value,false)
    assert.equal(state.leave(),true)
    editor.resetForm()
    editor.endpointForm.id='new'
    editor.endpointForm.api_base='http://localhost:4/v1'
    editor.endpointForm.credentials='{"project_id":"fixture"}'
    await flush()
    assert.equal(page.unsavedChanges.value,true,'credentials and open drafts count as unsaved changes')
    editor.endpointFormEdit(page.settingForm.data.llm_settings.endpoints[0],0)
    const confirmation=state.confirms.at(-1)
    confirmation.onCancel?.()
    assert.equal(editor.endpointForm.id,'new','canceling a switch keeps the current draft')
    await confirmation.onOk()
    await flush()
    assert.equal(page.settingForm.data.llm_settings.endpoints.length,3)
    assert.equal(editor.endpointForm.id,'first')
    editor.endpointForm.credentials='{"project_id":"edited"}'
    await flush()
    assert.equal(page.unsavedChanges.value,true)
    editor.closeEditor()
    await flush()
    assert.equal(page.unsavedChanges.value,false,'canceling an edit keeps the persisted endpoint unchanged')
    page.settingForm.data.shortcuts={fixture:'ctrl+alt+k'}
    await page.saveSetting()
    assert.equal(state.calls.at(-1).update_shortcuts,true)
    page.selectedKeys.value=['embedding_models']
    await flush()
    assert.equal(page.unsavedChanges.value,false)
  } finally {
    app?.unmount()
    await server.close()
    globalThis.window=oldWindow
    globalThis.__settingsSave=oldHarness
  }
})
