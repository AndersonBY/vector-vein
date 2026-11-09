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
import { taskAgentSpaceRoute } from '../src/router/modules/taskAgent.js'

const flush = async () => {
  for (let i = 0; i < 6; i++) await new Promise(resolve => setImmediate(resolve))
  await nextTick()
}

const textOf = node => [node?.text || '', ...(node?.children || []).map(textOf)].join(' ')
const findAll = (node, predicate, results = []) => {
  if (predicate(node)) results.push(node)
  for (const child of node.children || []) findAll(child, predicate, results)
  return results
}

async function componentSource(path, id) {
  const filename = fileURLToPath(new URL(path, import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const script = compileScript(descriptor, { id })
  const source = script.content.replace('export default', 'const component =')
  const template = compileTemplate({
    source: descriptor.template.content,
    filename,
    id,
    compilerOptions: { bindingMetadata: script.bindings },
  }).code.replace('export function render', 'function render')
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

async function loadMergedMessages(locale = 'zh-CN') {
  return JSON.parse(await readFile(new URL(`../src/locales/${locale}.json`, import.meta.url), 'utf8'))
}

async function withSchedulesApp(run, {
  initialSchedules = [],
  agents = [
    { agent_id: 'general', name: '通用助手', permission_mode: 'auto' },
    { agent_id: 'researcher', name: '调研专家', permission_mode: 'ask', model_provider: 'OpenAI', model: 'gpt-4.1', reasoning_effort: 'high' },
  ],
  projects = [
    { project_id: 'proj_alpha', name: 'Alpha 项目', folders: [{ available: true }] },
    { project_id: 'proj_offline', name: 'Offline 项目', folders: [{ available: false }] },
  ],
  defaultModelPref = { model_provider: 'DeepSeek', model: 'deepseek-chat', reasoning_effort: 'medium' },
  modelOptions = [
    { value: 'DeepSeek', children: [{ value: 'deepseek-chat', label: 'DeepSeek Chat' }] },
    { value: 'OpenAI', children: [{ value: 'gpt-4.1', label: 'GPT-4.1' }, { value: 'o3-mini', label: 'o3-mini' }] },
  ],
} = {}) {
  const state = {
    calls: [],
    errors: [],
    successes: [],
    confirms: [],
    schedules: structuredClone(initialSchedules),
    agents: structuredClone(agents),
    projects: structuredClone(projects),
    modelOptions: structuredClone(modelOptions),
    defaultModelPref: structuredClone(defaultModelPref),
    handler: null,
  }

  state.handler = async (action, payload) => {
    if (action === 'schedules') return { status: 200, data: { schedules: structuredClone(state.schedules) } }
    if (action === 'profiles') return { status: 200, data: { agents: structuredClone(state.agents) } }
    if (action === 'projects') return { status: 200, data: { projects: structuredClone(state.projects) } }
    if (action === 'save_schedule') {
      const saved = {
        ...payload,
        name: payload.name || payload.goal.split('\n')[0].slice(0, 80),
        created_at: '2026-11-06T01:00:00Z',
        updated_at: '2026-11-06T02:00:00Z',
        next_run_at: payload.enabled ? '2026-11-07T01:00:00Z' : null,
        task_id: payload.run_mode === 'continue' ? 'task_cont_1' : null,
        last_run: null,
      }
      const idx = state.schedules.findIndex(s => s.schedule_id === saved.schedule_id)
      if (idx >= 0) state.schedules.splice(idx, 1, saved)
      else state.schedules.unshift(saved)
      return { status: 200, data: saved }
    }
    if (action === 'run_schedule') {
      return { status: 200, data: { run_id: 'run_123', task_id: 'task_run_123', status: 'ADMITTED' } }
    }
    if (action === 'delete_schedule') {
      state.schedules = state.schedules.filter(s => s.schedule_id !== payload.schedule_id)
      return { status: 200, data: { deleted: true } }
    }
    return { status: 200, data: {} }
  }

  globalThis.__schedulesTestState = state
  const rawScript = (await componentSource('../src/views/Workspace/TaskAgent/TaskAgentSchedules.vue', 'task-schedules'))
    .replaceAll("'ant-design-vue'", "'virtual:antd'")
    .replaceAll("'./TaskAgentPermissions.vue'", "'virtual:permissions'")
    .replaceAll("'./TaskAgentModelError.vue'", "'virtual:model-error'")

  const modules = {
    '@/components/IconButton.vue': iconButtonFixture,
    '/task-schedules-test.js': rawScript,
    'virtual:antd': `
      export const message = {
        error: v => globalThis.__schedulesTestState.errors.push(v),
        success: v => globalThis.__schedulesTestState.successes.push(v),
      };
      export const Modal = {
        confirm: opts => globalThis.__schedulesTestState.confirms.push(opts),
      };
    `,
    '@/api/taskAgent': 'export const taskAgentAPI = (action, payload) => { const s = globalThis.__schedulesTestState; s.calls.push({ action, payload: structuredClone(payload) }); return s.handler(action, payload); }',
    '@/utils/schedule': await readFile(new URL('../src/utils/schedule.js', import.meta.url), 'utf8'),
    '@/utils/taskAgentPresentation': await readFile(new URL('../src/utils/taskAgentPresentation.js', import.meta.url), 'utf8'),
    '@/utils/common': 'export const getChatModelOptions = () => globalThis.__schedulesTestState.modelOptions',
    '@/utils/modelPreferences': 'export const validModelPair = (options, provider, model) => options.some(p => p.value === provider && p.children?.some(m => m.value === model))',
    '@/stores/modelCatalog': 'export const useModelCatalogStore = () => ({ ensureLoaded: async () => {} })',
    '@/stores/userSettings': 'export const useUserSettingsStore = () => ({ setting: { data: { model_preferences: { default: globalThis.__schedulesTestState.defaultModelPref } } } })',
    '@/icons': 'export const Add = { render: () => null }, Calendar = Add, Search = Add, Control = Add, Edit = Add, Delete = Add, PlayOne = Add, Robot = Add, FolderOpen = Add, Time = Add, OpenExternal = Add, Setting = Add; export const Refresh=Add,Close=Add,Undo=Add,Star=Add,OffScreenOne=Add,Down=Add;',
    '@/components/scheduling/ScheduleEditor.vue': `
      import { h, onMounted } from 'vue';
      export default {
        props: ['modelValue', 'recurrence', 'timezone', 'disabled'],
        emits: ['update:modelValue', 'update:recurrence', 'update:timezone', 'validity-change'],
        setup(props, { emit }) {
          onMounted(() => emit('validity-change', true));
          return () => h('ScheduleEditorStub', {
            modelValue: props.modelValue,
            recurrence: props.recurrence,
            timezone: props.timezone,
            disabled: props.disabled,
            onSetCron: v => emit('update:modelValue', v),
            onSetRecurrence: v => emit('update:recurrence', v),
            onSetTimezone: v => emit('update:timezone', v),
            onSetValid: v => emit('validity-change', v),
          });
        },
      };
    `,
    '@/components/taskAgent/AgentPicker.vue': 'import {h} from "vue";export default{props:["modelValue","disabled"],setup:props=>()=>h("AgentPickerStub",{disabled:props.disabled})}',
    '@/components/taskAgent/TaskPicker.vue': 'export default { render: () => null }',
    '@/components/ModelPicker.vue': `
      import { h } from 'vue';
      export default {
        props: ['model', 'modelProvider', 'preference', 'reasoningEffort', 'options', 'disabled'],
        emits: ['update:model', 'update:modelProvider', 'update:preference', 'update:reasoningEffort'],
        setup(props, { emit }) {
          return () => h('ModelPickerStub', {
            model: props.model,
            modelProvider: props.modelProvider,
            reasoningEffort: props.reasoningEffort,
            disabled: props.disabled,
            onSelect: ({ provider, model, effort }) => {
              if (provider !== undefined) emit('update:modelProvider', provider);
              if (model !== undefined) emit('update:model', model);
              if (effort !== undefined) emit('update:reasoningEffort', effort);
            },
          });
        },
      };
    `,
    'virtual:permissions': `
      import { h } from 'vue';
      export default {
        props: ['modelValue', 'disabled'],
        emits: ['update:modelValue'],
        setup(props, { emit }) {
          return () => h('PermissionsStub', {
            value: props.modelValue,
            disabled: props.disabled,
            onChange: v => emit('update:modelValue', v),
          });
        },
      };
    `,
    'virtual:model-error': `
      import { h } from 'vue';
      export default {
        props: ['failure', 'modelConfig'],
        setup(props) {
          return () => h('ModelErrorStub', { category: props.failure?.category, model: props.modelConfig?.selected_model });
        },
      };
    `,
  }

  const server = await createServer({
    configFile: false,
    root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{
      name: 'task-schedules-fixture',
      resolveId: id => Object.hasOwn(modules, id) ? id : undefined,
      load: id => modules[id],
    }],
    server: { middlewareMode: true, hmr: false, ws: false },
    optimizeDeps: { noDiscovery: true },
    appType: 'custom',
  })

  let app, vm
  try {
    const component = (await server.ssrLoadModule('/task-schedules-test.js')).default
    const zhMessages = await loadMergedMessages('zh-CN')
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/task-agent/schedules', name: 'taskAgentSchedules', component: { render: () => null } },
        { path: '/task-agent/tasks/:taskId', name: 'taskAgentDetail', component: { render: () => null } },
        { path: '/settings', name: 'settings', component: { render: () => null } },
      ],
    })
    await router.push('/task-agent/schedules')
    await router.isReady()

    const compRef = { value: null }
    app = renderer().createApp({
      render: () => h(component, { ref: instance => { compRef.value = instance } }),
    })
    app.use(router)
    app.use(createI18n({ legacy: false, locale: 'zh-CN', messages: { 'zh-CN': zhMessages } }))
    for (const name of ['AButton', 'AInput', 'ATextarea', 'ASelect', 'ARadioGroup', 'ARadio', 'ASwitch', 'AModal', 'AForm', 'AFormItem', 'AAlert', 'ASpin', 'AEmpty', 'ATooltip', 'ADropdown', 'AMenu', 'ATypographyText']) {
      app.component(name, {
        inheritAttrs: false,
        setup: (_props, { attrs, slots }) => () => h(name, attrs, [slots.default?.(), slots.icon?.(), slots.action?.(), slots.overlay?.()]),
      })
    }
    const root = { children: [] }
    app.mount(root)
    await flush()
    vm = compRef.value
    await run({ vm, root, state, router })
  } finally {
    app?.unmount()
    await server.close()
    delete globalThis.__schedulesTestState
  }
}

