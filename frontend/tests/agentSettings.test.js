import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick, reactive } from 'vue'
import { createI18n } from 'vue-i18n'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'
import { createServer } from 'vite'

const copy = value => JSON.parse(JSON.stringify(value))
const flush = async () => { for (let i = 0; i < 12; i++) await Promise.resolve(); await nextTick() }
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b }); return { promise, resolve, reject } }
const find = (node, type) => [...(node.type === type ? [node] : []), ...(node.children || []).flatMap(child => find(child, type))]
const agent = (extra = {}) => ({ aid: 'a', is_owner: true, name: 'Agent', description: 'Description', avatar: '', model_provider: 'OpenAI', model: 'current', settings: { system_prompt: 'Original', opening_dialog: { text: '', questions: [] } }, related_workflows: [{ wid: 'w', title: 'Workflow' }], related_templates: [{ tid: 't', title: 'Template' }], ...extra })

async function source(path, id) {
  const filename = fileURLToPath(new URL(path, import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const script = compileScript(descriptor, { id })
  script.content = script.content.replaceAll('vue-router', 'virtual:agent-router').replaceAll('ant-design-vue', 'virtual:agent-ant')
  const template = compileTemplate({ source: descriptor.template.content, filename, id, compilerOptions: { bindingMetadata: script.bindings } }).code.replace('export function render', 'function render')
  return `${script.content.replace('export default', 'const component =')}\n${template}\ncomponent.render = render; export default component`
}

async function harness(initial = agent()) {
  const previous = globalThis.__agentSettingsTest, previousWindow = globalThis.window
  const data = { stored: copy(initial), calls: [], errors: [], successes: [], route: reactive({ params: { agentId: 'a' }, query: {} }), validate: async () => {}, leave: null,
    catalog: reactive({ loaded: true, loading: false, loadError: '', ensureLoaded: async () => {}, generalModelOptions: [{ value: 'OpenAI', label: 'OpenAI', children: [{ value: 'current', label: 'Current' }] }, { value: 'Other', label: 'Other', children: [{ value: 'other', label: 'Other' }] }] }) }
  data.request = async (action, payload) => {
    if (action === 'get') return { status: 200, data: copy(data.stored) }
    data.stored = { ...copy(payload), related_workflows: payload.related_workflows?.map(wid => ({ wid })) || data.stored.related_workflows, related_templates: payload.related_templates?.map(tid => ({ tid })) || data.stored.related_templates }
    return { status: 200, data: copy(data.stored) }
  }
  globalThis.__agentSettingsTest = data
  globalThis.window = { confirm: () => false }
  const modules = {
    '/agent-test.js': await source('../src/views/Workspace/Agent/AgentDetail.vue', 'agent-test'),
    '/conversation-test.js': await source('../src/views/Workspace/Chat/ConversationNew.vue', 'agent-conversation-test'),
    '@/components/ModelPicker.vue': await source('../src/components/ModelPicker.vue', 'agent-model-picker'),
    '@/utils/modelPreferences': (await readFile(new URL('../src/utils/modelPreferences.js', import.meta.url), 'utf8')).replace("'./modelSelection'", "'@/utils/modelSelection'"),
    '@/stores/userSettings': 'export const useUserSettingsStore=()=>({setting:{data:{}}})',
    '@/components/ModelSelector.vue': await source('../src/components/ModelSelector.vue', 'agent-model-selector'),
    '@/utils/modelSelection': await readFile(new URL('../src/utils/modelSelection.js', import.meta.url), 'utf8'),
    'virtual:agent-router': 'export const useRoute = () => globalThis.__agentSettingsTest.route; export const useRouter = () => ({push:async()=>{}}); export const onBeforeRouteLeave = cb => {globalThis.__agentSettingsTest.leave=cb}',
    'virtual:agent-ant': 'import {ref} from "vue"; export const theme={useToken:()=>({token:ref({colorBorder:"#ddd",colorTextSecondary:"#777"})})}; export const message = { error: x=>globalThis.__agentSettingsTest.errors.push(x), success:x=>globalThis.__agentSettingsTest.successes.push(x) }',
    '@/utils/util': 'export const deepCopy = x=>JSON.parse(JSON.stringify(x)); export const hashObject = x=>JSON.stringify(x); export const formatTime = ()=>""; export const navigateToElementBottom=()=>{}',
    '@/utils/common': 'export const getChatModelOptions=()=>globalThis.__agentSettingsTest.catalog.generalModelOptions; export const websiteBase=""; export const agentVoiceOptions=[]; export const defaultSettings={en:{}}',
    '@/stores/modelCatalog': 'export const useModelCatalogStore=()=>globalThis.__agentSettingsTest.catalog',
    '@/stores/userChats': 'export const useUserChatsStore=()=>({})',
    '@/utils/useChatDraft': 'import {ref} from "vue"; export const useChatDraft=()=>({userInput:ref(""),attachments:ref([]),draftOwner:ref([])})',
    '@/api/chat': 'export const agentAPI=async(action,payload)=>{const t=globalThis.__agentSettingsTest;if(action!=="get")t.calls.push(payload);return t.request(action,payload)}; export const conversationAPI=async()=>({status:500})',
    '@/api/workflow': 'export const workflowAPI=async()=>({status:500})', '@/api/remote': 'export const officialSiteAPI=async()=>({status:500})',
    '@/icons': 'export const EditTwo={render:()=>null},CloseOne=EditTwo,Share=EditTwo,Send=EditTwo,Link=EditTwo,CheckOne=EditTwo,Down=EditTwo',
    '@/assets/logo.svg': 'export default "logo"',
  }
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)), plugins: [{ name: 'agent-settings-fixtures', resolveId(id) { if (Object.hasOwn(modules, id)) return '\0fixture:' + id; if (id.startsWith('@/components/')) return '\0child:' + id }, load(id) { return modules[id.replace('\0fixture:', '')] || (id.startsWith('\0child:') ? `import {h} from 'vue'; export default {inheritAttrs:false,setup:(_,ctx)=>()=>h('Child',ctx.attrs,ctx.slots.default?.())}` : undefined) } }], server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  const apps = []
  async function mount(path = '/agent-test.js') {
    const component = (await server.ssrLoadModule(path)).default
    const renderer = createRenderer({ createElement: type => ({ type, props: {}, children: [], style: {} }), createText: text => ({ text }), createComment: text => ({ text }), setText: (n, text) => { n.text = text }, setElementText: (n, text) => { n.text = text }, parentNode: n => n.parent, nextSibling: () => null, patchProp: (n, key, old, value) => { n.props[key] = value }, insert(n, p) { n.parent = p; p.children.push(n) }, remove(n) { if (n.parent) n.parent.children.splice(n.parent.children.indexOf(n), 1) } })
    const app = renderer.createApp({ render: () => h(component) })
    app.use(createI18n({ legacy: false, locale: 'en', messages: { en: JSON.parse(await readFile(new URL('../src/locales/en-US.json', import.meta.url), 'utf8')) } }))
    const template = (await Promise.all(['Agent/AgentDetail.vue', 'Chat/ConversationNew.vue'].map(path => readFile(new URL('../src/views/Workspace/' + path, import.meta.url), 'utf8')))).join('\n')
    const names = new Set([...template.matchAll(/<(a-[\w-]+)/g)].map(x => x[1].split('-').map(x => x[0].toUpperCase() + x.slice(1)).join('')))
    for (const name of new Set([...names, 'AMenu', 'AMenuItem', 'AMenuDivider', 'ADropdown', 'ASlider', 'ACascader', 'AInput', 'ATypographyText'])) app.component(name, { inheritAttrs: false, setup(_, { attrs, slots, expose }) { expose({ validate: () => data.validate() }); return () => h(name, attrs, [slots.default?.(), slots.overlay?.()]) } })
    const root = { children: [] }; app.mount(root); apps.push(app); await flush()
    return { app, root, state: app._instance.subTree.component.setupState }
  }
  return { data, mount, close: async () => { apps.forEach(app => app.unmount()); await server.close(); globalThis.__agentSettingsTest = previous; globalThis.window = previousWindow } }
}

