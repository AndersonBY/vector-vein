import assert from 'node:assert/strict'
import test from 'node:test'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { createRenderer, h, nextTick, reactive } from 'vue'
import { createI18n } from 'vue-i18n'
import { parse, compileScript, compileTemplate } from 'vue/compiler-sfc'
import { createServer } from 'vite'

const deferred = () => { let resolve; const promise = new Promise(r => { resolve = r }); return { promise, resolve } }
const flush = async () => { await nextTick(); await nextTick() }

test('mounted attachments preserve selections, handle preview lifecycle, replace history and show safe unavailable images', async () => {
  const previous = globalThis.__attachmentImages
  const requests = []
  globalThis.__attachmentImages = (info, thumbnail, current) => {
    const request = { ...deferred(), path: info.path, thumbnail, current }
    requests.push(request)
    return request.promise
  }
  const filename = fileURLToPath(new URL('../src/components/workspace/chat/AttachmentsList.vue', import.meta.url))
  const { descriptor } = parse(await readFile(filename, 'utf8'), { filename })
  const compiled = compileScript(descriptor, { id: 'attachments-ui-test' })
  const script = compiled.content.replace('export default', 'const component =')
    .replace("'@/utils/chatAttachments'", "'virtual:attachment-images'")
    .replace("'ant-design-vue'", "'virtual:attachment-theme'")
  const template = compileTemplate({ source: descriptor.template.content, filename, id: 'attachments-ui-test',
    compilerOptions: { bindingMetadata: compiled.bindings } }).code.replace('export function render', 'function render')
  const moduleId = '/attachments-ui-mounted.js'
  const server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    plugins: [{ name: 'attachments-ui-test',
      resolveId: id => [moduleId, 'virtual:attachment-images', 'virtual:attachment-theme'].includes(id) ? id : undefined,
      load: id => id === moduleId ? `${script}\n${template}\ncomponent.render = render; export default component`
        : id === 'virtual:attachment-images' ? 'export {getAttachmentInfo} from "/src/utils/chatAttachments.js"; export const loadAttachmentImage = (...args) => globalThis.__attachmentImages(...args)'
          : id === 'virtual:attachment-theme' ? 'import {ref} from "vue"; export const theme = {useToken:()=>({token:ref({colorBgContainer:"#fff",colorBorderSecondary:"#ddd",colorText:"#222",colorTextSecondary:"#666"})})}' : undefined }],
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  let app
  let mounted = false
  try {
    const component = (await server.ssrLoadModule(moduleId)).default
    const renderer = createRenderer({
      createElement: type => ({ type, children: [], props: {} }), createText: text => ({ text }), createComment: text => ({ text }),
      setText: (node, text) => { node.text = text }, setElementText: (node, text) => { node.text = text },
      parentNode: node => node.parent, nextSibling: node => node.parent?.children[node.parent.children.indexOf(node) + 1] || null,
      patchProp: (node, key, _old, value) => { node.props[key] = value },
      insert: (node, parent, anchor) => {
        if (node.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1)
        node.parent = parent
        const index = anchor ? parent.children.indexOf(anchor) : -1
        if (index < 0) parent.children.push(node)
        else parent.children.splice(index, 0, node)
      },
      remove: node => { if (node?.parent) node.parent.children.splice(node.parent.children.indexOf(node), 1) },
    })
    const photo = 'C:\\工作\\照片.PNG'
    const source = Object.freeze([photo, 'C:\\工作\\中文报告.pdf', photo])
    const props = reactive({ modelValue: source, removable: true })
    let c
    const wrapped = { ...component, setup(p, ctx) { c = component.setup(p, ctx); return c } }
    app = renderer.createApp({ render: () => h(wrapped, { ...props, 'onUpdate:modelValue': value => { props.modelValue = value } }) })
    const messages = JSON.parse(await readFile(new URL('../src/locales/en-US.json', import.meta.url), 'utf8'))
    app.use(createI18n({ legacy: false, locale: 'en', messages: { en: messages } }))
    for (const name of ['AFlex', 'AButton', 'AImage']) app.component(name, {
      inheritAttrs: false, setup: (_, { attrs, slots }) => () => h(name, attrs, [slots.default?.(), slots.icon?.()]),
    })
    const root = { children: [] }
    app.mount(root)
    mounted = true
    assert.equal(requests.length, 1, 'duplicates share a thumbnail within the list')
    assert.equal(requests[0].thumbnail, true)
    assert.equal(c.items.value[1].name, '中文报告.pdf')
    requests[0].resolve('data:image/png;base64,AAAA')
    await flush()
    assert.equal(c.thumbnails.get(photo).src, 'data:image/png;base64,AAAA')
    c.removeAttachment(2)
    await flush()
    assert.deepEqual([...props.modelValue], [photo, 'C:\\工作\\中文报告.pdf'])
    assert.equal(source.length, 3, 'selection updates do not mutate the caller array')
    assert.equal(requests.length, 1)
    const stale = c.openImage(c.items.value[0])
    assert.equal(requests[1].thumbnail, false)
    c.closePreview()
    requests[1].resolve('data:image/png;base64,U1RBTEU=')
    await stale
    assert.equal(c.preview.visible, false)
    assert.equal(c.preview.src, '')
    const opening = c.openImage(c.items.value[0])
    requests[2].resolve('data:image/png;base64,RlVMTA==')
    await opening
    await flush()
    assert.equal(c.preview.visible, true)
    assert.equal(c.preview.src, 'data:image/png;base64,RlVMTA==')
    const find = (node, type) => node.type === type ? node : node.children?.map(child => find(child, type)).find(Boolean)
    assert.equal(find(root, 'AImage').props.preview.visible, true)
    c.previewVisibleChange(false)
    await flush()
    assert.equal(c.preview.src, '', 'closing releases original image data')
    const failed = c.openImage(c.items.value[0])
    requests[3].resolve(null)
    await failed
    assert.equal(c.previewError.value, photo)
    assert.equal(c.opening.value, '')
    const oldImage = c.openImage(c.items.value[0])
    props.modelValue = ['C:/history/replaced.jpg']
    props.removable = false
    await flush()
    requests[4].resolve('data:image/png;base64,T0xE')
    await oldImage
    assert.equal(c.preview.visible, false)
    assert.equal(c.thumbnails.has(photo), false)
    c.removeAttachment(0)
    assert.equal(props.modelValue.length, 1, 'history has no removal action')
    requests[5].resolve(null)
    await flush()
    assert.equal(c.thumbnails.get('C:/history/replaced.jpg').failed, true)
    const text = node => [node.text || '', ...(node.children || []).map(text)].join(' ')
    assert.match(text(root), /Image unavailable/)
    props.modelValue = ['C:/history/pending.webp']
    await flush()
    assert.equal(requests.length, 7)
    app.unmount()
    mounted = false
    requests[6].resolve('data:image/png;base64,AAAA')
    await flush()
    assert.equal(c.thumbnails.size, 0)
    assert.equal(c.preview.src, '')
  } finally {
    if (mounted) app.unmount()
    await server.close()
    globalThis.__attachmentImages = previous
  }
})