test('taskAgentSpaceRoute registers schedules route with taskAgentSchedules name and schedules section meta', () => {
  const schedulesRoute = taskAgentSpaceRoute.children.find(child => child.path === 'schedules')
  assert.ok(schedulesRoute, 'schedules child route should exist')
  assert.equal(schedulesRoute.name, 'taskAgentSchedules')
  assert.equal(schedulesRoute.meta?.taskAgentSection, 'schedules')
})

test('retrying an unconfirmed schedule run preserves its original run ID', async () => {
  const item = { schedule_id: 'schedule_unknown', updated_at: 'v1', name: 'Unknown', enabled: true,
    last_run: { run_id: 'original_run', status: 'UNKNOWN', task_id: 'task' } }
  await withSchedulesApp(async ({ vm, state }) => {
    const handler = state.handler
    let unavailable = true
    state.handler = async (action, payload) => {
      if (action === 'retry_schedule_run') {
        if (unavailable) { unavailable = false; throw Error('Lost synthetic response') }
        return { status: 200, data: { run_id: 'original_run', status: 'ADMITTED' } }
      }
      return handler(action, payload)
    }
    await vm.retryRun(item)
    await vm.retryRun(item)
    assert.deepEqual(state.calls.filter(call => call.action === 'retry_schedule_run').map(call => call.payload), [
      { schedule_id: 'schedule_unknown', run_id: 'original_run' },
      { schedule_id: 'schedule_unknown', run_id: 'original_run' },
    ])
  }, { initialSchedules: [item] })
})

