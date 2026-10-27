import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { computed, createRenderer, h, nextTick, reactive } from 'vue'
import { createI18n } from 'vue-i18n'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'
import { createServer } from 'vite'

const flush = async () => { for (let i = 0; i < 5; i++) await nextTick() }
const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const findAll = (node, type) => [...(node.type === type ? [node] : []), ...(node.children || []).flatMap(child => findAll(child, type))]
const renderer = () => createRenderer({
  createElement: type => ({ type, children: [], props: {} }), createText: text => ({ text }), createComment: text => ({ text }),
  setText: (node, text) => { node.text = text }, setElementText: (node, text) => { node.text = text }, parentNode: node => node.parent,
  nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
  patchProp: (node, key, _old, value) => { node.props[key] = value },
  insert: (node, parent, anchor) => { if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1); node.parent = parent; const index = anchor ? parent.children.indexOf(anchor) : -1; if (index < 0) parent.children.push(node); else parent.children.splice(index, 0, node) },
  remove: node => { if (node?.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1) },
})

async function componentSource(path, id) {
  const filename = fileURLToPath(new URL(path, import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const compiled = compileScript(descriptor, { id })
  const script = compiled.content.replace('export default', 'const component =')
  const template = compileTemplate({ source: descriptor.template.content, filename, id, compilerOptions: { bindingMetadata: compiled.bindings } }).code.replace('export function render', 'function render')
  return `${script}\n${template}\ncomponent.render = render; export default component`
}

async function setupModules(extra = {}) {
  const modules = {
    '@/components/ModelPicker.vue': await componentSource('../src/components/ModelPicker.vue', 'model-picker-test'),
    '@/components/ModelSelector.vue': await componentSource('../src/components/ModelSelector.vue', 'model-selector'),
    '@/utils/modelPreferences': (await readFile(new URL('../src/utils/modelPreferences.js', import.meta.url), 'utf8')).replace("'./modelSelection'", "'@/utils/modelSelection'"),
    '@/stores/userSettings': 'export const useUserSettingsStore = () => globalThis.__pickerSettings || {setting:{data:{}}}',
    '@/icons': 'export const CheckOne={render:()=>null},Down=CheckOne;',
    '/model-selector-test.js': await componentSource('../src/components/ModelSelect.vue', 'model-select-test'),
    '/grouped-model-selector-test.js': await componentSource('../src/components/ModelSelector.vue', 'grouped-model-selector-test'),
    '@/components/ModelSelect.vue': await componentSource('../src/components/ModelSelect.vue', 'flat-model-select'),
    '@/utils/modelSelection': await readFile(new URL('../src/utils/modelSelection.js', import.meta.url), 'utf8'),
    'ant-design-vue': 'import {ref} from "vue"; export const theme = {useToken:()=>({token:ref({colorBorder:"#ddd",colorTextSecondary:"#777"})})}',
    ...extra,
  }
  return createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'mounted-model-selection', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }],
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
}

async function mount(component, props) {
  const app = renderer().createApp({ render: () => h(component, props) })
  app.use(createI18n({ legacy: false, locale: 'en', messages: { en: JSON.parse(await readFile(new URL('../src/locales/en-US.json', import.meta.url), 'utf8')) } }))
  for (const name of ['ADropdown', 'AMenuItem', 'AMenuDivider', 'ASlider', 'ACascader', 'AMenu', 'ASelect', 'AAlert', 'APopover', 'AModal', 'ARow', 'ACol', 'AForm', 'AFormItem', 'ATypographyText', 'AFlex', 'ATextarea', 'ACheckbox', 'AInputNumber', 'AInput', 'AButton', 'ADrawer', 'ACheckboxGroup', 'ASelectOption']) {
    app.component(name, { inheritAttrs: false, props: ['showSearch', 'filterOption', 'okButtonProps', 'confirmLoading', 'selectedKeys'], setup: (props, { attrs, slots }) => () => h(name, { ...attrs, ...props }, [slots.default?.(), slots.overlay?.()]) })
  }
  const root = { children: [] }
  app.mount(root)
  return { app, root }
}

