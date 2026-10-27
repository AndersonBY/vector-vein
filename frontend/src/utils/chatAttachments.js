import { settingAPI } from '@/api/user'

const imageExtension = /\.(png|jpe?g|gif|webp|bmp)$/i
const scheme = /^[a-z][a-z0-9+.-]*:/i
const windowsDrive = /^[a-z]:[\\/]/i
const networkPath = /^[\\/]{2}/
const basename = path => path.split(/[\\/]/).pop() || ''
const decodeName = name => {
  try { return decodeURIComponent(name) } catch { return name }
}

export function getAttachmentInfo(value, index = 0) {
  const raw = typeof value === 'string' ? value : ''
  const info = { key: `${index}:${raw}`, path: raw, name: basename(raw), kind: 'unsupported', image: false }
  if (!raw.trim() || /[\x00-\x1f\x7f]/.test(raw)) { info.name = ''; return info }
  if (/^https?:/i.test(raw.trim())) {
    try {
      const url = new URL(raw)
      if (!['http:', 'https:'].includes(url.protocol)) return info
      info.kind = 'remote'
      info.name = decodeName(url.pathname.split('/').pop() || '')
    } catch { return info }
  } else if (/^file:\/\//i.test(raw.trim())) {
    try {
      const url = new URL(raw)
      if (url.hostname && url.hostname !== 'localhost') return info
      let path = decodeURIComponent(url.pathname)
      if (/^\/[a-z]:[\\/]/i.test(path)) path = path.slice(1)
      if (!path || networkPath.test(path) || /[\x00-\x1f\x7f]/.test(path)) return info
      info.path = path
      info.name = basename(path)
      info.kind = 'local'
    } catch { return info }
  } else if (!networkPath.test(raw) && (!scheme.test(raw.trim()) || windowsDrive.test(raw))) {
    info.kind = 'local'
  }
  info.image = info.kind !== 'unsupported' && imageExtension.test(info.name)
  return info
}

const queue = []
let activeReads = 0
const imageDataUrl = /^data:image\/(?:png|jpeg|gif|webp|bmp);base64,[a-z0-9+/]+={0,2}$/i

function drainQueue() {
  while (activeReads < 3 && queue.length) {
    const job = queue.shift()
    if (!job.current()) { job.resolve(null); continue }
    activeReads++
    ;(async () => {
      let result = null
      try {
        const response = await settingAPI('attachment_image', { path: job.path, thumbnail: job.thumbnail })
        const url = response?.data?.url
        if (job.current() && response?.status === 200 && typeof url === 'string' && imageDataUrl.test(url)) result = url
      } catch { /* Missing files and failed previews keep the attachment available as a file. */ }
      finally {
        activeReads--
        job.resolve(result)
        drainQueue()
      }
    })()
  }
}

export async function loadAttachmentImage(info, thumbnail = true, isCurrent = () => true) {
  const current = () => {
    try { return Boolean(isCurrent()) } catch { return false }
  }
  if (!current() || !info?.image) return null
  const parsed = getAttachmentInfo(info.path)
  if (!parsed.image || parsed.kind !== info.kind) return null
  if (info.kind === 'remote') return current() ? info.path : null
  if (info.kind !== 'local') return null
  return new Promise(resolve => {
    const job = { path: info.path, thumbnail, current, resolve }
    if (thumbnail) queue.push(job)
    else queue.unshift(job)
    drainQueue()
  })
}
