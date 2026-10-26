import assert from 'node:assert/strict'
import { createRequire } from 'node:module'
import test from 'node:test'
import * as dagre from '@dagrejs/dagre'
import katexPluginModule from '@vscode/markdown-it-katex'
import { Transformer } from 'markmap-lib'
import { createPinia, storeToRefs } from 'pinia'
import { nextTick } from 'vue'
import { useGeneralQueueStore } from '../src/stores/generalQueue.js'

const markdownRequire = createRequire(import.meta.resolve('vue-markdown-render'))
const MarkdownIt = markdownRequire('markdown-it')
const katexPlugin = katexPluginModule.default || katexPluginModule

test('Dagre public ESM entry lays out connected workflow nodes', () => {
  for (const direction of ['LR', 'TB']) {
    const graph = new dagre.graphlib.Graph()
      .setGraph({ rankdir: direction })
      .setDefaultEdgeLabel(() => ({}))
    graph.setNode('input', { width: 250, height: 150 })
    graph.setNode('output', { width: 250, height: 150 })
    graph.setEdge('input', 'output')
    dagre.layout(graph)
    const axis = direction === 'LR' ? 'x' : 'y'
    assert.ok(graph.node('output')[axis] > graph.node('input')[axis])
    assert.ok(graph.edge('input', 'output').points.every(
      point => Number.isFinite(point.x) && Number.isFinite(point.y),
    ))
  }
})

test('Markdown and mind maps render formulas with the shared KaTeX version', () => {
  const markdown = new MarkdownIt().use(katexPlugin)
  const html = markdown.render('Inline $x^2$\n\n$$\n\\frac{1}{2}\n$$')
  assert.match(html, /class="katex"/)
  assert.match(html, /katex-display/)
  assert.doesNotMatch(html, /katex-error/)
  const { root } = new Transformer().transform('# Formula\n\n- $x^2$')
  assert.match(root.children[0].content, /class="katex"/)
})

test('application queue actions preserve reactive refs and isolate stores', async () => {
  const first = useGeneralQueueStore(createPinia())
  const second = useGeneralQueueStore(createPinia())
  const { items } = storeToRefs(first)
  const changes = []
  const unsubscribe = first.$subscribe((_mutation, state) => {
    changes.push(state.items.map(item => ({ ...item })))
  })
  first.setItems([{ id: 'workflow-1', status: 'queued' }])
  await nextTick()
  first.upsertItem({ id: 'workflow-1', status: 'finished' })
  await nextTick()
  assert.deepEqual(items.value, [{ id: 'workflow-1', status: 'finished' }])
  assert.deepEqual(second.items, [])
  assert.equal(changes.length, 2)
  first.removeItem('workflow-1')
  assert.deepEqual(items.value, [])
  first.clear()
  assert.equal(first.lastUpdatedAt, null)
  unsubscribe()
})