test('existing task selection includes hidden history and preserves the task workspace and Agent', async () => {
  await withSchedulesApp(async ({ vm, state }) => {
    const handler = state.handler
    const target = { tid: 'existing', title: '已有任务', goal: 'Existing context', hidden: 1, project_id: 'proj_alpha',
      model_provider: 'OpenAI', model: 'gpt-4.1', reasoning_effort: 'high',
      config_snapshot: { agent_profile: { agent_id: 'researcher', permission_mode: 'ask' }, project: { name: 'Alpha 项目' } } }
    state.handler = async (action, payload) => action === 'list' ? { status: 200, data: { tasks: [target], total: 1 } }
      : action === 'get' ? { status: 200, data: { task: target, runtime_settings: { model_provider: 'OpenAI', model: 'gpt-4.1', reasoning_effort: 'high', permission_mode: 'ask' } } }
      : handler(action, payload)
    vm.openCreateModal()
    vm.formState.run_mode = 'continue'
    vm.setContinuationSource('existing')
    await flush()
    assert.equal(vm.saveDisabled, true)
    await vm.loadExistingTask('existing')
    assert.equal(vm.formState.project_id, 'proj_alpha')
    assert.equal(vm.formState.agent_id, 'researcher')
    assert.equal(vm.formState.reasoning_effort, 'high')
    assert.equal(vm.continueThreadLocked, true)
    vm.formState.goal = '每次定时追加的消息'
    assert.equal(vm.saveDisabled, false)
    await vm.submitScheduleEditor()
    const saved = state.calls.find(call => call.action === 'save_schedule').payload
    assert.equal(saved.existing_task_id, 'existing')
    assert.equal(saved.project_id, 'proj_alpha')
    assert.equal(saved.agent_id, 'researcher')
    assert.equal(saved.goal, '每次定时追加的消息')
    assert.equal(vm.targetTask.hidden, 1)
  })
})

