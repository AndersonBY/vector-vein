import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick, reactive } from 'vue'
import { createI18n } from 'vue-i18n'
import { createServer } from 'vite'
import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'

const flush = async () => {
  for (let i = 0; i < 6; i++) await new Promise(resolve => setImmediate(resolve))
  await nextTick()
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

const createTreeRenderer = () =>
  createRenderer({
    patchProp: (node, key, _old, value) => {
      node.props[key] = value
    },
    insert: (node, parent, anchor) => {
      if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
      node.parent = parent
      const index = anchor ? parent.children.indexOf(anchor) : -1
      if (index < 0) parent.children.push(node)
      else parent.children.splice(index, 0, node)
    },
    remove: node => {
      if (node?.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
    },
    createElement: type => ({ type, props: {}, children: [], parent: null }),
    createText: text => ({ text }),
    createComment: text => ({ text }),
    setText: (node, text) => {
      node.text = text
    },
    setElementText: (node, text) => {
      node.text = text
    },
    parentNode: node => node.parent,
    nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
  })

const textOf = node => [node?.text || '', ...(node?.children || []).map(textOf)].join(' ')
const findAll = (node, predicate, results = []) => {
  if (predicate(node)) results.push(node)
  for (const child of node.children || []) findAll(child, predicate, results)
  return results
}

async function withScheduleEditor(run, initialProps = {}) {
  const state = {
    props: reactive({
      modelValue: '0 9 * * *',
      recurrence: null,
      timezone: 'Asia/Shanghai',
      disabled: false,
      autoSyncProps: true,
      ...initialProps,
    }),
    emittedModel: [],
    emittedRecurrence: [],
    emittedTimezone: [],
    emittedValidity: [],
  }

  const modules = {
    '/schedule-editor-test.js': await componentSource('../src/components/scheduling/ScheduleEditor.vue', 'schedule-editor'),
    '@/utils/schedule': await readFile(new URL('../src/utils/schedule.js', import.meta.url), 'utf8'),
    '@/icons': 'export const Down = { render: () => null }',
  }

  const server = await createServer({
    configFile: false,
    root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [
      {
        name: 'schedule-editor-fixture',
        resolveId: id => (Object.hasOwn(modules, id) ? id : undefined),
        load: id => modules[id],
      },
    ],
    server: { middlewareMode: true, hmr: false, ws: false },
    optimizeDeps: { noDiscovery: true },
    appType: 'custom',
  })

  let app
  let vm
  const root = { type: 'root', props: {}, children: [], parent: null }
  try {
    const Component = (await server.ssrLoadModule('/schedule-editor-test.js')).default
    const renderer = createTreeRenderer()
    const Host = {
      setup() {
        return () =>
          h(Component, {
            ref: instance => {
              if (instance) vm = instance
            },
            modelValue: state.props.modelValue,
            recurrence: state.props.recurrence,
            timezone: state.props.timezone,
            disabled: state.props.disabled,
            'onUpdate:modelValue': val => {
              state.emittedModel.push(val)
              if (state.props.autoSyncProps) state.props.modelValue = val
            },
            'onUpdate:recurrence': val => {
              state.emittedRecurrence.push(val)
              if (state.props.autoSyncProps) state.props.recurrence = val
            },
            'onUpdate:timezone': val => {
              state.emittedTimezone.push(val)
              if (state.props.autoSyncProps) state.props.timezone = val
            },
            onValidityChange: val => {
              state.emittedValidity.push(val)
            },
          })
      },
    }
    app = renderer.createApp(Host)
    for (const name of ['ASelect', 'ASelectOptGroup', 'ASelectOption', 'ADropdown', 'ACheckboxGroup', 'ACheckbox', 'ATimePicker']) {
      app.component(name, {
        inheritAttrs: false,
        setup: (_, { attrs, slots }) => () => h(name, attrs, [slots.default?.(), slots.overlay?.()]),
      })
    }
    const locales = Object.fromEntries(await Promise.all(['zh-CN', 'en-US'].map(async locale => [locale, JSON.parse(await readFile(new URL(`../src/locales/${locale}.json`, import.meta.url), 'utf8')).components.schedule_editor])))
    app.use(
      createI18n({
        legacy: false,
        locale: 'zh-CN',
        messages: {
          'zh-CN': { components: { schedule_editor: locales['zh-CN'] } },
          'en-US': { components: { schedule_editor: locales['en-US'] } },
        },
      }),
    )
    app.mount(root)
    await flush()
    await run(vm, state, root)
  } finally {
    app?.unmount()
    await server.close()
  }
}

test('ScheduleEditor never mutates modelValue, recurrence, or timezone on mount or external prop refresh, and emits validity-change on mount', async () => {
  await withScheduleEditor(
    async (vm, state, root) => {
      assert.equal(state.emittedModel.length, 0, 'Must not emit update:modelValue on mount')
      assert.equal(state.emittedRecurrence.length, 0, 'Must not emit update:recurrence on mount')
      assert.equal(state.emittedTimezone.length, 0, 'Must not emit update:timezone on mount')
      assert.deepEqual(state.emittedValidity, [true])
      assert.equal(vm.draft.mode, 'weekly')
      assert.deepEqual(vm.draft.weekdays, [1, 3, 0])

      // External prop change to a legacy non-lossless cron preserves exact cron without emitting mutations
      state.props.modelValue = '0 9,18 * * 1-5'
      state.props.recurrence = null
      await flush()
      assert.equal(state.emittedModel.length, 0)
      assert.equal(state.emittedRecurrence.length, 0)
      assert.equal(vm.draft.mode, 'legacy')
      assert.equal(vm.draft.rawCron, '0 9,18 * * 1-5')
      assert.match(textOf(root), /已保留原有的自定义计划/)

      // Only after explicit user mode selection does it replace the legacy cron
      vm.handleModeChange('weekdays')
      await flush()
      assert.equal(state.props.modelValue, '0 9 * * 1-5')
      assert.equal(state.props.recurrence, null)
    },
    {
      modelValue: '0 9 * * MON,WED,7',
      recurrence: null,
      timezone: 'America/New_York',
    },
  )
})

test('ScheduleEditor supports user edits across daily, weekly, and custom 2-week/monthly intervals, and validates empty weekdays or out-of-range intervals', async () => {
  await withScheduleEditor(async (vm, state) => {
    // 1. Change time on daily
    vm.handleTimeChange('14:30')
    await flush()
    assert.equal(state.props.modelValue, '30 14 * * *')
    assert.equal(state.props.recurrence, null)

    // 2. Switch to weekly and select Tue + Thu
    vm.handleModeChange('weekly')
    vm.handleWeekdaysChange([2, 4])
    await flush()
    assert.equal(state.props.modelValue, '30 14 * * 2,4')
    assert.equal(state.props.recurrence, null)

    // 3. Clearing all weekdays emits validity-change=false and does not emit an invalid cron or restore old selection
    const prevCron = state.props.modelValue
    vm.handleWeekdaysChange([])
    await flush()
    assert.equal(state.emittedValidity.at(-1), false)
    assert.deepEqual(vm.draft.weekdays, [])
    assert.equal(state.props.modelValue, prevCron, 'Must not emit invalid cron when weekdays are empty')

    // Restore valid weekday selection -> validity-change=true
    vm.handleWeekdaysChange([1, 5])
    await flush()
    assert.equal(state.emittedValidity.at(-1), true)
    assert.equal(state.props.modelValue, '30 14 * * 1,5')

    // 4. Switch to custom -> every 2 weeks starting 2026-11-06 -> emits recurrence object
    vm.handleModeChange('custom')
    vm.handleCustomUnitChange('week')
    vm.handleAnchorDateInput('2026-11-06')
    vm.handleCalendarIntervalInput('2')
    await flush()
    assert.equal(state.emittedValidity.at(-1), true)
    assert.equal(state.props.modelValue, '30 14 * * 1,5')
    assert.deepEqual(state.props.recurrence, {
      unit: 'week',
      interval: 2,
      anchor_date: '2026-11-06',
    })

    // 5. Out-of-range week interval (e.g. 60 > 52) emits validity-change=false
    vm.handleCalendarIntervalInput('60')
    await flush()
    assert.equal(state.emittedValidity.at(-1), false)
    assert.match(vm.validationMessage, /1–52/)

    // 6. Custom monthly every 3 months on day 15
    vm.handleCustomUnitChange('month')
    vm.handleDayOfMonthChange(15)
    vm.handleAnchorDateInput('2026-11-15')
    vm.handleCalendarIntervalInput('3')
    await flush()
    assert.equal(state.emittedValidity.at(-1), true)
    assert.equal(state.props.modelValue, '30 14 15 * *')
    assert.deepEqual(state.props.recurrence, {
      unit: 'month',
      interval: 3,
      anchor_date: '2026-11-15',
    })

    // 7. Setting interval back to 1 clears recurrence to null
    vm.handleCalendarIntervalInput('1')
    await flush()
    assert.equal(state.props.modelValue, '30 14 15 * *')
    assert.equal(state.props.recurrence, null)

    // 8. Custom hourly uses minuteOfHour only
    vm.handleCustomUnitChange('hour')
    vm.handleIntervalSelect(4)
    vm.handleMinuteOfHourChange(20)
    await flush()
    assert.equal(state.props.modelValue, '20 */4 * * *')
    assert.equal(state.props.recurrence, null)
  })
})

test('ScheduleEditor respects disabled prop, updates timezone only on explicit selection, and avoids reset loops during multi-prop emissions', async () => {
  await withScheduleEditor(
    async (vm, state, root) => {
      // No raw Cron input anywhere in DOM
      const rawTextInputs = findAll(root, n => n.type === 'AInput' || (n.type === 'input' && (!n.props.type || n.props.type === 'text')))
      assert.equal(rawTextInputs.length, 0, 'ScheduleEditor must not render any raw editable Cron text input')

      // Advanced timezone change emits update:timezone only when explicitly changed
      vm.advancedOpen = true
      await flush()
      vm.handleTimezoneChange('UTC')
      await flush()
      assert.deepEqual(state.emittedTimezone, ['UTC'])

      // Disabled prop blocks all mutations
      state.props.disabled = true
      await flush()
      const countBefore = state.emittedModel.length
      vm.handleModeChange('weekdays')
      vm.handleTimeChange('18:00')
      vm.handleTimezoneChange('Asia/Tokyo')
      await flush()
      assert.equal(state.emittedModel.length, countBefore)
      assert.equal(state.emittedTimezone.length, 1)
    },
    {
      modelValue: '0 9 * * *',
      recurrence: null,
      timezone: 'Asia/Shanghai',
    },
  )
})

test('ScheduleEditor does not reset local draft when parent echoes modelValue before recurrence on multi-prop updates, and resets cleanly when switching external records', async () => {
  await withScheduleEditor(
    async (vm, state) => {
      // Simulate delayed parent sync: parent updates modelValue first, then recurrence on next tick
      state.props.autoSyncProps = false
      vm.handleModeChange('custom')
      vm.handleCustomUnitChange('week')
      vm.handleAnchorDateInput('2026-11-06')
      vm.handleCalendarIntervalInput('2')
      await flush()

      const emittedCron = state.emittedModel.at(-1)
      const emittedRec = state.emittedRecurrence.at(-1)
      assert.equal(emittedCron, '0 9 * * 1')
      assert.deepEqual(emittedRec, { unit: 'week', interval: 2, anchor_date: '2026-11-06' })

      // Parent echoes only modelValue first while recurrence is still null: must NOT reset draft to weekly (interval=1)
      state.props.modelValue = emittedCron
      await flush()
      assert.equal(vm.draft.mode, 'custom')
      assert.equal(vm.draft.customUnit, 'week')
      assert.equal(vm.draft.interval, 2)

      // Parent then echoes recurrence: draft stays intact
      state.props.recurrence = emittedRec
      await flush()
      assert.equal(vm.draft.mode, 'custom')
      assert.equal(vm.draft.interval, 2)

      // Now parent switches to a genuinely different external schedule record (e.g. every 15 minutes)
      state.props.modelValue = '*/15 * * * *'
      state.props.recurrence = null
      await flush()
      assert.equal(vm.draft.mode, 'custom')
      assert.equal(vm.draft.customUnit, 'minute')
      assert.equal(vm.draft.interval, 15)
    },
    {
      modelValue: '0 9 * * *',
      recurrence: null,
      timezone: 'Asia/Shanghai',
    },
  )
})

test('ScheduleEditor rejects invalid stored recurrence until explicitly replaced and validates timezone changes', async () => {
  await withScheduleEditor(async (vm, state) => {
    assert.deepEqual(state.emittedValidity, [false])
    assert.equal(vm.buildResult.valid, false)
    assert.equal(state.emittedModel.length, 0)
    assert.equal(state.emittedRecurrence.length, 0)
    vm.handleModeChange('daily')
    await flush()
    assert.equal(state.emittedValidity.at(-1), true)
    assert.equal(state.props.recurrence, null)
    state.props.timezone = 'Not/A_Timezone'
    await flush()
    assert.equal(state.emittedValidity.at(-1), false)
    assert.match(vm.validationMessage, /时区无效/)
    vm.handleTimezoneChange('UTC')
    await flush()
    assert.equal(state.emittedValidity.at(-1), true)
  }, { recurrence: { unit: 'week', interval: 0, anchor_date: '2026-11-06' } })

  await withScheduleEditor(async (vm, state) => {
    assert.deepEqual(state.emittedValidity, [false])
    assert.match(vm.validationMessage, /时区无效/)
    assert.equal(state.emittedTimezone.length, 0)
  }, { timezone: 'Not/A_Timezone' })
})
