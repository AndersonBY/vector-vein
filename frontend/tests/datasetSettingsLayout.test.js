import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile, readdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createSSRApp, h } from 'vue'
import { renderToString } from 'vue/server-renderer'
import { createI18n } from 'vue-i18n'
import { compileScript, compileTemplate, parse } from 'vue/compiler-sfc'
import { createServer } from 'vite'
import vue from '@vitejs/plugin-vue'

const source = file => readFile(new URL(`../src/${file}`, import.meta.url), 'utf8')
const find = (node, predicate) => [...(predicate(node) ? [node] : []), ...(node.children || []).flatMap(child => find(child, predicate))]
const attr = (node, name) => node.props?.find(prop => prop.type === 6 && prop.name === name)?.value?.content
const directive = (node, name, arg) => node.props?.find(prop => prop.type === 7 && prop.name === name && (!arg || prop.arg?.content === arg))
async function template(file) {
  const { descriptor, errors } = parse(await source(file), { filename: file })
  assert.deepEqual(errors, [])
  const script = compileScript(descriptor, { id: file })
  assert.deepEqual(compileTemplate({ source: descriptor.template.content, filename: file, id: file,
    compilerOptions: { bindingMetadata: script.bindings } }).errors, [])
  return descriptor.template.ast
}

test('dataset pages and components use normal buttons and confirmation actions', async () => {
  for (const directory of ['views/Workspace/Database', 'components/workspace/database']) {
    for (const filename of await readdir(new URL(`../src/${directory}`, import.meta.url))) {
      if (!filename.endsWith('.vue')) continue
      const file = `${directory}/${filename}`
      const ast = await template(file)
      for (const button of find(ast, node => ['a-button', 'IconButton'].includes(node.tag))) {
        assert.notEqual(attr(button, 'type'), 'primary', file)
      }
      for (const dialog of find(ast, node => ['a-modal', 'a-popconfirm'].includes(node.tag))) {
        assert.equal(attr(dialog, 'ok-type'), 'default', file)
      }
    }
  }
})

test('knowledge base navigation and actions share one header; metadata and folder navigation remain separate', async () => {
  const ast = await template('views/Workspace/Database/KnowledgeBaseDetail.vue')
  const header = find(ast, node => node.tag === 'header')[0]
  const crumbs = find(header, node => node.tag === 'a-breadcrumb-item')
  assert.equal(crumbs.length, 2)
  assert.match(crumbs[0].loc.source, /DataSpaceMain/)
  assert.match(crumbs[0].loc.source, /knowledgeBase.title/)
  assert.match(crumbs[1].loc.source, /base\?\.name/)
  assert.equal(find(header, node => node.tag === 'IconButton').length, 2)
  assert.equal(find(ast, node => node.tag === 'h1').length, 0)
  assert.equal(find(header, node => attr(node, 'class') === 'kb-meta').length, 0)
  assert.equal(find(ast, node => attr(node, 'class') === 'kb-meta').length, 1)
  const files = find(ast, node => attr(node, 'class') === 'files')[0]
  assert.equal(find(files, node => node.tag === 'a-breadcrumb').length, 1)
  assert.match(files.loc.source, /@click="navigate\(crumb.id\)"/)
})

test('Vekai entries appear only in their model card extra slots and the embedding info block is removed', async () => {
  const ast = await template('views/Settings.vue')
  const toolbar = find(ast, node => attr(node, 'class') === 'settings-toolbar')[0]
  assert.equal(find(toolbar, node => node.tag === 'VekaiSettings').length, 0)
  assert.equal(find(ast, node => node.tag === 'VekaiSettings').length, 2)
  for (const kind of ['embedding', 'rerank']) {
    const card = find(ast, node => node.tag === 'a-card' && directive(node, 'show')?.exp?.content.includes(`${kind}_models`))[0]
    const extra = find(card, node => directive(node, 'slot', 'extra'))[0]
    const vekai = find(extra, node => node.tag === 'VekaiSettings')
    assert.equal(vekai.length, 1)
    assert.equal(attr(vekai[0], 'kind'), kind)
    if (kind === 'embedding') assert.equal(find(card, node => node.tag === 'a-alert').length, 0)
  }
})

test('each Vekai panel renders only its own service form without modifying settings', async () => {
  const server = await createServer({ configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [vue()], resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } }, server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom' })
  try {
    const component = (await server.ssrLoadModule('/src/components/settings/VekaiSettings.vue')).default
    for (const kind of ['embedding', 'rerank']) {
      const draft = { llm_settings: { endpoints: [] } }, before = structuredClone(draft), warnings = []
      const app = createSSRApp(component, { kind, modelValue: draft })
      app.config.warnHandler = warning => warnings.push(warning)
      app.use(createI18n({ legacy: false, locale: 'en', messages: { en: JSON.parse(await source('locales/en-US.json')) } }))
      for (const name of ['AButton', 'ATooltip', 'AModal', 'ATypographyTitle', 'AForm', 'AFormItem']) {
        app.component(name, { setup: (_props, { slots }) => () => h(name === 'AForm' ? 'form' : 'div', slots.default?.()) })
      }
      app.component('AInput', { inheritAttrs: false, setup: (_props, { attrs }) => () => h('input', { value: attrs.value }) })
      const html = await renderToString(app)
      assert.equal((html.match(/<form(?:\s[^>]*)?>/g) || []).length, 1)
      assert.match(html, new RegExp(kind === 'embedding' ? '8013' : '8012'))
      assert.doesNotMatch(html, new RegExp(kind === 'embedding' ? '8012|local-reranker' : '8013|local-embedding'))
      assert.deepEqual(draft, before)
      assert.deepEqual(warnings, [])
    }
  } finally { await server.close() }
})