test('existing task selection ignores stale details and clears its selected task', async () => {
  await withSchedulesApp(async ({ vm, state }) => {
    const handler = state.handler
    let resolveOld
    const old = new Promise(resolve => { resolveOld = resolve })
    const target = id => ({ tid: id, title: id, goal: 'Goal', project_id: null, model_provider: 'DeepSeek', model: 'deepseek-chat', config_snapshot: { agent_profile: { agent_id: 'general' } } })
    state.handler = async (action, payload) => action === 'list' ? { status: 200, data: { tasks: [target('listed')], total: 2 } }
      : action === 'get' ? payload.task_id === 'old' ? old : { status: 200, data: { task: target(payload.task_id) } }
      : handler(action, payload)
    vm.openCreateModal(); vm.formState.run_mode = 'continue'; vm.setContinuationSource('existing'); await flush()
    const pending = vm.loadExistingTask('old')
    await vm.loadExistingTask('selected')
    resolveOld({ status: 200, data: { task: { ...target('old'), project_id: 'stale-project' } } }); await pending
    assert.equal(vm.formState.existing_task_id, 'selected')
    assert.equal(vm.formState.project_id, '')
    assert.equal(vm.targetTask.tid, 'selected')
    await vm.loadExistingTask('')
    assert.equal(vm.targetTask, null)
    assert.equal(vm.formState.existing_task_id, null)
  })
})