test('AgentDetail binds provider/model, preserves unavailable history and prevents invalid or readonly saves', async () => {
  const t = await harness(agent({ model: 'retired' }))
  try {
    const { state, root } = await t.mount()
    assert.equal(state.agentData.model, 'retired')
    await state.save(); assert.equal(t.data.calls.length, 0)
    t.data.catalog.generalModelOptions[0].children.push({ value: 'retired', label: 'Restored' }); await flush()
    assert.equal(state.agentData.model, 'retired')
    find(root, 'AMenu')[0].props.onClick({key:'custom'}); await flush()
    const provider = find(root, 'AMenu').filter(node => node.props.items)[0]
    provider.props.onClick({ key: 'Other' }); await flush()
    assert.equal(state.agentData.model_provider, 'OpenAI'); assert.equal(state.agentData.model, 'retired')
    const model = find(root, 'AMenu').filter(node => node.props.items)[1]
    model.props.onClick({ key: 'other' }); await flush()
    await find(root, 'AModal').find(node => node.props.title === 'Custom').props.onOk(); await flush()
    assert.equal(state.agentData.model, 'other')
    state.agentData.is_owner = false; await flush()
    assert.equal(find(root, 'button').find(node => node.props.class === 'selected-model-tag').props.disabled, true)
    provider.props.onClick({ key: 'OpenAI' }); model.props.onClick({ key: 'current' }); await flush()
    assert.equal(state.agentData.model_provider, 'Other'); assert.equal(state.agentData.model, 'other')
    await state.save(); assert.equal(t.data.calls.length, 0)
  } finally { await t.close() }
})

