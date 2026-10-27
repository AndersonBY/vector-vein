import assert from 'node:assert/strict'
import test from 'node:test'
import { createRequire } from 'node:module'
import katexModule from '@vscode/markdown-it-katex'
import { streamingMarkdownPlugin } from '../src/utils/streamingMarkdown.js'

const require = createRequire(import.meta.resolve('vue-markdown-render'))
const MarkdownIt = require('markdown-it')
const md = new MarkdownIt().use(katexModule.default || katexModule).use(streamingMarkdownPlugin)

test('currency remains prose while numeric and bracket math renders', () => {
  const html = md.render('Costs $10 and $20. Math $1+2$ and \\(x^2\\).\n\n\\[x+1\\]\n\n$$x^2$$')
  assert.ok(html.includes('Costs $10 and $20.'))
  assert.equal((html.match(/class="katex"/g) || []).length, 4)
})

test('code spans, backtick and tilde fences preserve dollars and backslashes', () => {
  for (const fence of ['```', '~~~~']) {
    const code = 'echo $10 \\(x\\) \\path\n'
    const html = md.render(`${fence}sh\n${code}${fence}`)
    assert.ok(html.includes('echo $10 \\(x\\) \\path'))
    const encoded = html.match(/data-code="([^"]+)"/)[1]
    assert.equal(decodeURIComponent(encoded), code)
    assert.equal((html.match(/class="code-block"/g) || []).length, 1)
  }
  assert.equal(md.render('`$1+2$ \\(x\\)`').includes('katex'), false)
})

test('Mermaid requires an actual closing fence across progressive chunks', () => {
  for (const fence of ['```', '~~~~']) {
    const source = `${fence}mermaid\ngraph TD\nA-->B\n`
    for (const suffix of ['', fence.slice(0, -1), `${fence} trailing`]) {
      assert.ok(md.render(source + suffix).includes('data-mermaid="false"'))
    }
    const html = md.render(source + fence + '\n\nAfter')
    assert.ok(html.includes('data-mermaid="true"'))
    assert.equal((html.match(/class="code-block"/g) || []).length, 1)
  }
})

test('mounted Markdown updates replace code markup without accumulating wrappers', async () => {
  const { createRenderer, h, nextTick, ref } = await import('vue')
  const { default: VueMarkdown } = await import('vue-markdown-render')
  const host = () => ({ children: [], props: {}, parent: null })
  const renderer = createRenderer({
    createElement: host, createText: host, createComment: host,
    setText() {}, setElementText() {},
    parentNode: node => node.parent, nextSibling: () => null,
    insert(node, parent) { node.parent = parent; parent.children.push(node) },
    remove(node) { node.parent.children.splice(node.parent.children.indexOf(node), 1) },
    patchProp(node, key, previous, value) { node.props[key] = value },
  })
  const source = ref('```python\nprint("$10")')
  const app = renderer.createApp({ render: () => h(VueMarkdown, {
    source: source.value, plugins: [katexModule.default || katexModule, streamingMarkdownPlugin],
  }) })
  const root = host()
  app.mount(root)
  const html = () => root.children[0].props.innerHTML
  assert.equal((html().match(/class="code-block"/g) || []).length, 1)
  source.value += '\n```\n\n~~~~mermaid\ngraph TD\nA-->B'
  await nextTick()
  assert.equal((html().match(/class="code-block"/g) || []).length, 2)
  assert.ok(html().includes('data-mermaid="false"'))
  source.value += '\n~~~~\n\nDone $1+2$'
  await nextTick()
  assert.equal((html().match(/class="code-block"/g) || []).length, 2)
  assert.ok(html().includes('data-mermaid="true"'))
  assert.ok(html().includes('print(&quot;$10&quot;)'))
  assert.ok(html().includes('class="katex"'))
  app.unmount()
  assert.equal(root.children.length, 0)
})

test('container fence completion and numeric math use parser context', () => {
  for (const source of [
    '> ```mermaid\n> graph TD\n> A-->B\n> ```',
    '- ~~~mermaid\n  graph TD\n  A-->B\n  ~~~',
  ]) assert.ok(md.render(source).includes('data-mermaid="true"'))
  const html = md.render('$2$ and $1.5$. Costs $20 and $30.')
  assert.equal((html.match(/class="katex"/g) || []).length, 2)
  assert.ok(html.includes('Costs $20 and $30.'))
})

