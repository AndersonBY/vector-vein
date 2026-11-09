export function folderOptions(folders, excludedId = null) {
  const visit = (nodes, prefix = '') => nodes.flatMap(folder => {
    if (folder.id === excludedId) return []
    const label = prefix ? `${prefix} / ${folder.name}` : folder.name
    return [{ value: folder.id, label }, ...visit(folder.children || [], label)]
  })
  return visit(folders)
}

export function knowledgeOptions(bases, selected = [], missingLabel = id => id) {
  const options = bases.map(base => ({ value: base.id, label: base.name }))
  for (const id of new Set(selected)) {
    if (!bases.some(base => base.id === id)) options.push({ value: id, label: missingLabel(id), disabled: true })
  }
  return options
}

export function validChunkSettings(size, overlap) {
  return Number.isInteger(size) && size >= 64 && size <= 16000 && Number.isInteger(overlap) && overlap >= 0 && overlap < size
}

export function indexingErrorKey(code) {
  const messages = {
    embedding_unavailable: 'embedding_unavailable',
    embedding_failed: 'embedding_failed',
    invalid_model: 'embedding_unavailable',
    invalid_embedding: 'invalid_embedding',
    invalid_dimensions: 'embedding_dimensions_failed',
    dimension_mismatch: 'embedding_dimensions_failed',
    extraction_failed: 'extraction_failed',
    empty_document: 'empty_document',
    text_too_large: 'text_too_large',
    file_too_large: 'file_too_large',
    unsupported_type: 'unsupported_type',
    original_unavailable: 'original_unavailable',
    file_missing: 'file_missing',
    unsafe_path: 'unsafe_path',
    indexing_failed: 'index_failed',
  }
  return `knowledgeBase.${messages[code] || 'index_failed'}`
}
