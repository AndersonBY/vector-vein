import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { ref, reactive, computed, watch, nextTick, effectScope, createRenderer, h } from 'vue'
import { parse, compileScript } from 'vue/compiler-sfc'
import { useVueFlow } from '@vue-flow/core'
import { createWorkflowHistory, workflowSnapshot, isHistoryTextTarget } from '../src/utils/workflowHistory.js'

const condition = fields => fields.input.value === 'yes'
const node = (id = 'a') => ({ id, type: 'Example', position: { x: 0, y: 0 },
  data: { template: { input: { value: 'yes', condition } } } })
const edge = { id: 'ab', source: 'a', target: 'b', ignored: true }

test('snapshots preserve functions and ignored topology, isolating mutations and excluding rendering/ghosts', () => {
  const a = node()
  const snapshot = workflowSnapshot([a, node('b'), { ...node('ghost'), shadow: true }],
    [edge, { ...edge, id: 'ghost', target: 'ghost' }])
  a.selected = true
  a.initialized = true
  a.computedPosition = { x: 900 }
  a.dimensions = { width: 200, height: 100 }
  a.data.template.input.hide = true
  a.data.template.input.group_collpased = true
  assert.deepEqual(workflowSnapshot([a, node('b')], [edge]), snapshot)
  a.data.template.input.value = 'no'
  assert.equal(snapshot.nodes[0].data.template.input.condition(snapshot.nodes[0].data.template), true)
  assert.equal(snapshot.edges[0].ignored, true)
  assert.equal(snapshot.nodes.length, 2)
  assert.equal(snapshot.edges.length, 1)
})

test('history restores graph edits, invalidates redo before commit, and caps retained undo actions', () => {
  const history = createWorkflowHistory(2)
  const graph = count => workflowSnapshot(Array.from({ length: count }, (_, i) => node(`${i}`)), [])
  history.reset(graph(1))
  assert.equal(history.canUndo, false)
  history.observe(graph(2))
  assert.equal(history.canUndo, true)
  assert.equal(history.undo().nodes.length, 1)
  assert.equal(history.canRedo, true)
  history.observe(graph(3))
  assert.equal(history.canRedo, false)
  assert.equal(history.redo(), undefined)
  history.commit()
  history.observe(graph(4)); history.commit()
  history.observe(graph(5)); history.commit()
  assert.equal(history.undo().nodes.length, 4)
  const restored = history.undo()
  assert.equal(restored.nodes.length, 3)
  restored.nodes[0].data.template.input.value = 'changed'
  assert.equal(history.undo(), undefined)
  assert.equal(history.redo().nodes[0].data.template.input.value, 'yes')
})

test('native editable targets and modal content reserve their own undo shortcuts', () => {
  let selector
  assert.equal(isHistoryTextTarget({ closest(value) { selector = value; return {} } }), true)
  for (const expected of ['input', 'textarea', 'contenteditable', '.cm-editor', '[role="dialog"]', '.ant-modal']) {
    assert.ok(selector.includes(expected))
  }
  assert.equal(isHistoryTextTarget({ closest: () => null }), false)
  assert.equal(isHistoryTextTarget(null), false)
})

test('BaseNode displayed custom title follows restored data and falls back to its translated title', async () => {
  const source = await readFile(new URL('../src/components/nodes/BaseNode.vue', import.meta.url), 'utf8')
  const block = source.slice(source.indexOf('const title = ref('), source.indexOf('const description ='))
  const props = reactive({ data: { title: 'Edited title' }, title: '', translatePrefix: 'example' })
  const scope = effectScope()
  try {
    const title = scope.run(() => new Function('ref', 'watch', 'props', 't', `${block}; return title`)(ref, watch, props, key => key))
    assert.equal(title.value, 'Edited title')
    props.data = { title: 'Original title' }
    await nextTick()
    assert.equal(title.value, 'Original title')
    props.data = {}
    await nextTick()
    assert.equal(title.value, 'example.title')
    props.title = 'Explicit default'
    props.data = { title: 'Another edit' }
    await nextTick()
    props.data = {}
    await nextTick()
    assert.equal(title.value, 'Explicit default')
  } finally { scope.stop() }
})