test('create schedule applies workbench defaults, supports project/run_mode/model reasoning and submits exact save_schedule payload', async () => {
  await withSchedulesApp(async ({ vm, root, state }) => {
    vm.openCreateModal()
    await flush()

    assert.equal(vm.editorOpen, true)
    assert.match(vm.formState.schedule_id, /^sched_[a-f0-9]{32}$/)
    assert.equal(vm.formState.expected_updated_at, '')
    assert.equal(vm.formState.name, '')
    assert.equal(vm.formState.goal, '')
    assert.equal(vm.formState.agent_id, 'general')
    assert.equal(vm.formState.project_id, '')
    assert.equal(vm.formState.run_mode, 'new')
    assert.equal(vm.formState.permission_mode, 'auto')
    assert.equal(vm.formState.model_provider, 'DeepSeek')
    assert.equal(vm.formState.model, 'deepseek-chat')
    assert.equal(vm.formState.reasoning_effort, 'medium')
    assert.equal(vm.formState.cron_expression, '0 9 * * *')
    assert.equal(vm.formState.recurrence, null)
    assert.ok(vm.formState.timezone)
    assert.equal(vm.formState.hide_after_run, false)
    assert.equal(vm.formState.notify_after_run, true)
    assert.equal(vm.formState.enabled, true)

    // Check Settings notifications link in modal
    const settingsLinks = findAll(root, node => String(node.props?.class || '').includes('settings-link'))
    assert.equal(settingsLinks.length, 1)

    // Goal missing -> saveDisabled is true
    assert.equal(vm.saveDisabled, true)

    // Fill goal, select Agent with custom model & reasoning, select Project, switch to continue mode and custom recurrence
    vm.formState.goal = '每日汇总项目进展\n并整理风险清单'
    vm.handleAgentSelect('researcher')
    assert.equal(vm.formState.permission_mode, 'ask')
    assert.equal(vm.formState.model_provider, 'OpenAI')
    assert.equal(vm.formState.model, 'gpt-4.1')
    assert.equal(vm.formState.reasoning_effort, 'high')

    vm.formState.project_id = 'proj_alpha'
    vm.formState.run_mode = 'continue'
    vm.formState.hide_after_run = true
    vm.formState.notify_after_run = false
    vm.formState.cron_expression = '30 14 * * 1,3,5'
    vm.formState.recurrence = { unit: 'week', interval: 2, anchor_date: '2026-11-02' }
    vm.formState.timezone = 'Asia/Shanghai'
    await flush()

    assert.equal(vm.saveDisabled, false)
    const ok = await vm.submitScheduleEditor()
    assert.equal(ok, true)
    assert.equal(vm.editorOpen, false)

    const saveCall = state.calls.find(c => c.action === 'save_schedule')
    assert.ok(saveCall)
    assert.deepEqual(saveCall.payload, {
      schedule_id: vm.formState.schedule_id,
      name: '',
      goal: '每日汇总项目进展\n并整理风险清单',
      agent_id: 'researcher',
      project_id: 'proj_alpha',
      run_mode: 'continue',
      existing_task_id: null,
      model_provider: 'OpenAI',
      model: 'gpt-4.1',
      reasoning_effort: 'high',
      permission_mode: 'ask',
      cron_expression: '30 14 * * 1,3,5',
      recurrence: { unit: 'week', interval: 2, anchor_date: '2026-11-02' },
      timezone: 'Asia/Shanghai',
      hide_after_run: true,
      notify_after_run: false,
      enabled: true,
    })
    assert.equal(Object.hasOwn(saveCall.payload, 'expected_updated_at'), false)
    assert.equal(vm.schedules.length, 1)
    assert.equal(vm.schedules[0].name, '每日汇总项目进展')
  })
})

