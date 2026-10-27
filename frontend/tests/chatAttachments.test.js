import assert from 'node:assert/strict'
import test, { before, after } from 'node:test'
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'

let server, getAttachmentInfo, loadAttachmentImage
const originalWindow = globalThis.window
const png = 'data:image/png;base64,YWJj'
const local = name => getAttachmentInfo(`/tmp/${name}.png`)
const tick = async () => { await Promise.resolve(); await Promise.resolve() }
const installAPI = handler => {
  globalThis.window = { pywebview: { api: { setting__attachment_image: handler } } }
}

before(async () => {
  server = await createServer({
    configFile: false, root: fileURLToPath(new URL('..', import.meta.url)),
    resolve: { alias: { '@': fileURLToPath(new URL('../src', import.meta.url)) } },
    server: { middlewareMode: true, hmr: false, ws: false }, optimizeDeps: { noDiscovery: true }, appType: 'custom',
  })
  ;({ getAttachmentInfo, loadAttachmentImage } = await server.ssrLoadModule('/src/utils/chatAttachments.js'))
})
after(async () => { globalThis.window = originalWindow; await server?.close() })

test('attachment names preserve local literals and distinguish local paths from URL names', () => {
  for (const [path, name] of [
    ['C:\\Users\\中文\\100%#原图.JpG', '100%#原图.JpG'],
    ['C:/images/photo.WEBP', 'photo.WEBP'],
    ['/home/a/100%#?.PNG', '100%#?.PNG'],
    ['./images/中文%20原图.gif', '中文%20原图.gif'],
    ['photo.bmp', 'photo.bmp'],
  ]) {
    const info = getAttachmentInfo(path, 4)
    assert.deepEqual(info, { key: `4:${path}`, path, name, kind: 'local', image: true })
  }
  const url = 'https://example.com/%E4%B8%AD%E6%96%87%20%25%23%3F.JPEG?token=private#part'
  assert.deepEqual(getAttachmentInfo(url), {
    key: `0:${url}`, path: url, name: '中文 %#?.JPEG', kind: 'remote', image: true,
  })
  assert.equal(getAttachmentInfo('http://example.com/bad%ZZ.JPG?q=1').name, 'bad%ZZ.JPG')
  assert.equal(getAttachmentInfo('https://example.com/report.pdf?image=foo.png').image, false)
  assert.equal(getAttachmentInfo('/tmp/report.png?literal').image, false)
  assert.equal(getAttachmentInfo('/tmp/report%2Epng').image, false)
})

test('only local file URIs become backend paths and malformed or unsafe schemes never auto-load', () => {
  for (const [uri, path, name] of [
    ['file:///C:/Users/%E4%B8%AD%E6%96%87/a%20%23%25.png', 'C:/Users/中文/a #%.png', 'a #%.png'],
    ['file:///C:%5Cimages%5Cphoto.png', 'C:\\images\\photo.png', 'photo.png'],
    ['file://localhost/home/user/a%3Fb.GIF', '/home/user/a?b.GIF', 'a?b.GIF'],
    ['file:///tmp/photo.jpg?download=1#fragment', '/tmp/photo.jpg', 'photo.jpg'],
  ]) assert.deepEqual(getAttachmentInfo(uri), { key: `0:${uri}`, path, name, kind: 'local', image: true })
  for (const path of [
    'javascript:alert(1).png', 'data:text/html;base64,PHNjcmlwdD4=', 'data:image/svg+xml,<svg/>',
    'data:image/png;base64,YWJj', 'custom:photo.jpg', 'ftp://example.com/photo.jpg',
    'file://server/share/photo.png', 'file:///%5Cserver/share/photo.png', 'file:///tmp/bad%ZZ.png', 'file:///tmp/%00.png',
    'file:photo.png', 'https://', '\\\\server\\share\\photo.png', '//server/share/photo.png',
    '/tmp/a\u0000.png', ' file://remote/photo.png',
  ]) {
    const info = getAttachmentInfo(path)
    assert.equal(info.kind, 'unsupported', path)
    assert.equal(info.image, false, path)
  }
  for (const value of [undefined, null, 0, false, {}, [], '', '   ']) {
    const info = getAttachmentInfo(value)
    assert.equal(info.name, '')
    assert.equal(info.kind, 'unsupported')
    assert.equal(info.image, false)
  }
})

