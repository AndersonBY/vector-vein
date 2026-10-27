import { getTimelineNodeLabel } from './workflowTimeline.js'

const text = value => typeof value === 'string' ? value : ''
const coordinate = value => typeof value === 'number' && Number.isFinite(value) ? value : 0

// Project only structural metadata: editable templates and their values never enter the canvas store.
export function getWorkflowPreview(workflow, t = key => key, te = () => false) {
  const rawNodes = Array.isArray(workflow?.nodes) ? workflow.nodes : []
  const rawEdges = Array.isArray(workflow?.edges) ? workflow.edges : []
  const originals = new Map()
  const nodes = []
  for (const node of rawNodes) {
    if (!node || !text(node.id) || originals.has(node.id)) continue
    originals.set(node.id, node)
    nodes.push({
      id: node.id,
      type: 'preview',
      position: { x: coordinate(node.position?.x), y: coordinate(node.position?.y) },
      draggable: false, connectable: false, selectable: false, focusable: false,
      data: {
        title: getTimelineNodeLabel({ id: node.id, type: text(node.type), category: text(node.category),
          title: text(node.data?.title), taskName: text(node.data?.task_name) }, t, te),
        ignored: Boolean(node.ignored),
        inputs: [], outputs: [],
      },
    })
  }
  const projected = new Map(nodes.map(node => [node.id, node]))
  const edges = []
  const edgeIds = new Set()
  const addPort = (nodeId, handle, direction) => {
    const ports = projected.get(nodeId).data[direction]
    if (ports.some(port => port.id === handle)) return
    const node = originals.get(nodeId)
    const template = node.data?.template
    const entry = template && typeof template === 'object' ? Object.entries(template).find(([key, field]) =>
      field && typeof field === 'object' && [key, field.id, field.name].includes(handle)) : null
    const [key, field] = entry || []
    const labelKey = `components.nodes.${text(node.category)}.${text(node.type)}.${key}`
    const label = entry && te(labelKey) ? t(labelKey)
      : text(field?.display_name) || text(field?.name) || text(key) || handle || '—'
    ports.push({ id: handle, label })
  }
  for (const [index, edge] of rawEdges.entries()) {
    if (!edge || !projected.has(edge.source) || !projected.has(edge.target)) continue
    if (edge.sourceHandle != null && typeof edge.sourceHandle !== 'string'
      || edge.targetHandle != null && typeof edge.targetHandle !== 'string') continue
    let id = text(edge.id) || `preview-edge-${index}`
    while (edgeIds.has(id)) id += '-copy'
    edgeIds.add(id)
    const sourceHandle = edge.sourceHandle || null
    const targetHandle = edge.targetHandle || null
    addPort(edge.source, sourceHandle, 'outputs')
    addPort(edge.target, targetHandle, 'inputs')
    const ignored = Boolean(edge.ignored || originals.get(edge.source).ignored || originals.get(edge.target).ignored)
    edges.push({
      id, source: edge.source, target: edge.target, sourceHandle, targetHandle,
      type: 'smoothstep', selectable: false, focusable: false, updatable: false,
      markerEnd: { type: 'arrowclosed', color: 'var(--preview-edge, #666)' },
      style: { stroke: 'var(--preview-edge, #666)', ...(ignored ? { opacity: 0.4, strokeDasharray: '5 4' } : {}) },
    })
  }
  return { nodes, edges }
}