test('schedule editor validity gate, missing goal/model gate, continue thread lock on agent/project, and failed draft preservation', async () => {
  const existingContinueSchedule = {
    schedule_id: 'sched_existing_1',
    name: '持续追踪周报',
    goal: '检查本周指标变化',
    agent_id: 'researcher',
    project_id: 'proj_alpha',
    run_mode: 'continue',
    model_provider: 'OpenAI',
    model: 'gpt-4.1',
    reasoning_effort: 'high',
    permission_mode: 'auto',
    cron_expression: '0 9 * * 1',
    recurrence: null,
    timezone: 'Asia/Shanghai',
    hide_after_run: false,
    notify_after_run: true,
    enabled: true,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-05T08:00:00Z',
    next_run_at: '2026-11-09T01:00:00Z',
    task_id: 'task_thread_99',
    last_run: {
      run_id: 'run_prev',
      task_id: 'task_thread_99',
      status: 'SKIPPED',
      error_code: 'busy',
      scheduled_at: '2026-11-05T01:00:00Z',
      finished_at: '2026-11-05T01:00:01Z',
    },
  }

  await withSchedulesApp(async ({ vm, root, state }) => {
    // Verify card renders natural language schedule and busy error status
    assert.match(textOf(root), /目标任务仍在运行/)

    vm.openEditModal(existingContinueSchedule)
    await flush()

    // Because task_id exists and run_mode === 'continue', continueThreadLocked is true
    assert.equal(vm.continueThreadLocked, true)
    const selects = findAll(root, node => ['ASelect', 'AgentPickerStub'].includes(node.type))
    assert.equal(selects.length, 2)
    assert.equal(selects[0].props.disabled, true)
    assert.equal(selects[1].props.disabled, true)

    // Switching run_mode to 'new' unlocks Agent and Project selects
    vm.formState.run_mode = 'new'
    await flush()
    assert.equal(vm.continueThreadLocked, false)
    assert.equal(selects[0].props.disabled, false)
    assert.equal(selects[1].props.disabled, false)

    // Switch back to 'continue'
    vm.formState.run_mode = 'continue'
    await flush()
    assert.equal(vm.continueThreadLocked, true)

    // Invalid schedule emitted by ScheduleEditor blocks save
    const schedStub = findAll(root, node => node.type === 'ScheduleEditorStub')[0]
    schedStub.props.onSetValid(false)
    await flush()
    assert.equal(vm.saveDisabled, true)
    assert.equal(await vm.submitScheduleEditor(), false)

    schedStub.props.onSetValid(true)
    await flush()
    assert.equal(vm.saveDisabled, false)

    // Invalid model pair blocks save
    vm.formState.model = 'non-existent-model'
    await flush()
    assert.equal(vm.saveDisabled, true)
    vm.formState.model = 'gpt-4.1'
    await flush()
    assert.equal(vm.saveDisabled, false)

    // Failed API save preserves user draft, shows error & ModelError, and 409 updates expected_updated_at
    vm.formState.goal = '修改后的提示词内容（保存失败需保留）'
    vm.formState.project_id = ''
    vm.formState.run_mode = 'new'
    state.schedules[0].updated_at = '2026-11-06T09:30:00Z'
    state.handler = async (action) => {
      if (action === 'save_schedule') {
        return {
          status: 409,
          data: {
            schedule_error: { code: 'changed' },
            model_failure: { category: 'credentials_missing' },
          },
        }
      }
      if (action === 'schedules') return { status: 200, data: { schedules: structuredClone(state.schedules) } }
      if (action === 'profiles') return { status: 200, data: { agents: structuredClone(state.agents) } }
      if (action === 'projects') return { status: 200, data: { projects: structuredClone(state.projects) } }
      return { status: 200, data: {} }
    }

    const saveResult = await vm.submitScheduleEditor()
    await flush()
    assert.equal(saveResult, false)
    assert.equal(vm.editorOpen, true)
    assert.equal(vm.formState.goal, '修改后的提示词内容（保存失败需保留）')
    assert.match(vm.editorError, /状态已更新/)
    assert.equal(vm.formState.expected_updated_at, '2026-11-06T09:30:00Z')
    assert.equal(findAll(root, node => node.type === 'ModelErrorStub')[0]?.props.category, 'credentials_missing')

    // Retry succeeds with refreshed expected_updated_at and project_id: null
    state.handler = async (action, payload) => {
      if (action === 'save_schedule') {
        return {
          status: 200,
          data: {
            ...payload,
            created_at: '2026-11-01T00:00:00Z',
            updated_at: '2026-11-06T10:00:00Z',
            next_run_at: '2026-11-07T01:00:00Z',
            task_id: null,
            last_run: null,
          },
        }
      }
      return { status: 200, data: {} }
    }
    const retryResult = await vm.submitScheduleEditor()
    assert.equal(retryResult, true)
    assert.equal(vm.editorOpen, false)
    const lastSave = state.calls.filter(c => c.action === 'save_schedule').at(-1).payload
    assert.equal(lastSave.expected_updated_at, '2026-11-06T09:30:00Z')
    assert.equal(lastSave.project_id, null)
    assert.equal(lastSave.goal, '修改后的提示词内容（保存失败需保留）')
  }, { initialSchedules: [existingContinueSchedule] })
})

