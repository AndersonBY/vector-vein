import { iconButtonFixture } from './taskAgentButtonFixture.js'
import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick, reactive } from 'vue'
import { createI18n } from 'vue-i18n'
import { parse, compileScript } from 'vue/compiler-sfc'
import { createServer } from 'vite'

const flush = async () => { for (let n = 0; n < 5; n++) await new Promise(resolve => setImmediate(resolve)); await nextTick() }
const deferred = () => { let resolve; const promise = new Promise(done => { resolve = done }); return { promise, resolve } }
const row = (name, source = '.agents') => ({ path: `C:/fixtures/${name}`, name, description: `${name} skill`, sources: [source], error_code: '' })
const scan = (items = [row('one'), row('two', '.codex')]) => ({ status: 200, data: {
  roots: ['.agents', '.codex', '.claude'].map(id => ({ id, label: `~/${id}/skills`, path: `C:/fixtures/${id}/skills`, status: 'ready', count: items.filter(item => item.sources?.includes(id)).length })),
  skills: items, truncated: false,
} })

async function catalog(run) {
  const previous = globalThis.__localSkillsTest, previousWindow = globalThis.window
  const state = { route: reactive({ name: 'taskAgentSkills', params: {}, query: {} }), calls: [], successes: [], navigations: [],
    request: async action => action === 'skills' ? { status: 200, data: { skills: [] } } : scan() }
  globalThis.__localSkillsTest = state; globalThis.window = {}
  const filename = fileURLToPath(new URL('../src/views/Workspace/TaskAgent/TaskAgentSkills.vue', import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const source = compileScript(descriptor, { id: 'local-skills' }).content.replaceAll("'vue-router'", "'virtual:router'").replaceAll("'ant-design-vue'", "'virtual:messages'")
  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    '/local-skills.js': source,
    'virtual:router': 'export const useRoute=()=>globalThis.__localSkillsTest.route;export const useRouter=()=>({replace:()=>Promise.resolve(),push:target=>{globalThis.__localSkillsTest.navigations.push(target);return Promise.resolve()}})',
    'virtual:messages': 'export const Modal={confirm:()=>{}};export const message={success:text=>globalThis.__localSkillsTest.successes.push(text),warning:()=>{},error:()=>{}}',
    '@/api/taskAgent': 'export const taskAgentAPI=(action,payload={})=>{const state=globalThis.__localSkillsTest;state.calls.push({action,payload});return state.request(action,payload)}',
    '@/utils/taskAgentErrors': await readFile(new URL('../src/utils/taskAgentErrors.js', import.meta.url), 'utf8'),
    '@/utils/taskAgentTimeline': 'export const fileSize=bytes=>String(bytes)',
    '@/utils/taskAgentPresentation': 'export const formatTaskTime=()=>""',
    '@/icons': 'export const Add={render:()=>null},BookOpen=Add,Search=Add,Control=Add,ToTop=Add,ToBottom=Add,Edit=Add,Delete=Add,Upload=Add,FolderOpen=Add,DocDetail=Add,ViewGridCard=Add,ListOne=Add,Refresh=Add; export const Close=Add,Undo=Add,Star=Add,OffScreenOne=Add,Down=Add,OpenExternal=Add;',
  }
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'local-skills-fixture', resolveId: id => Object.hasOwn(modules, id) ? id : undefined, load: id => modules[id] }],
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  let app, vm
  try {
    const component = (await server.ssrLoadModule('/local-skills.js')).default
    const renderer = createRenderer({ createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {}, parentNode: () => null, nextSibling: () => null })
    app = renderer.createApp({ setup(props, context) { vm = component.setup(props, context); return () => h('div') } })
    const messages = JSON.parse(await readFile(new URL('../src/locales/zh-CN.json', import.meta.url), 'utf8'))
    app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': messages } })); app.mount({}); await flush()
    await run(vm, state)
  } finally { app?.unmount(); await server.close(); globalThis.__localSkillsTest = previous; globalThis.window = previousWindow }
}

