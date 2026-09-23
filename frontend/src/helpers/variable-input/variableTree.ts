/**
 * Turns a node's available data into the variable tree that every field's "{{"
 * popup and picker browse. Paths keep the raw node ids the runtime resolves;
 * only the breadcrumb shown to the user swaps them for node names.
 */

import {
  buildArrayItemPath,
  formatVariableReference,
  isPlainObject,
} from "./variableReference"

type VariableKind = "object" | "array" | "value"

/** A variable, plus the variables nested underneath it. */
export interface VariableNode {
  /** Raw runtime path, e.g. "<node-uuid>.prediction[0].label" */
  path: string
  /** Path wrapped for insertion, e.g. "{{<node-uuid>.prediction[0].label}}" */
  reference: string
  /** Last segment, shown as the option title */
  label: string
  /** Readable full path with node ids swapped for node names */
  breadcrumb: string
  /** Short rendering of the current value */
  preview: string
  kind: VariableKind
  /** Lowercased haystack used for filtering */
  search: string
  children: VariableNode[]
}

/** One rendered line of the tree, already resolved for indent and expansion. */
export interface VariableRow {
  node: VariableNode
  depth: number
  expandable: boolean
  expanded: boolean
}

export interface VariableNodeNames {
  [nodeId: string]: { name: string; type: string }
}

const UUID_PATTERN =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

const MAX_DEPTH = 6
const MAX_OPTIONS = 500
const MAX_ROWS = 300
const PREVIEW_LIMIT = 48

function previewOf(value: unknown): string {
  if (value === null) return "null"
  if (value === undefined) return "undefined"
  if (Array.isArray(value)) return `Array[${value.length}]`
  if (value instanceof Date) return value.toISOString()
  if (typeof value === "object") {
    return `Object{${Object.keys(value as object).length}}`
  }
  if (typeof value === "string") {
    return value.length > PREVIEW_LIMIT
      ? `"${value.slice(0, PREVIEW_LIMIT)}…"`
      : `"${value}"`
  }
  return String(value)
}

function kindOf(value: unknown): VariableKind {
  if (Array.isArray(value)) return "array"
  if (isPlainObject(value)) return "object"
  return "value"
}

/** Node ids are unreadable in a flat list, so show the node's name instead. */
function displayKey(key: string, nodeNames: VariableNodeNames): string {
  if (!UUID_PATTERN.test(key)) return key
  return nodeNames[key]?.name || key
}

/** Builds the same hierarchy the variables panel shows, ready to expand. */
export function buildVariableTree(
  data: unknown,
  nodeNames: VariableNodeNames = {}
): VariableNode[] {
  if (!isPlainObject(data)) return []

  let budget = MAX_OPTIONS

  const visit = (
    label: string,
    breadcrumb: string,
    value: unknown,
    path: string,
    depth: number
  ): VariableNode | null => {
    if (budget <= 0) return null
    budget -= 1

    const node: VariableNode = {
      path,
      reference: formatVariableReference(path),
      label,
      breadcrumb,
      preview: previewOf(value),
      kind: kindOf(value),
      search: `${breadcrumb} ${path}`.toLowerCase(),
      children: [],
    }

    if (depth >= MAX_DEPTH) return node

    if (Array.isArray(value)) {
      value.forEach((item, index) => {
        const child = visit(
          `[${index}]`,
          `${breadcrumb}[${index}]`,
          item,
          buildArrayItemPath(path, index),
          depth + 1
        )
        if (child) node.children.push(child)
      })
      return node
    }

    if (isPlainObject(value)) {
      Object.entries(value).forEach(([key, raw]) => {
        const shown = displayKey(key, nodeNames)
        const child = visit(
          shown,
          `${breadcrumb}.${shown}`,
          raw,
          `${path}.${key}`,
          depth + 1
        )
        if (child) node.children.push(child)
      })
    }

    return node
  }

  const roots: VariableNode[] = []
  Object.entries(data).forEach(([key, value]) => {
    const shown = displayKey(key, nodeNames)
    const node = visit(shown, shown, value, key, 0)
    if (node) roots.push(node)
  })

  return roots
}

function queryTerms(query: string): string[] {
  return query.trim().toLowerCase().split(/[\s.]+/).filter(Boolean)
}

function nodeMatches(node: VariableNode, terms: string[]): boolean {
  return terms.every((term) => node.search.includes(term))
}

/** Prune to nodes that match, keeping the ancestors needed to reach them. */
function keepMatching(nodes: VariableNode[], terms: string[]): VariableNode[] {
  const kept: VariableNode[] = []

  for (const node of nodes) {
    if (nodeMatches(node, terms)) {
      kept.push(node)
      continue
    }
    const children = keepMatching(node.children, terms)
    if (children.length > 0) kept.push({ ...node, children })
  }

  return kept
}

/**
 * Resolves the tree into the lines to draw. Without a query, only expanded
 * branches are walked. With one, non-matching branches are dropped and the
 * ancestors of a deep hit open automatically so it can be seen.
 */
export function getVisibleRows(
  tree: VariableNode[],
  expanded: ReadonlySet<string>,
  query = ""
): VariableRow[] {
  const terms = queryTerms(query)
  const rows: VariableRow[] = []

  const walk = (nodes: VariableNode[], depth: number) => {
    for (const node of nodes) {
      if (rows.length >= MAX_ROWS) return

      let children = node.children
      let autoExpanded = false

      if (terms.length > 0 && !nodeMatches(node, terms)) {
        children = keepMatching(node.children, terms)
        if (children.length === 0) continue
        // Only opened to reveal a hit further down
        autoExpanded = true
      }

      const expandable = children.length > 0
      const isExpanded = expandable && (autoExpanded || expanded.has(node.path))

      rows.push({ node, depth, expandable, expanded: isExpanded })
      if (isExpanded) walk(children, depth + 1)
    }
  }

  walk(tree, 0)
  return rows
}