test('editor history wiring groups an entire drag, captures connected deletion and preserves conditional fields', async () => {
  const source = await readFile(new URL('../src/views/Workspace/WorkflowEditor.vue', import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  assert.doesNotThrow(() => compileScript(descriptor, { id: 'workflow-history-test' }))
  assert.match(source, /@node-drag-start="onHistoryDragStart" @node-drag-stop="onHistoryDragStop"/)
  assert.match(source, /:disabled="!canUndo" :aria-label=/)
  assert.match(source, /:disabled="!canRedo" :aria-label=/)
  assert.match(source, /activeTab\.value !== 'canvas'/)
  assert.match(source, /clearTimeout\(initialSnapshotTimeout\)/)
  const block = source.slice(source.indexOf('const history = createWorkflowHistory'), source.indexOf('onConnect((params)'))
  const flow = useVueFlow('history-regression')
  const { nodes, edges, findNode } = flow
  flow.setElements([node(), node('b'), edge])
  const elements = ref([])
  const wrapperSource = await readFile(new URL('../src/components/nodes/tools/ProgrammingFunction.vue', import.meta.url), 'utf8')
  assert.match(wrapperSource, /const fieldsData = ref\(props.data.template\)/)
  const renderedFields = new Map()
  let hydrateOnMount = false
  const NodeWrapper = {
    props: ['id', 'data'],
    setup(props) {
      // Match the existing node wrappers' setup-time template reference.
      const fieldsData = ref(props.data.template)
      if (hydrateOnMount) fieldsData.value.input.hydrated = true
      renderedFields.set(props.id, fieldsData)
      return () => null
    },
  }
  const noop = () => {}
  const renderer = createRenderer({
    createElement: () => ({}), createText: () => ({}), createComment: () => ({}),
    insert: noop, remove: noop, setText: noop, setElementText: noop, patchProp: noop,
    parentNode: () => null, nextSibling: () => null,
  })
  const mountedNodes = renderer.createApp({ render: () => h('div', nodes.value.map(item => h(NodeWrapper, {
    key: item.id, id: item.id, data: item.data,
  }))) })
  mountedNodes.mount({})
  const stopModel = watch(elements, value => {
    flow.setElements(value)
  }, { flush: 'sync' })
  const editor = new Function('ref', 'computed', 'watch', 'nextTick', 'createWorkflowHistory', 'workflowSnapshot',
    'nodes', 'edges', 'elements', 'findNode', `${block}\nreturn { undo, redo, canUndo, canRedo, onHistoryDragStart, onHistoryDragStop,
      init() { history.reset(workflowSnapshot(nodes.value, edges.value)); historyReady = true; historyVersion.value++ },
      dispose() { clearTimeout(historyTimeout); historyDisposed = true } }`)(
    ref, computed, watch, nextTick, createWorkflowHistory, workflowSnapshot, nodes, edges, elements, findNode)
  const settle = async () => { await nextTick(); await nextTick(); await nextTick() }
  try {
    editor.init()
    editor.onHistoryDragStart()
    nodes.value[0].position.x = 20
    await new Promise(resolve => setTimeout(resolve, 230))
    nodes.value[0].position.x = 100
    editor.onHistoryDragStop()
    editor.undo(); await settle()
    assert.equal(nodes.value[0].position.x, 0)
    assert.equal(editor.canUndo.value, false)
    editor.redo(); await settle()
    assert.equal(nodes.value[0].position.x, 100)
    nodes.value = nodes.value.filter(item => item.id !== 'b')
    edges.value = []
    await settle()
    hydrateOnMount = true
    editor.undo(); await settle()
    assert.equal(nodes.value.length, 2)
    assert.equal(edges.value.length, 1)
    assert.equal(nodes.value[1].data.template.input.hydrated, true)
    assert.equal(editor.canRedo.value, true)
    // Vue Flow's EdgeWrapper writes these after handles/layout settle.
    Object.assign(edges.value[0], { sourceX: 120, sourceY: 80, targetX: 300, targetY: 240 })
    await settle()
    assert.equal(editor.canRedo.value, true)
    editor.redo(); await settle()
    assert.equal(nodes.value.length, 1)
    assert.equal(edges.value.length, 0)
    editor.undo(); await settle()
    assert.equal(nodes.value.length, 2)
    assert.equal(edges.value.length, 1)
    nodes.value[0].data.template.input.value = 'no'
    assert.equal(editor.canRedo.value, false)
    editor.undo(); await settle()
    assert.equal(nodes.value[0].data.template.input.condition(nodes.value[0].data.template), true)
    assert.equal(renderedFields.get('a').value.input.value, 'yes')
    editor.redo(); await settle()
    assert.equal(nodes.value[0].data.template.input.condition(nodes.value[0].data.template), false)
    assert.equal(renderedFields.get('a').value.input.value, 'no')
    editor.undo(); await settle()
    assert.equal(editor.canRedo.value, true)
    nodes.value[0].selected = true
    nodes.value[0].dimensions = { width: 100, height: 20 }
    nodes.value[0].data.template.input.hide = true
    assert.equal(editor.canRedo.value, true)
    nodes.value[0].ignored = true
    delete edges.value[0].ignored
    editor.undo(); await settle()
    assert.equal(nodes.value[0].ignored, undefined)
    assert.equal(edges.value[0].ignored, true)
    editor.redo(); await settle()
    assert.equal(nodes.value[0].ignored, true)
    assert.equal(edges.value[0].ignored, undefined)
  } finally { editor.dispose(); stopModel(); mountedNodes.unmount(); flow.$destroy() }
})