test('mounted selector searches names and IDs, preserves unavailable values and normalizes clearing', async () => {
  const server = await setupModules()
  let mounted
  try {
    const component = (await server.ssrLoadModule('/model-selector-test.js')).default
    const updates = []
    const props = reactive({ modelValue: 'retired', options: [{ value: 'GPT-4', label: 'Friendly Name' }], ready: false,
      'onUpdate:modelValue': value => updates.push(value) })
    mounted = await mount(component, props)
    const select = () => findAll(mounted.root, 'ASelect')[0]
    assert.equal(select().props.showSearch, '')
    assert.equal(select().props.filterOption('friendly', props.options[0]), true)
    assert.equal(select().props.filterOption('gPt-4', props.options[0]), true)
    assert.equal(select().props.filterOption('absent', props.options[0]), false)
    assert.equal(select().props['aria-invalid'], false)
    props.ready = true; await flush()
    assert.equal(select().props['aria-invalid'], true)
    assert.equal(select().props.value, 'retired')
    props.options = [{ value: 'retired', label: 'Restored' }]; await flush()
    assert.equal(select().props['aria-invalid'], false)
    props.options = []; props.loading = true; await flush()
    assert.equal(select().props.disabled, true)
    assert.equal(select().props['aria-invalid'], false)
    assert.deepEqual(updates, [], 'readiness and catalog changes never rewrite saved values')
    select().props['onUpdate:value'](undefined)
    select().props['onUpdate:value']('new-model')
    assert.deepEqual(updates, ['', 'new-model'])
  } finally { mounted?.app.unmount(); await server.close() }
})

test('grouped cascader preserves saved pairs, searches labels and IDs, and rejects invalid or disabled choices', async () => {
  const server = await setupModules()
  let mounted
  try {
    const changes = []
    const props = reactive({ modelProvider: '_local__Family', model: 'retired', ready: false, options: [],
      'onUpdate:modelProvider': value => { changes.push(['provider', value]); props.modelProvider = value },
      'onUpdate:model': value => { changes.push(['model', value]); props.model = value } })
    mounted = await mount((await server.ssrLoadModule('/grouped-model-selector-test.js')).default, props)
    const select = () => findAll(mounted.root, 'ACascader')[0]
    assert.deepEqual(select().props.value, ['_local__Family', 'retired'])
    assert.equal(select().props['aria-invalid'], false)
    props.ready = true; await flush()
    assert.equal(select().props['aria-invalid'], true)
    props.options = [{ value: '_local__Family', labelText: 'Family', children: [{ value: 'retired', label: 'Friendly' }, { value: 'disabled', disabled: true }] }]
    await flush()
    assert.equal(select().props['aria-invalid'], false)
    assert.equal(select().props.options[0].label, 'Family')
    const path = [select().props.options[0], props.options[0].children[0]]
    assert.equal(select().props.showSearch.filter('fRiEnDlY', path), true)
    assert.equal(select().props.showSearch.filter('RETIRED', path), true)
    assert.equal(select().props.showSearch.filter('family', path), true)
    assert.equal(select().props.showSearch.filter('missing', path), false)
    select().props.onChange(['_local__Family', 'disabled'])
    select().props.onChange(['missing', 'retired'])
    props.disabled = true; await flush(); select().props.onChange(undefined)
    props.disabled = false; props.loading = true; await flush(); select().props.onChange(undefined)
    assert.deepEqual(changes, [], 'loading, catalog refreshes and rejected choices never rewrite the saved pair')
    props.loading = false; await flush(); select().props.onChange(undefined); await flush()
    assert.equal(props.modelProvider, ''); assert.equal(props.model, '')
    select().props.onChange(['_local__Family', 'retired']); await flush()
    assert.equal(props.modelProvider, '_local__Family'); assert.equal(props.model, 'retired')
  } finally { mounted?.app.unmount(); await server.close() }
})

test('expanded selector shares pair state, clears only on a different provider, searches, and respects readonly menus', async () => {
  const server = await setupModules()
  let mounted
  try {
    const changes = []
    const props = reactive({ expanded: true, modelProvider: 'OpenAI', model: 'shared',
      options: [{ value: 'OpenAI', label: 'OpenAI', children: [{ value: 'shared', label: 'First' }] },
        { value: 'Other', label: 'Other', children: [{ value: 'shared', label: 'Second' }, { value: 'off', disabled: true }] }],
      'onUpdate:modelProvider': value => { changes.push(value); props.modelProvider = value },
      'onUpdate:model': value => { changes.push(value); props.model = value } })
    mounted = await mount((await server.ssrLoadModule('/grouped-model-selector-test.js')).default, props)
    const menus = () => findAll(mounted.root, 'AMenu')
    menus()[0].props.onClick({ key: 'OpenAI' }); await flush()
    assert.deepEqual(changes, [], 'clicking the active provider retains its model')
    menus()[0].props.onClick({ key: 'Other' }); await flush()
    assert.equal(props.modelProvider, 'Other'); assert.equal(props.model, '')
    assert.deepEqual(menus()[1].props.selectedKeys, [])
    menus()[1].props.onClick({ key: 'off' }); await flush(); assert.equal(props.model, '')
    menus()[1].props.onClick({ key: 'shared' }); await flush(); assert.equal(props.model, 'shared')
    findAll(mounted.root, 'AInput')[0].props['onUpdate:value']('SECOND'); await flush()
    assert.deepEqual(menus()[0].props.items.map(item => item.key), ['Other'])
    assert.deepEqual(menus()[1].props.items.map(item => item.key), ['shared'])
    findAll(mounted.root, 'AInput')[0].props['onUpdate:value']('absent'); await flush()
    assert.deepEqual(menus()[0].props.items, []); assert.deepEqual(menus()[1].props.items, [])
    assert.equal(props.model, 'shared', 'search filters do not change selection')
    findAll(mounted.root, 'AInput')[0].props['onUpdate:value'](''); await flush()
    props.disabled = true; await flush()
    assert.ok(menus().every(menu => menu.props.disabled))
    menus()[0].props.onClick({ key: 'OpenAI' }); menus()[1].props.onClick({ key: 'off' }); await flush()
    assert.equal(props.modelProvider, 'Other'); assert.equal(props.model, 'shared')
    props.disabled = false; props.modelProvider = 'OpenAI'; props.model = 'shared'; await flush()
    assert.deepEqual(menus()[0].props.selectedKeys, ['OpenAI']); assert.deepEqual(menus()[1].props.selectedKeys, ['shared'])
    props.options = []; await flush()
    assert.equal(props.modelProvider, 'OpenAI'); assert.equal(props.model, 'shared')
  } finally { mounted?.app.unmount(); await server.close() }
})