test('runScheduleNow reuses idempotent input_id across uncertain failures and clears on success or 409 conflict', async () => {
  const savedSchedule = {
    schedule_id: 'sched_run_1',
    name: '立即运行测试',
    goal: '执行检查',
    agent_id: 'general',
    project_id: null,
    run_mode: 'new',
    model_provider: 'DeepSeek',
    model: 'deepseek-chat',
    reasoning_effort: 'default',
    permission_mode: 'auto',
    cron_expression: '0 9 * * *',
    recurrence: null,
    timezone: 'Asia/Shanghai',
    hide_after_run: false,
    notify_after_run: true,
    enabled: true,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-05T08:00:00Z',
    next_run_at: '2026-11-07T01:00:00Z',
    task_id: null,
    last_run: null,
  }

  await withSchedulesApp(async ({ vm, state }) => {
    // 1. Network / 503 uncertain failure retains pendingRuns[schedule_id]
    state.handler = async (action) => {
      if (action === 'run_schedule') return { status: 503, data: { schedule_error: { code: 'connection_unavailable' } } }
      return { status: 200, data: { schedules: [savedSchedule], agents: state.agents, projects: state.projects } }
    }

    await vm.runScheduleNow(savedSchedule)
    const firstRunCall = state.calls.filter(c => c.action === 'run_schedule')[0]
    assert.ok(firstRunCall)
    assert.match(firstRunCall.payload.input_id, /^run_[a-f0-9]{32}$/)
    assert.equal(vm.pendingRuns.sched_run_1, firstRunCall.payload.input_id)

    // 2. Retry after uncertain failure sends the EXACT same input_id
    state.handler = async (action) => {
      if (action === 'run_schedule') return { status: 200, data: { run_id: 'run_ok', task_id: 'task_ok', status: 'ADMITTED' } }
      return { status: 200, data: { schedules: [savedSchedule], agents: state.agents, projects: state.projects } }
    }

    await vm.runScheduleNow(savedSchedule)
    const secondRunCall = state.calls.filter(c => c.action === 'run_schedule')[1]
    assert.equal(secondRunCall.payload.input_id, firstRunCall.payload.input_id)
    assert.equal(vm.pendingRuns.sched_run_1, undefined)

    // 3. Subsequent manual run generates a fresh input_id, and a definitive 409 busy response clears pendingRuns
    state.handler = async (action) => {
      if (action === 'run_schedule') return { status: 409, data: { schedule_error: { code: 'busy' } } }
      return { status: 200, data: { schedules: [savedSchedule], agents: state.agents, projects: state.projects } }
    }

    await vm.runScheduleNow(savedSchedule)
    const thirdRunCall = state.calls.filter(c => c.action === 'run_schedule')[2]
    assert.notEqual(thirdRunCall.payload.input_id, firstRunCall.payload.input_id)
    assert.equal(vm.pendingRuns.sched_run_1, undefined)
    assert.ok(state.errors.some(msg => msg.includes('目标任务仍在运行')))
  }, { initialSchedules: [savedSchedule] })
})
test('delete_schedule sends expected_updated_at and removes item on 200, while stale load responses are ignored', async () => {
  const item = {
    schedule_id: 'sched_del_1',
    name: '清理过期文件',
    goal: '清理缓存',
    agent_id: 'general',
    project_id: null,
    run_mode: 'new',
    model_provider: 'DeepSeek',
    model: 'deepseek-chat',
    reasoning_effort: 'default',
    permission_mode: 'auto',
    cron_expression: '0 9 * * *',
    recurrence: null,
    timezone: 'Asia/Shanghai',
    hide_after_run: false,
    notify_after_run: true,
    enabled: true,
    created_at: '2026-11-01T00:00:00Z',
    updated_at: '2026-11-05T08:00:00Z',
    next_run_at: '2026-11-07T01:00:00Z',
    task_id: null,
    last_run: null,
  }

  await withSchedulesApp(async ({ vm, state }) => {
    vm.confirmDeleteSchedule(item)
    assert.equal(state.confirms.length, 1)
    await state.confirms[0].onOk()
    const delCall = state.calls.find(c => c.action === 'delete_schedule')
    assert.deepEqual(delCall.payload, {
      schedule_id: 'sched_del_1',
      expected_updated_at: '2026-11-05T08:00:00Z',
    })
    assert.equal(vm.schedules.length, 0)
  }, { initialSchedules: [item] })
})
