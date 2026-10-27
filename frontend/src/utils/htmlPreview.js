export function previewSourceUrl(value) {
  try {
    const url = new URL(value)
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password ? url.href : ''
  } catch { return '' }
}

export function buildPreviewHtml(content, sourceUrl) {
  const doc = new DOMParser().parseFromString(content, 'text/html')
  const base = doc.querySelector('base[href]') || doc.createElement('base')
  const source = previewSourceUrl(sourceUrl)
  let href = source || 'about:blank'
  try { href = previewSourceUrl(new URL(base.getAttribute('href') || href, source || undefined).href) || 'about:blank' } catch { /* Keep a neutral base for invalid sources. */ }
  base.setAttribute('href', href)
  doc.head.prepend(base)
  return '<!DOCTYPE html>\n' + doc.documentElement.outerHTML
}