test('compact picker applies configured presets and supported reasoning, while catalog refreshes preserve saved pairs', async () => {
  const previous = globalThis.__pickerSettings
  const settings = reactive({ setting: { data: {
    model_preferences: { high_performance: { model_provider: 'Gemini', model: 'reasoner' } },
    llm_settings: { backends: { gemini: { models: { reasoner: { capabilities: { reasoning_efforts: ['low', 'high'] } } } } } },
  } } })
  globalThis.__pickerSettings = settings
  const server = await setupModules()
  let mounted
  try {
    const changes = []
    const props = reactive({ modelProvider: 'OpenAI', model: 'old', preference: 'custom', reasoningEffort: 'max',
      options: [{ value: 'OpenAI', label: 'OpenAI', children: [{ value: 'old', label: 'Old' }] },
        { value: 'Gemini', label: 'Gemini', children: [{ value: 'reasoner', label: 'Reasoner' }] }],
      'onUpdate:modelProvider': value => { props.modelProvider = value; changes.push(value) },
      'onUpdate:model': value => { props.model = value; changes.push(value) },
      'onUpdate:preference': value => { props.preference = value },
      'onUpdate:reasoningEffort': value => { props.reasoningEffort = value },
    })
    mounted = await mount((await server.ssrLoadModule('@/components/ModelPicker.vue')).default, props)
    const menu = () => findAll(mounted.root, 'AMenu')[0]
    menu().props.onClick({key:'default'}); await flush()
    assert.deepEqual(changes, [], 'unconfigured presets cannot replace a saved model')
    menu().props.onClick({key:'high_performance'}); await flush()
    assert.equal(props.modelProvider, 'Gemini'); assert.equal(props.model, 'reasoner')
    assert.equal(props.preference, 'high_performance'); assert.equal(props.reasoningEffort, 'default', 'unsupported effort resets on an explicit model choice')
    const slider = () => findAll(mounted.root, 'ASlider')[0]
    assert.equal(slider().props.max, 2, 'slider only exposes default and model-supported levels')
    slider().props.onAfterChange(2); await flush()
    assert.equal(props.reasoningEffort, 'high')
    const count = changes.length
    settings.setting.data.model_preferences.high_performance.model = 'removed'
    await flush()
    assert.equal(props.model, 'reasoner'); assert.equal(changes.length, count)
    assert.deepEqual(menu().props.selectedKeys, ['custom'], 'a changed preset no longer claims the old saved model')
    props.disabled = true; await flush(); slider().props.onAfterChange(1); menu().props.onClick({key:'custom'}); await flush()
    assert.equal(props.reasoningEffort, 'high'); assert.equal(findAll(mounted.root, 'AModal')[0].props.open, false)
    props.disabled = false; props.modelProvider = 'OpenAI'; props.model = ''; await flush()
    assert.equal(findAll(mounted.root, 'div').some(node => node.props.class === 'picker-error'), false, 'a new node with an empty model is not reported as a retired model')
  } finally { mounted?.app.unmount(); globalThis.__pickerSettings = previous; await server.close() }
})