test('image loading uses the settings bridge only for local images and validates its result', async () => {
  const calls = []
  installAPI(async payload => { calls.push(payload); return { status: 200, data: { url: png } } })
  const info = local('中文%#')
  const before = JSON.stringify(info)
  assert.equal(await loadAttachmentImage(info), png)
  assert.deepEqual(calls, [{ path: '/tmp/中文%#.png', thumbnail: true }])
  assert.equal(await loadAttachmentImage(info, false), png)
  assert.deepEqual(calls[1], { path: '/tmp/中文%#.png', thumbnail: false })
  assert.equal(JSON.stringify(info), before)
  const remote = getAttachmentInfo('https://example.com/image.PNG?q=1#part')
  assert.equal(await loadAttachmentImage(remote), remote.path)
  assert.equal(calls.length, 2)
  for (const value of [null, {}, getAttachmentInfo('file://remote/a.png'), getAttachmentInfo('/tmp/a.pdf'),
    { path: 'javascript:evil.png', kind: 'remote', image: true }]) {
    assert.equal(await loadAttachmentImage(value), null)
  }
  assert.equal(calls.length, 2)
  for (const url of [
    'data:image/png;base64,YWJj', 'data:image/jpeg;base64,YWJj', 'data:image/gif;base64,YWJj',
    'data:image/webp;base64,YWJj', 'data:image/bmp;base64,YWJj',
  ]) {
    installAPI(async () => ({ status: 200, data: { url } }))
    assert.equal(await loadAttachmentImage(info), url)
  }
  for (const response of [
    { status: 400 }, { status: 404 }, { status: 200 }, { status: 200, data: { url: 'https://unsafe/image.png' } },
    { status: 200, data: { url: 'data:text/html;base64,YWJj' } },
    { status: 200, data: { url: 'data:image/svg+xml;base64,YWJj' } },
    { status: 200, data: { url: 'data:image/png;base64,' } },
    { status: 200, data: { url: 'data:image/png;base64,not base64' } },
  ]) {
    installAPI(async () => response)
    assert.equal(await loadAttachmentImage(info), null)
  }
  installAPI(async () => { throw new Error('missing file') })
  assert.equal(await loadAttachmentImage(info), null)
})

test('all callers share three local read slots and full previews pass queued thumbnails', async () => {
  const pending = []
  let active = 0, maximum = 0
  installAPI(payload => new Promise(resolve => {
    active++
    maximum = Math.max(maximum, active)
    pending.push({ payload, finish: () => { active--; resolve({ status: 200, data: { url: png } }) } })
  }))
  const results = [0, 1, 2, 3, 4].map(index => loadAttachmentImage(local(`thumb${index}`)))
  results.push(loadAttachmentImage(local('full'), false))
  assert.equal(pending.length, 3)
  pending[0].finish()
  await tick()
  assert.equal(pending.length, 4)
  assert.deepEqual(pending[3].payload, { path: '/tmp/full.png', thumbnail: false })
  pending[1].finish()
  await tick()
  assert.equal(pending[4].payload.path, '/tmp/thumb3.png')
  pending[2].finish()
  await tick()
  assert.equal(pending[5].payload.path, '/tmp/thumb4.png')
  pending.slice(3).forEach(item => item.finish())
  assert.deepEqual(await Promise.all(results), Array(6).fill(png))
  assert.equal(maximum, 3)
  assert.equal(active, 0)
})

test('expired jobs never start, expired responses are ignored, and cancellation or failure frees the queue', async () => {
  const pending = []
  installAPI(payload => new Promise((resolve, reject) => pending.push({ payload, resolve, reject })))
  assert.equal(await loadAttachmentImage(local('never'), true, () => false), null)
  assert.equal(await loadAttachmentImage(getAttachmentInfo('https://example.com/expired.png'), true, () => false), null)
  let runningCurrent = true, queuedCurrent = true
  const running = loadAttachmentImage(local('running'), true, () => runningCurrent)
  const second = loadAttachmentImage(local('second'))
  const third = loadAttachmentImage(local('third'))
  const skipped = loadAttachmentImage(local('skipped'), true, () => queuedCurrent)
  const survivor = loadAttachmentImage(local('survivor'))
  assert.equal(pending.length, 3)
  queuedCurrent = false
  runningCurrent = false
  pending[0].resolve({ status: 200, data: { url: png } })
  await tick()
  assert.equal(await running, null)
  assert.equal(await skipped, null)
  assert.equal(pending.length, 4)
  assert.equal(pending[3].payload.path, '/tmp/survivor.png')
  pending[1].reject(new Error('file disappeared'))
  pending[2].resolve({ status: 404 })
  pending[3].resolve({ status: 200, data: { url: png } })
  assert.deepEqual(await Promise.all([second, third, survivor]), [null, null, png])
  installAPI(async () => ({ status: 200, data: { url: png } }))
  assert.equal(await loadAttachmentImage(local('after-cancellation')), png)
})