test('AgentDetail snapshots nested drafts, retains failures, rejects duplicate saves and preserves edits during retry', async () => {
  const t = await harness()
  try {
    const { state } = await t.mount()
    state.agentData.settings.system_prompt = 'First draft'
    const pending = deferred(); t.data.request = () => pending.promise
    const saving = state.save(); const duplicate = state.save(); await state.modifyAgentModal.ok()
    assert.equal(t.data.calls.length, 1); assert.equal(state.saving, true)
    state.agentData.settings.system_prompt = 'Later draft'
    state.selectedFlows.workflows.w.title = 'Later workflow'
    assert.equal(t.data.calls[0].settings.system_prompt, 'First draft')
    pending.reject(new Error('network')); await saving; await duplicate
    assert.equal(state.saving, false); assert.equal(state.agentData.settings.system_prompt, 'Later draft')
    assert.equal(state.savedAgentData.settings.system_prompt, 'Original')
    assert.ok(state.selectedFlows.templates.t)
    const retry = deferred(); t.data.request = () => retry.promise
    const retried = state.save(); const snapshot = copy(t.data.calls[1])
    state.agentData.settings.opening_dialog.questions.push('New question')
    delete state.selectedFlows.templates.t
    retry.resolve({ status: 200, data: agent({ ...snapshot, related_workflows: [{ wid: 'w' }], related_templates: [{ tid: 't' }] }) }); await retried
    assert.equal(state.savedAgentData.settings.system_prompt, 'Later draft')
    assert.deepEqual(state.agentData.settings.opening_dialog.questions, ['New question'])
    assert.equal(state.selectedFlows.templates.t, undefined)
    assert.ok(state.savedSelectedFlows.templates.t)
  } finally { await t.close() }
})

test('AgentDetail ignores saves resolved after unmount', async () => {
  const t = await harness()
  try {
    const { state, app } = await t.mount(); const pending = deferred(); t.data.request = () => pending.promise
    const save = state.save(); app.unmount(); pending.resolve({ status: 200, data: agent({ name: 'Late' }) }); await save
    assert.equal(state.agentData.name, 'Agent'); assert.equal(t.data.successes.length, 0)
  } finally { await t.close() }
})