for (const name of ['UniversalLlm', 'CustomModel', 'LocalLlm']) {
  test(`mounted ${name} preserves restored values while explicit provider or family changes clear the model`, async () => {
    const previous = globalThis.__workflowSelectionCatalog
    const catalog = reactive({ edges: [], loaded: true, loading: false, loadError: '', ensureLoaded: async () => {},
      generalModelOptions: [{ value: 'OpenAI', label: 'OpenAI', children: [{ value: 'current', label: 'Current' }] },
        { value: 'Other', label: 'Other', children: [{ value: 'other', label: 'Other Model' }] }],
      modelFamilies: [{ key: 'family', label: 'Family', isCustom: true }, { key: 'other', label: 'Other', isCustom: true }],
      familyMap: { family: [{ key: 'current', id: 'Current' }], other: [{ key: 'other', id: 'Other Model' }] } })
    globalThis.__workflowSelectionCatalog = catalog
    const source = (await componentSource(`../src/components/nodes/llms/${name}.vue`, `workflow-${name}`))
      .replace(/(['"])\.\/_(?:BaseLLM)\.vue\1/g, "'virtual:workflow-base'")
      .replace(/(['"])\.\/(?:UniversalLlm|CustomModel|LocalLlm)(?:\.js)?\1/g, "'virtual:workflow-template'")
    const server = await setupModules({
      '/workflow-selection-test.js': source.replace("'@vue-flow/core'", "'virtual:workflow-flow'"),
      'virtual:workflow-flow': 'import {toRef} from "vue"; export const useVueFlow=()=>({edges:toRef(globalThis.__workflowSelectionCatalog,"edges")})',
      '@/components/ModelSelector.vue': await componentSource('../src/components/ModelSelector.vue', 'workflow-model-selector'),
      '@/stores/modelCatalog': 'export const useModelCatalogStore = () => globalThis.__workflowSelectionCatalog',
      '@/utils/modelCatalog': await readFile(new URL('../src/utils/modelCatalog.js', import.meta.url), 'utf8'),
      'virtual:workflow-template': 'export const createTemplateData = () => ({template:{model_provider:{value:"OpenAI"},model_family:{value:"family"},model_preference:{value:"custom"},reasoning_effort:{value:"default"},llm_model:{value:""}}})',
      'virtual:workflow-base': 'import {h} from "vue"; export default {setup:(_, {slots})=>()=>h("workflow-base",slots.modelSelection?.())}',
      '@/components/nodes/BaseField.vue': 'import {h} from "vue"; export default {setup:(_, {slots})=>()=>h("workflow-field",[slots.default?.(),slots.inline?.()])}',
      '@/components/nodes/BaseNode.vue': 'import {h} from "vue"; export default {setup:(_, {slots})=>()=>h("workflow-base",[slots["field-model_family"]?.(),slots["field-llm_model"]?.()])}',
      '@/components/ModelCapabilities.vue': 'export default {render:()=>null}',
    })
    let mounted
    try {
      const field = name === 'UniversalLlm' ? 'model_provider' : 'model_family'
      const initial = name === 'UniversalLlm' ? 'OpenAI' : 'family'
      const other = name === 'UniversalLlm' ? 'Other' : 'other'
      const data = reactive({ template: { [field]: { value: initial }, llm_model: { value: 'retired' } } })
      mounted = await mount((await server.ssrLoadModule('/workflow-selection-test.js')).default, { id: 'node', data })
      await flush()
      if (name === 'UniversalLlm') {
        assert.equal(findAll(mounted.root, 'workflow-field').length, 1, 'ordinary nodes show only the model row')
        catalog.edges.push({source:'upstream',target:'node',targetHandle:'model_provider'}); await flush()
        assert.equal(findAll(mounted.root, 'workflow-field').length, 2, 'existing provider connections keep their field and handle')
        catalog.edges = []; await flush()
        const modal = () => findAll(mounted.root, 'AModal')[0]
        const menus = () => findAll(mounted.root, 'AMenu').filter(node => node.props.items)
        const open = async () => { findAll(mounted.root, 'AMenu')[0].props.onClick({key:'custom'}); await flush() }
        await open()
        assert.deepEqual(menus()[0].props.selectedKeys, ['OpenAI'])
        assert.deepEqual(menus()[1].props.selectedKeys, ['retired'])
        assert.equal(modal().props.okButtonProps.disabled, true)
        catalog.generalModelOptions[0].children = [{ value: 'refreshed', label: 'Refreshed' }]
        await flush()
        assert.equal(data.template.llm_model.value, 'retired')
        assert.equal(menus()[1].props.items[0].key, 'refreshed')
        menus()[0].props.onClick({key:'Other'}); await flush()
        menus()[1].props.onClick({key:'other'}); await flush()
        assert.equal(data.template.llm_model.value, 'retired', 'custom dialog changes remain a draft')
        modal().props.onCancel(); await flush()
        await open(); assert.deepEqual(menus()[0].props.selectedKeys, ['OpenAI'])
        menus()[0].props.onClick({key:'Other'}); await flush()
        menus()[1].props.onClick({key:'other'}); await flush()
        await modal().props.onOk(); await flush()
        assert.equal(data.template[field].value, 'Other'); assert.equal(data.template.llm_model.value, 'other')
        assert.equal(data.template.model_preference.value, 'custom'); assert.equal(data.template.reasoning_effort.value, 'default')
      } else {
        const selects = () => findAll(mounted.root, 'ASelect')
        assert.equal(selects().length, 2)
        assert.equal(selects()[1].props.value, 'retired')
        assert.equal(data.template.llm_model.value, 'retired')
        assert.deepEqual(selects()[1].props.options, [{ value: 'current', label: 'Current' }])
        catalog.familyMap.family = [{ key: 'refreshed', id: 'Refreshed' }]
        await flush()
        assert.deepEqual(selects()[1].props.options, [{ value: 'refreshed', label: 'Refreshed' }])
        assert.equal(data.template.llm_model.value, 'retired', 'catalog refresh does not replace saved values')
        data.template[field].value = other; data.template.llm_model.value = 'other'; await flush()
        assert.equal(selects()[1].props.value, 'other', 'external paired restoration does not act like a user change')
        selects()[0].props['onUpdate:value'](initial); selects()[0].props.onChange(initial); await flush()
        assert.equal(data.template.llm_model.value, ''); assert.equal(selects()[1].props.value, undefined)
      }
    } finally { mounted?.app.unmount(); globalThis.__workflowSelectionCatalog = previous; await server.close() }
  })
}

test('mounted chat selector commits only successful saves and ignores stale conversation saves', async () => {
  const previous = globalThis.__chatSelection
  const state = { options: reactive([{ value: 'OpenAI', label: 'OpenAI', children: [{ value: 'old', label: 'Old' }] },
    { value: 'Other', label: 'Other', children: [{ value: 'new', label: 'New' }] }]), requests: [], successes: [] }
  globalThis.__chatSelection = state
  const server = await setupModules({
    '/chat-selector-test.js': (await componentSource('../src/components/workspace/chat/ModelSelectButton.vue', 'chat-selector-test')).replace("'ant-design-vue'", "'virtual:selection-message'"),
    '@/components/ModelSelector.vue': await componentSource('../src/components/ModelSelector.vue', 'chat-model-selector'),
    '@/components/ModelCapabilities.vue': 'export default {render:()=>null}',
    '@/components/IconButton.vue': 'import {h} from "vue"; export default {inheritAttrs:false, setup:(_, {attrs})=>()=>h("open-model",attrs)}',
    '@/icons': 'export const RobotOne = {render:()=>null}, CheckOne=RobotOne, Down=RobotOne',
    '@/utils/common': 'export const getChatModelOptions = () => globalThis.__chatSelection.options',
    '@/api/chat': 'export const conversationAPI = (...args) => globalThis.__chatSelection.request(...args)',
    'virtual:selection-message': 'export const message = {success: value => globalThis.__chatSelection.successes.push(value)}',
  })
  let mounted
  try {
    state.request = (...args) => { const request = { ...deferred(), args }; state.requests.push(request); return request.promise }
    const updates = []
    const props = reactive({ cid: 'first', model: 'old', modelProvider: 'OpenAI',
      'onUpdate:model': value => updates.push(['model', value]), 'onUpdate:modelProvider': value => updates.push(['provider', value]) })
    mounted = await mount((await server.ssrLoadModule('/chat-selector-test.js')).default, props)
    const modal = () => findAll(mounted.root, 'AModal')[0]
    const menus = () => findAll(mounted.root, 'AMenu').filter(node => node.props.items)
    const open = async () => { findAll(mounted.root, 'AMenu')[0].props.onClick({key:'custom'}); await flush() }
    const choose = async () => { menus()[0].props.onClick({ key: 'Other' }); await flush(); assert.deepEqual(menus()[1].props.selectedKeys, []); menus()[1].props.onClick({ key: 'new' }); await flush() }
    await open()
    state.options[0].children = []; await flush()
    assert.equal(modal().props.okButtonProps.disabled, true)
    await modal().props.onOk()
    assert.equal(state.requests.length, 0, 'invalid provider/model pairs cannot be submitted')
    modal().props.onCancel(); state.options[0].children = [{ value: 'old', label: 'Old' }]; await flush()
    await open(); await choose()
    assert.equal(modal().props.okButtonProps.disabled, false)
    modal().props.onCancel(); await flush()
    assert.deepEqual(updates, [])
    await open()
    assert.deepEqual(menus()[0].props.selectedKeys, ['OpenAI'])
    assert.deepEqual(menus()[1].props.selectedKeys, ['old'])
    await choose()
    const failed = modal().props.onOk(); await flush()
    assert.deepEqual(state.requests[0].args, ['update', { cid: 'first', model: 'new', model_provider: 'Other', settings: {model_preference:'custom',reasoning_effort:'default'} }])
    assert.deepEqual(updates, [], 'pending save must not update the conversation')
    state.requests[0].reject(new Error('offline')); await failed; await flush()
    assert.equal(modal().props.open, true)
    assert.deepEqual(menus()[1].props.selectedKeys, ['new'])
    assert.equal(findAll(mounted.root, 'ATypographyText').some(node => node.props.role === 'alert'), true)
    assert.deepEqual(updates, [])
    const saved = modal().props.onOk(); state.requests[1].resolve({ status: 200 }); await saved; await flush()
    assert.deepEqual(updates, [['provider', 'Other'], ['model', 'new']])
    assert.equal(modal().props.open, false)
    updates.length = 0
    await open(); await choose()
    const stale = modal().props.onOk(); props.cid = 'second'; props.model = 'old'; props.modelProvider = 'OpenAI'; await flush()
    state.requests[2].resolve({ status: 200 }); await stale; await flush()
    assert.deepEqual(updates, [])
    assert.equal(modal().props.open, false)
    assert.equal(state.successes.length, 1)
    props.cid = 'tmp'; await flush(); await open(); await choose(); await modal().props.onOk(); await flush()
    assert.equal(state.requests.length, 3)
    assert.deepEqual(updates, [['provider', 'Other'], ['model', 'new']])
    updates.length = 0
    props.cid = 'last'; await flush(); await open(); await choose()
    const unmounted = modal().props.onOk(); mounted.app.unmount(); mounted = null
    state.requests[3].resolve({ status: 200 }); await unmounted; await flush()
    assert.deepEqual(updates, [])
    assert.equal(state.successes.length, 1)
  } finally { mounted?.app.unmount(); globalThis.__chatSelection = previous; await server.close() }
})

test('model catalog hydration preserves saved models and reacts to catalog refreshes', async () => {
  const modules = {
    '/model-hydration-test.js': await readFile(new URL('../src/utils/modelCatalog.js', import.meta.url), 'utf8'),
    '@/stores/modelCatalog': 'export const useModelCatalogStore = () => globalThis.__selectionCatalog',
  }
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'model-hydration-test', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }],
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  const previous = globalThis.__selectionCatalog
  try {
    const loading = deferred()
    const catalog = reactive({ generalModelOptions: [], visionModelOptions: [], ensureLoaded: () => loading.promise })
    globalThis.__selectionCatalog = catalog
    const { hydrateTemplateModelField, hydrateFlattenedModelField } = await server.ssrLoadModule('/model-hydration-test.js')
    const fields = { value: reactive({ llm_model: { value: 'retired-model', options: [] } }) }
    const flat = { value: reactive({ llm_model: { value: 'Removed/old', options: [] } }) }
    const hydration = Promise.all([hydrateTemplateModelField(fields, 'OpenAI'), hydrateFlattenedModelField(flat)])
    catalog.generalModelOptions = [{ value: 'OpenAI', children: [{ value: 'current', label: 'Current' }] }]
    loading.resolve(); await hydration
    assert.equal(fields.value.llm_model.value, 'retired-model')
    assert.equal(flat.value.llm_model.value, 'Removed/old')
    assert.deepEqual(fields.value.llm_model.options, [{ value: 'current', label: 'Current' }])
    assert.deepEqual(flat.value.llm_model.options, [{ value: 'OpenAI/current', label: 'OpenAI/Current' }])
    catalog.generalModelOptions = []
    assert.deepEqual(fields.value.llm_model.options, [])
    assert.deepEqual(flat.value.llm_model.options, [])
    assert.equal(fields.value.llm_model.value, 'retired-model')
    assert.equal(flat.value.llm_model.value, 'Removed/old')
  } finally { globalThis.__selectionCatalog = previous; await server.close() }
})

test('real chat options and catalog families filter only explicitly disabled local models and refresh reactively', async () => {
  const previousStorage = globalThis.localStorage
  globalThis.localStorage = { getItem: () => null, setItem() {} }
  const modules = {
    '/real-chat-options.js': (await readFile(new URL('../src/utils/common.js', import.meta.url), 'utf8'))
      .replace("'ant-design-vue'", "'virtual:catalog-ui'").replace("'./modelProviders'", "'virtual:model-providers'"),
    '/real-model-catalog.js': await readFile(new URL('../src/stores/modelCatalog.js', import.meta.url), 'utf8'),
    '/catalog-fixture.js': 'export {createPinia, setActivePinia} from "pinia"; export {useUserSettingsStore} from "@/stores/userSettings"',
    '@/stores/userSettings': 'import {defineStore} from "pinia"; export const useUserSettingsStore = defineStore("selection-test-settings",{state:()=>({setting:{data:{}}})})',
    '@/api/user': 'export const settingAPI = () => {throw new Error("Unexpected settings request")}',
    'virtual:catalog-ui': 'export const TypographyText = {}; export const Tag = {}; export const Flex = {}',
    'virtual:model-providers': await readFile(new URL('../src/utils/modelProviders.js', import.meta.url), 'utf8'),
  }
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'real-selection-catalog', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }],
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  try {
    const { createPinia, setActivePinia, useUserSettingsStore } = await server.ssrLoadModule('/catalog-fixture.js')
    setActivePinia(createPinia())
    const settings = useUserSettingsStore()
    const { useModelCatalogStore } = await server.ssrLoadModule('/real-model-catalog.js')
    const catalog = useModelCatalogStore()
    const { getChatModelOptions } = await server.ssrLoadModule('/real-chat-options.js')
    const options = computed(() => getChatModelOptions())
    const data = { custom_llms: { Family: ['disabled', 'enabled', 'legacy', 'shared'], Empty: ['disabled'] },
      llm_settings: { backends: {
        local: { models: { disabled: { enabled: false }, enabled: { enabled: true }, shared: { enabled: false } } },
        openai: { models: { shared: { id: 'Remote Shared', enabled: true }, remoteDisabled: { enabled: false } } },
      } } }
    settings.setting = { data }
    catalog.setPayloadFromSettings(settings.setting)
    const children = provider => options.value.find(option => option.value === provider)?.children.map(option => option.value)
    assert.deepEqual(children('_local__Family'), ['enabled', 'legacy'])
    assert.equal(children('_local__Empty'), undefined)
    assert.deepEqual(children('OpenAI'), ['shared'], 'disabled local metadata does not hide the same remote model ID')
    assert.deepEqual(catalog.familyMap.Family.map(model => model.key), ['enabled', 'legacy'])
    assert.deepEqual(catalog.familyMap.Empty, [])
    assert.deepEqual(catalog.generalModelOptions.find(provider => provider.value === 'OpenAI').children.map(model => model.value), ['shared'])
    assert.ok(getChatModelOptions(true).some(option => option.value === 'OpenAI⋄shared'))
    assert.ok(!getChatModelOptions(true).some(option => option.value === '_local__Family⋄shared'))
    settings.setting.data.llm_settings.backends.local.models.shared.enabled = true
    settings.setting.data.llm_settings.backends.local.models.enabled.enabled = false
    catalog.setPayloadFromSettings(settings.setting)
    assert.deepEqual(children('_local__Family'), ['legacy', 'shared'])
    assert.deepEqual(catalog.familyMap.Family.map(model => model.key), ['legacy', 'shared'])
    assert.deepEqual(children('OpenAI'), ['shared'])
    settings.setting = { data: { ...data, custom_llms: { Refreshed: ['new-legacy'] } } }
    catalog.setPayloadFromSettings(settings.setting)
    assert.equal(children('_local__Family'), undefined)
    assert.deepEqual(children('_local__Refreshed'), ['new-legacy'])
    assert.equal(catalog.familyMap.Family, undefined)
    assert.deepEqual(catalog.familyMap.Refreshed.map(model => model.key), ['new-legacy'])
  } finally { globalThis.localStorage = previousStorage; await server.close() }
})

for (const name of ['Moonshot', 'Gemini']) {
  test(`real ${name} and BaseLLM hydrate enabled options asynchronously and after saved JSON restoration`, async () => {
    const previousStorage = globalThis.localStorage
    const previousRequest = globalThis.__baseLLMSettingsRequest
    globalThis.localStorage = { getItem: () => null, setItem() {} }
    const request = deferred()
    globalThis.__baseLLMSettingsRequest = () => request.promise
    const templateSource = await readFile(new URL(`../src/components/nodes/llms/${name}.js`, import.meta.url), 'utf8')
    const server = await setupModules({
      '/real-provider-node.js': (await componentSource(`../src/components/nodes/llms/${name}.vue`, `real-${name}`))
        .replace("'./_BaseLLM.vue'", "'virtual:real-base-llm'").replace(`'./${name}.js'`, "'virtual:real-provider-template'"),
      'virtual:real-provider-template': templateSource,
      'virtual:real-base-llm': (await componentSource('../src/components/nodes/llms/_BaseLLM.vue', `real-base-${name}`))
        .replace("'ant-design-vue'", "'virtual:base-llm-message'"),
      '@/components/ModelSelector.vue': await componentSource('../src/components/ModelSelector.vue', `base-selector-${name}`),
      '@/utils/modelCatalog': await readFile(new URL('../src/utils/modelCatalog.js', import.meta.url), 'utf8'),
      '@/stores/modelCatalog': await readFile(new URL('../src/stores/modelCatalog.js', import.meta.url), 'utf8'),
      '/base-catalog-fixture.js': 'export {createPinia, setActivePinia} from "pinia"; export {useModelCatalogStore} from "@/stores/modelCatalog"',
      '@/api/user': 'export const settingAPI = () => globalThis.__baseLLMSettingsRequest()',
      '@/icons': 'export const AddOne = {}; export const ReduceOne = {}; export const Edit = {}',
      'virtual:base-llm-message': 'export const message = {error:()=>{}}',
      '@/components/nodes/BaseNode.vue': 'import {h} from "vue"; export default {setup:(_, {slots})=>()=>h("real-base-node",slots.main?.())}',
      '@/components/nodes/BaseField.vue': 'import {h} from "vue"; export default {setup:(_, {slots})=>()=>h("real-base-field",[slots.default?.(),slots.inline?.()])}',
      '@/components/nodes/BaseFieldsCollapse.vue': 'export default {render:()=>null}',
      '@/components/nodes/TemperatureInput.vue': 'export default {render:()=>null}',
      '@/components/ModelCapabilities.vue': 'export default {render:()=>null}',
    })
    let mounted
    try {
      const { createPinia, setActivePinia, useModelCatalogStore } = await server.ssrLoadModule('/base-catalog-fixture.js')
      setActivePinia(createPinia())
      const catalog = useModelCatalogStore()
      const component = (await server.ssrLoadModule('/real-provider-node.js')).default
      const { createTemplateData } = await server.ssrLoadModule('virtual:real-provider-template')
      const node = reactive({ id: 'vue-flow-node', data: createTemplateData() })
      node.data.template.llm_model.value = 'saved-retired'
      mounted = await mount(component, { id: node.id, data: node.data })
      await flush()
      assert.equal(catalog.loading, true)
      assert.equal(findAll(mounted.root, 'ASelect').length, 0, 'BaseLLM waits for initial async catalog hydration')
      const backend = name.toLowerCase()
      const payload = { data: { llm_settings: { backends: {
        [backend]: { models: { enabled: { id: `${name} Enabled`, enabled: true }, disabled: { enabled: false } } },
        openai: { models: { unrelated: { id: 'Unrelated' } } },
      } } } }
      request.resolve({ data: payload })
      await catalog.ensureLoaded(); await flush()
      const select = () => findAll(mounted.root, 'ASelect')[0]
      assert.deepEqual(select().props.options, [{ value: 'enabled', label: `${name} Enabled` }])
      assert.equal(select().props.value, 'saved-retired')
      assert.equal(select().props['aria-invalid'], true)
      const serialized = JSON.stringify(node)
      const restored = reactive(JSON.parse(serialized))
      assert.deepEqual(restored.data.template.llm_model.options, [{ value: 'enabled', label: `${name} Enabled` }], 'serialized reactive fields contain plain options, not computed internals')
      mounted.app.unmount()
      mounted = await mount(component, { id: restored.id, data: restored.data })
      await flush()
      assert.deepEqual(select().props.options, [{ value: 'enabled', label: `${name} Enabled` }])
      payload.data.llm_settings.backends[backend].models = { fresh: { id: `${name} Refreshed`, enabled: true } }
      catalog.setPayloadFromSettings(structuredClone(payload)); await flush()
      assert.deepEqual(select().props.options, [{ value: 'fresh', label: `${name} Refreshed` }], 'remount rehydrates serialized options and keeps them reactive')
      assert.equal(restored.data.template.llm_model.value, 'saved-retired')
      payload.data.llm_settings.backends[backend].models.fresh.enabled = false
      catalog.setPayloadFromSettings(structuredClone(payload)); await flush()
      assert.deepEqual(select().props.options, [], 'disabled backend models alone produce the empty dropdown')
      assert.equal(restored.data.template.llm_model.value, 'saved-retired')
      const savedWithEmptyOptions = reactive(JSON.parse(JSON.stringify(restored)))
      mounted.app.unmount()
      mounted = await mount(component, { id: savedWithEmptyOptions.id, data: savedWithEmptyOptions.data })
      await flush()
      assert.deepEqual(select().props.options, [])
      payload.data.llm_settings.backends[backend].models.fresh.enabled = true
      catalog.setPayloadFromSettings(structuredClone(payload)); await flush()
      assert.deepEqual(select().props.options, [{ value: 'fresh', label: `${name} Refreshed` }], 'saved empty option arrays do not freeze future catalog updates')
      assert.equal(savedWithEmptyOptions.data.template.llm_model.value, 'saved-retired')
      assert.doesNotThrow(() => JSON.stringify(savedWithEmptyOptions))
    } finally { mounted?.app.unmount(); globalThis.localStorage = previousStorage; globalThis.__baseLLMSettingsRequest = previousRequest; await server.close() }
  })
}
