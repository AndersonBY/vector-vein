import { iconButtonFixture } from './taskAgentButtonFixture.js'
import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick, ref } from 'vue'
import { createI18n } from 'vue-i18n'
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



test('permission selector renders three modes and changes the task value', async () => {
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    '/permission-test.js': await componentSource('../src/views/Workspace/TaskAgent/TaskAgentPermissions.vue', 'permissions'),
    '@/icons': 'export const Down={render:()=>null},CheckOne=Down; export const Refresh=Down,Close=Down,Delete=Down,Undo=Down,Star=Down,OffScreenOne=Down,OpenExternal=Down;',
  }
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)), plugins: [{ name: 'permissions-test', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }], server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  let app
  try {
    const component = (await server.ssrLoadModule('/permission-test.js')).default
    const mode = ref('auto')
    const disabled = ref(false)
    app = renderer().createApp({ render: () => h(component, { modelValue: mode.value, disabled: disabled.value, 'onUpdate:modelValue': value => { mode.value = value } }) })
    app.component('ADropdown', { inheritAttrs: false, setup: (_, { attrs, slots }) => () => h('Dropdown', attrs, [slots.default?.(), slots.overlay?.()]) })
    for (const name of ['AMenu', 'AMenuItem']) app.component(name, { inheritAttrs: false, setup: (_, { attrs, slots }) => () => h(name, attrs, slots.default?.()) })
    const messages = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
    app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } }))
    const root = { children: [] }; app.mount(root); await flush()
    assert.match(textOf(root), /请求批准.*帮我批准.*完全访问权限/)
    const button = () => findAll(root, node => node.type === 'button')[0]
    const menu = () => findAll(root, node => node.type === 'AMenu')[0]
    assert.match(textOf(button()), /帮我批准/)
    assert.equal(button().props['aria-haspopup'], 'menu')
    assert.equal(findAll(root, node => node.type === 'AMenuItem').length, 3)
    findAll(root, node => node.type === 'Dropdown')[0].props['onUpdate:open'](true); await nextTick()
    assert.equal(button().props['aria-expanded'], true)
    menu().props.onClick({ key: 'full' }); await nextTick()
    assert.equal(mode.value, 'full')
    assert.equal(button().props['aria-expanded'], false)
    assert.match(findAll(root, node => node.type === 'div')[0].props.class, /full-access/)
    menu().props.onClick({ key: 'ask' }); await nextTick()
    assert.equal(mode.value, 'ask')
    disabled.value = true; await nextTick()
    assert.equal(button().props.disabled, true)
    menu().props.onClick({ key: 'full' }); await nextTick()
    assert.equal(mode.value, 'ask')
  } finally { app?.unmount(); await server.close() }
})


test('settings exposes an independent review model and can clear its selection', async () => {
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    '/reviewer-settings-test.js': await componentSource('../src/components/settings/TaskAgentApprovalSettings.vue', 'reviewer-settings'),
    '@/utils/modelPreferences': 'export const validModelPair=(options,provider,model)=>options.some(p=>p.value===provider&&p.children.some(m=>m.value===model))',
  }
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)), plugins: [{ name: 'reviewer-settings-test', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }], server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  let app
  try {
    const component = (await server.ssrLoadModule('/reviewer-settings-test.js')).default
    const selection = ref({ model_provider: '', model: '' })
    const options = [{ value: 'local', children: [{ value: 'reviewer' }] }]
    app = renderer().createApp({ render: () => h(component, { modelValue: selection.value, options, 'onUpdate:modelValue': value => { selection.value = value } }) })
    for (const name of ['AForm', 'AFormItem', 'ACascader', 'ATypographyText']) app.component(name, { inheritAttrs: false, setup: (_, { attrs, slots }) => () => h(name, attrs, slots.default?.()) })
    const messages = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
    app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } }))
    const root = { children: [] }; app.mount(root); await flush()
    assert.match(textOf(root), /独立 LLM/)
    assert.match(textOf(root), /调用费用/)
    const picker = findAll(root, node => node.type === 'ACascader')[0]
    picker.props.onChange(['local', 'reviewer']); await nextTick()
    assert.deepEqual(selection.value, { model_provider: 'local', model: 'reviewer' })
    picker.props.onChange([]); await nextTick()
    assert.deepEqual(selection.value, { model_provider: '', model: '' })
  } finally { app?.unmount(); await server.close() }
})


test('risk review progress cannot be manually approved and fallback links to reviewer settings', async () => {
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    '@/icons': 'export const Down={render:()=>null}',
    '/review-interaction-test.js': await componentSource('../src/views/Workspace/TaskAgent/TaskAgentInteraction.vue', 'review-interaction'),
    '@/utils/taskAgentTimeline': await readFile(new URL('../src/utils/taskAgentTimeline.js', import.meta.url), 'utf8'),
  }
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)), plugins: [{ name: 'review-interaction-test', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }], server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  let app
  try {
    const component = (await server.ssrLoadModule('/review-interaction-test.js')).default
    const question = ref({ kind: 'approval', permission_mode: 'auto', tool_name: 'bash', requestId: 'review-one', risk_review: { status: 'reviewing' } })
    const approvals = []
    app = renderer().createApp({ render: () => h(component, { question: question.value, onApprove: value => approvals.push(value) }) })
    for (const name of ['ASpace', 'AButton', 'RouterLink', 'ARadioGroup', 'ARadio', 'ACheckboxGroup', 'ATextarea']) app.component(name, { inheritAttrs: false, setup: (_, { attrs, slots }) => () => h(name, attrs, slots.default?.()) })
    const messages = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
    app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } }))
    const root = { children: [] }; app.mount(root); await flush()
    assert.match(textOf(root), /LLM 正在审核/)
    assert.equal(findAll(root, node => node.type === 'AButton' && /允许|拒/.test(textOf(node))).length, 0)
    question.value = { ...question.value, risk_review: { status: 'manual', reason: 'not_configured' } }; await nextTick()
    assert.match(textOf(root), /尚未配置风险审核模型/)
    const link = findAll(root, node => node.type === 'RouterLink')[0]
    assert.deepEqual(link.props.to, { name: 'settings', query: { section: 'model_preferences' } })
    const buttons = findAll(root, node => node.type === 'AButton' && /允许|拒/.test(textOf(node)))
    assert.equal(buttons.length, 2)
    buttons[1].props.onClick(); assert.deepEqual(approvals, ['allow'])
  } finally { app?.unmount(); await server.close() }
})