test('AgentDetail ignores an old save after loading another agent and keeps failed responses dirty', async () => {
  const t = await harness()
  try {
    const { state } = await t.mount()
    state.agentData.settings.system_prompt = 'Draft'
    t.data.request = async () => ({ status: 500, msg: 'Unavailable' })
    await state.save()
    assert.equal(state.saving, false); assert.equal(state.agentData.settings.system_prompt, 'Draft')
    assert.equal(state.savedAgentData.settings.system_prompt, 'Original')
    let left; t.data.leave({}, {}, value => { left = value }); assert.equal(left, false)
    const pending = deferred()
    t.data.request = async action => action === 'get' ? { status: 200, data: agent({ aid: 'b', name: 'Second agent' }) } : pending.promise
    const oldSave = state.save()
    await state.loadAgentData('b')
    pending.resolve({ status: 200, data: agent({ name: 'Old response' }) }); await oldSave
    assert.equal(state.agentData.aid, 'b'); assert.equal(state.agentData.name, 'Second agent')
    assert.equal(state.savedAgentData.aid, 'b')
  } finally { await t.close() }
})

test('metadata save awaits validation, keeps failures open and updates only metadata baselines', async () => {
  const t = await harness()
  try {
    const { state } = await t.mount()
    state.modifyAgentModal.open = true
    const validation = deferred(); t.data.validate = () => validation.promise
    const validating = state.modifyAgentModal.ok(); await flush(); assert.equal(t.data.calls.length, 0)
    validation.reject(new Error('required')); await validating
    assert.equal(state.modifyAgentModal.modifyLoading, false); assert.equal(state.modifyAgentModal.open, true)
    t.data.validate = async () => {}; t.data.request = async () => { throw new Error('network') }
    await state.modifyAgentModal.ok(); assert.equal(state.modifyAgentModal.open, true); assert.equal(state.modifyAgentModal.modifyLoading, false)
    t.data.request = async () => ({ status: 500, msg: 'Unavailable' }); await state.modifyAgentModal.ok()
    assert.equal(state.modifyAgentModal.open, true); assert.equal(state.modifyAgentModal.modifyLoading, false)
    state.agentData.settings.system_prompt = 'Unsaved prompt'; state.agentData.model_provider = 'Other'; state.agentData.model = 'other'; delete state.selectedFlows.workflows.w
    state.modifyAgentModal.form.name = 'Renamed'
    const pending = deferred(); t.data.request = () => pending.promise
    const metadata = state.modifyAgentModal.ok(); await flush(); const count = t.data.calls.length
    await state.save(); await state.modifyAgentModal.ok(); assert.equal(t.data.calls.length, count)
    pending.resolve({ status: 200, data: agent({ name: 'Renamed' }) }); await metadata
    assert.equal(state.agentData.name, 'Renamed'); assert.equal(state.savedAgentData.name, 'Renamed')
    assert.equal(state.agentData.settings.system_prompt, 'Unsaved prompt'); assert.equal(state.agentData.model, 'other'); assert.equal(state.agentData.model_provider, 'Other')
    assert.equal(state.savedAgentData.settings.system_prompt, 'Original'); assert.ok(state.savedSelectedFlows.workflows.w)
    assert.equal(state.selectedFlows.workflows.w, undefined); assert.equal(state.modifyAgentModal.open, false)
  } finally { await t.close() }
})

test('saved agent model, provider and settings load into a real ConversationNew component', async () => {
  const t = await harness()
  try {
    const { state } = await t.mount()
    state.agentData.model_provider = 'Other'; state.agentData.model = 'other'; state.agentData.settings.system_prompt = 'Saved prompt'
    await state.save()
    const chat = await t.mount('/conversation-test.js')
    assert.equal(chat.state.conversation.model_provider, 'Other'); assert.equal(chat.state.conversation.model, 'other')
    assert.equal(chat.state.conversation.settings.system_prompt, 'Saved prompt')
  } finally { await t.close() }
})