test('local Agent scan is explicit, supports source/search selection and excludes invalid rows', async () => {
  await catalog(async (vm, state) => {
    assert.equal(state.calls.some(call => call.action === 'local_skills'), false)
    state.request = async action => action === 'local_skills' ? scan([row('one'), row('two', '.codex'), { ...row('invalid'), error_code: 'invalid_frontmatter' }]) : { status: 200, data: { skills: [] } }
    vm.openImportModal(); assert.equal(vm.importMode.value, 'manual')
    vm.importMode.value = 'local'; await flush()
    assert.equal(vm.localLoaded.value, true); assert.equal(vm.localSkills.value.length, 3)
    assert.equal(vm.localSelectable.value.length, 2)
    vm.localSource.value = '.codex'; vm.selectVisibleLocalSkills()
    assert.deepEqual(vm.localSelected.value, [row('two').path])
    vm.localSource.value = 'all'; vm.localSearch.value = 'one'; vm.selectVisibleLocalSkills()
    assert.deepEqual(vm.localSelected.value, [row('two').path, row('one').path])
    assert.match(vm.localError(vm.localSkills.value[2]), /SKILL|技能|格式/)
    assert.equal(state.calls.some(call => call.action === 'import_skill'), false)
  })
})

test('batch import preserves partial successes, retry identity and modal ownership during submission', async () => {
  await catalog(async (vm, state) => {
    vm.openImportModal(); vm.importMode.value = 'local'; await flush(); vm.selectVisibleLocalSkills()
    const wait = deferred()
    state.request = async (action, payload) => {
      if (action === 'skills') return { status: 200, data: { skills: [] } }
      if (payload.path.endsWith('one')) return { status: 200, data: { skill_id: payload.skill_id } }
      return wait.promise
    }
    const pending = vm.submitImport(); await flush()
    assert.equal(vm.importSaving.value, true)
    const draftId = vm.importDraft.skill_id
    vm.closeImportModal(); vm.openImportModal()
    assert.equal(vm.importOpen.value, true); assert.equal(vm.importDraft.skill_id, draftId)
    wait.resolve({ status: 400, data: { integration_error: { kind: 'skills', code: 'invalid_skill' } } }); await pending
    assert.equal(vm.importSaving.value, false); assert.equal(vm.importOpen.value, true)
    assert.ok(vm.localSkills.value[0].imported_id); assert.ok(vm.localSkills.value[1].import_error)
    assert.deepEqual(vm.localSelected.value, [row('two').path])
    const failedId = state.calls.filter(call => call.action === 'import_skill').at(-1).payload.skill_id
    state.request = async (action, payload) => action === 'skills' ? { status: 200, data: { skills: [] } } : { status: 200, data: { skill_id: payload.skill_id } }
    await vm.submitImport()
    assert.equal(vm.importOpen.value, false)
    const imports = state.calls.filter(call => call.action === 'import_skill')
    assert.equal(imports.length, 3); assert.equal(imports.at(-1).payload.skill_id, failedId)
    assert.equal(state.navigations.length, 0)
  })
})

test('failed or malformed scan retains selections and retries without losing import identity', async () => {
  await catalog(async (vm, state) => {
    vm.openImportModal(); vm.importMode.value = 'local'; await flush(); vm.selectLocalSkill(row('one').path)
    const id = vm.localSkills.value[0].import_id
    state.request = async () => scan([{ path: 'malformed' }])
    await vm.scanLocalSkills(); assert.equal(vm.localFailed.value, true)
    assert.deepEqual(vm.localSelected.value, [row('one').path]); assert.equal(vm.localSkills.value[0].import_id, id)
    const callCount = state.calls.length; await vm.submitImport(); assert.equal(state.calls.length, callCount)
    state.request = async () => scan(); await vm.scanLocalSkills()
    assert.equal(vm.localFailed.value, false); assert.equal(vm.localSkills.value[0].import_id, id)
    assert.deepEqual(vm.localSelected.value, [row('one').path])
  })
})

test('late discovery after modal close cannot overwrite a new import draft', async () => {
  await catalog(async (vm, state) => {
    const old = deferred(); state.request = () => old.promise
    vm.openImportModal(); vm.importMode.value = 'local'; await flush()
    vm.closeImportModal(); vm.openImportModal()
    old.resolve(scan([row('obsolete')])); await flush()
    assert.equal(vm.importMode.value, 'manual'); assert.deepEqual(vm.localSkills.value, [])
    state.request = async () => scan([row('current')]); vm.importMode.value = 'local'; await flush()
    assert.equal(vm.localSkills.value[0].name, 'current')
  })
})