test('TextOutput preserves diagram hosts, copies raw input and disposes removed diagrams', async () => {
  const vue = await import('vue')
  const { parse, compileScript } = await import('vue/compiler-sfc')
  const { readFile } = await import('node:fs/promises')
  const { default: VueMarkdown } = await import('vue-markdown-render')
  const { Copy, Check } = await import('../src/icons/index.js')
  const source = await readFile(new URL('../src/components/TextOutput.vue', import.meta.url), 'utf8')
  const compiled = compileScript(parse(source).descriptor, { id: 'text-output-test', inlineTemplate: true }).content
  const decode = text => text.replaceAll('&quot;', '"').replaceAll('&amp;', '&').replaceAll('&#39;', "'").replaceAll('&lt;', '<').replaceAll('&gt;', '>')
  class Element {
    constructor(tag = 'div') { this.tag = tag; this.children = []; this.props = {}; this.style = {}; this.dataset = {}; this.parentNode = null; this.textContent = ''; this.className = ''; this.classList = { add() {}, contains: name => this.className.split(' ').includes(name) } }
    setAttribute(key, value) { this.props[key] = value }
    get isConnected() { return Boolean(this.parentNode) }
    appendChild(node) { node.remove(); this.children.push(node); node.parentNode = this }
    remove() { if (this.parentNode) this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null }
    closest(selector) { return this.matches(selector) ? this : this.parentNode?.closest(selector) }
    matches(selector) { return selector === 'pre code' ? this.tag === 'code' : selector === 'pre' ? this.tag === 'pre' : selector === '.header' ? this.className === 'header' : selector === '.copy-container' ? this.className === 'copy-container' : selector === '.code-block' ? this.className === 'code-block' : selector === '.code-block[data-mermaid="true"]' ? this.dataset.mermaid === 'true' : false }
    querySelectorAll(selector) { return this.children.flatMap(child => [...(child.matches(selector) ? [child] : []), ...child.querySelectorAll(selector)]) }
    querySelector(selector) { return this.querySelectorAll(selector)[0] }
    set innerHTML(html) {
      for (const child of [...this.children]) child.remove()
      for (const match of html.matchAll(/<div class="code-block" data-code="([^"]*)" data-mermaid="(true|false)">[\s\S]*?<button[^>]*>([^<]*)<\/button><\/div><pre><code(?: class="([^"]*)")?>[\s\S]*?<\/code><\/pre>\s*<\/div>/g)) {
        const wrapper = new Element(); wrapper.className = 'code-block'; wrapper.dataset = { code: decode(match[1]), mermaid: match[2] }
        const header = new Element(); header.className = 'header'; wrapper.appendChild(header)
        const button = new Element('button'); button.className = 'copy-container'; button.textContent = decode(match[3]); header.appendChild(button)
        const pre = new Element('pre'), code = new Element('code'); code.className = match[4] || ''; code.textContent = decodeURIComponent(wrapper.dataset.code); pre.appendChild(code); wrapper.appendChild(pre)
        this.appendChild(wrapper)
      }
    }
  }
  const renderer = vue.createRenderer({
    createElement: tag => new Element(tag), createText: text => { const node = new Element('text'); node.textContent = text; return node }, createComment: () => new Element('comment'),
    setText(node, value) { node.textContent = value }, setElementText(node, value) { node.textContent = value },
    parentNode: node => node.parentNode, nextSibling: node => node.parentNode?.children[node.parentNode.children.indexOf(node) + 1] || null,
    insert(node, parent, anchor) { node.remove(); const index = parent.children.indexOf(anchor); if (index < 0) parent.children.push(node); else parent.children.splice(index, 0, node); node.parentNode = parent }, remove: node => node.remove(),
    patchProp(node, key, previous, value) { if (key === 'innerHTML') node.innerHTML = value; else node.props[key] = value },
  })
  let mounted = 0, unmounted = 0
  const MermaidRenderer = { props: ['content'], emits: ['rendered'], setup(props, { emit }) {
    vue.onMounted(() => { mounted++; emit('rendered') }); vue.onBeforeUnmount(() => unmounted++)
    return () => vue.h('svg')
  } }
  const bindings = { ...vue, Copy, Check, render: renderer.render, streamingMarkdownPlugin, useI18n: () => ({ t: key => key }), VueMarkdown,
    markdownItKatexModule: katexModule, MarkdownItGitHubAlerts() {}, MarkdownItLinkAttributes() {}, MermaidRenderer,
    hljs: { highlightElement(block) { block.dataset.highlighted = 'yes' } },
  }
  const body = compiled.replace(/^import\s+['"][^'"]+['"];?\s*$/gm, '').replace(/import\s+([\s\S]*?)\s+from\s+['"]([^'"]+)['"];?/g, (statement, names, module) => {
    if (module === 'vue') for (const part of names.replace(/[{}]/g, '').split(',')) {
      const [name, alias] = part.trim().split(/\s+as\s+/); bindings[alias || name] = bindings[name]
    }
    return ''
  }).replace(/import\s+['"][^'"]+['"];?/g, '').replace('export default', 'return')
  const names = Object.keys(bindings).filter(key => /^[A-Za-z_$][\w$]*$/.test(key))
  const TextOutput = new Function('bindings', `const { ${names.join(', ')} } = bindings; ${body}`)(bindings)
  const documentBefore = globalThis.document
  const clipboardBefore = globalThis.navigator.clipboard
  globalThis.document = { createElement: tag => new Element(tag) }
  const copied = []
  globalThis.navigator.clipboard = { async writeText(text) { copied.push(text) } }
  const input = vue.ref('```python\nprint("$20 \\\\path")\n```\n\n~~~mermaid\ngraph TD\nA-->B')
  const wrapperClass = vue.ref(''), markdown = vue.ref(true)
  const host = new Element()
  const app = renderer.createApp({ render: () => vue.h(TextOutput, { text: input.value, wrapperClass: wrapperClass.value, renderMarkdown: markdown.value }) })
  const Paragraph = { props: ['copyable'], setup: (props, { slots }) => () => vue.h('paragraph', { copyable: props.copyable }, slots.default?.()) }
  app.component('ATypographyParagraph', Paragraph)
  try {
    app.mount(host)
    assert.equal(mounted, 0)
    input.value += '\n~~~'
    await vue.nextTick()
    assert.equal(mounted, 1)
    const diagram = host.querySelectorAll('.code-block')[1].children.at(-1)
    assert.equal(host.querySelectorAll('.code-block')[1].querySelector('.header').style.display, 'none')
    assert.equal(host.querySelectorAll('.code-block')[1].style.background, 'transparent')
    input.value += '\n\nLater chunk'
    await vue.nextTick()
    assert.equal(mounted, 1)
    assert.equal(host.querySelectorAll('.code-block')[1].children.at(-1), diagram)
    assert.equal(host.querySelectorAll('.code-block')[1].querySelector('.header').style.display, 'none')
    assert.equal(host.querySelectorAll('.code-block')[1].style.background, 'transparent')
    const root = host.children[0], button = host.querySelectorAll('.copy-container')[0]
    await root.props.onClick({ target: button })
    assert.equal(copied[0], 'print("$20 \\\\path")\n')
    assert.equal(button.props['aria-label'], 'components.copyButton.copy_success')
    assert.equal(button.props.title, 'components.copyButton.copy_success')
    assert.equal(button._vnode.type, Check)
    assert.equal(button.textContent, '')
    wrapperClass.value = 'updated'
    await vue.nextTick()
    assert.equal(button.props['aria-label'], 'components.copyButton.click_to_copy')
    assert.equal(button.children.length, 1)
    assert.equal(button._vnode.type, Copy)
    assert.equal(mounted, 1)
    assert.equal(host.querySelectorAll('.code-block')[1].children.at(-1), diagram)
    const paragraphs = () => host.children[0].children.filter(node => node.tag === 'paragraph')
    assert.equal(paragraphs()[0].props.copyable.text, input.value)
    markdown.value = false
    await vue.nextTick()
    assert.equal(unmounted, 1)
    assert.equal(button._vnode, null)
    assert.equal(paragraphs()[0].props.copyable.text, input.value)
    assert.equal(paragraphs()[0].children.map(node => node.textContent).join(''), input.value)
    input.value = ['first $20', { value: '\\path' }]
    await vue.nextTick()
    assert.equal(paragraphs()[0].props.copyable.text, 'first $20\n\n{"value":"\\\\path"}')
    app.unmount()
    assert.equal(unmounted, 1)
  } finally {
    app.unmount()
    globalThis.document = documentBefore
    globalThis.navigator.clipboard = clipboardBefore
  }
})
