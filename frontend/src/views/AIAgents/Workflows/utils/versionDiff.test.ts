import { describe, it, expect } from 'vitest';
import { Edge, Node } from 'reactflow';
import { Workflow } from '@/interfaces/workflow.interface';
import nodeRegistry from '../registry/nodeRegistry';
import { NodeData, NodeTypeDefinition } from '../types/nodes';
import { computeWorkflowDiff, diffEdges, diffNodeData, getNodeLabel, normalizeForDiff } from './versionDiff';

// --- Fixtures -------------------------------------------------------------------------------

const makeNode = (id: string, overrides: Partial<Node> = {}, data: Record<string, unknown> = {}): Node => ({
  id,
  type: 'llmNode',
  position: { x: 0, y: 0 },
  data: { name: id, ...data },
  ...overrides,
});

const makeEdge = (id: string, source: string, target: string, overrides: Partial<Edge> = {}): Edge => ({
  id,
  source,
  target,
  ...overrides,
});

const makeWorkflow = (nodes: Node[], edges: Edge[] = [], overrides: Partial<Workflow> = {}): Workflow => ({
  id: 'wf',
  name: 'Workflow',
  version: '1.0',
  nodes,
  edges,
  ...overrides,
});

// --- normalizeForDiff -----------------------------------------------------------------------

describe('normalizeForDiff', () => {
  it('strips workflow timestamps and cosmetic node/edge fields', () => {
    const wf = makeWorkflow(
      [
        makeNode('a', {
          selected: true,
          dragging: true,
          width: 200,
          height: 100,
          position: { x: 42, y: 99 },
          positionAbsolute: { x: 42, y: 99 },
        }),
      ],
      [makeEdge('e1', 'a', 'b', { selected: true, className: 'highlight' })],
      { created_at: '2026-01-01', updated_at: '2026-02-02' }
    );

    const norm = normalizeForDiff(wf);
    const node = norm.nodes[0] as Node & { positionAbsolute?: unknown };
    expect(node.selected).toBeUndefined();
    expect(node.dragging).toBeUndefined();
    expect(node.width).toBeUndefined();
    expect(node.height).toBeUndefined();
    expect(node.position).toBeUndefined();
    expect(node.positionAbsolute).toBeUndefined();

    const edge = norm.edges[0] as Edge & { className?: string };
    expect(edge.selected).toBeUndefined();
    expect(edge.className).toBeUndefined();
  });

  it('strips the injected data.updateNodeData function', () => {
    const wf = makeWorkflow([makeNode('a', {}, { updateNodeData: () => undefined, model: 'gpt-4' })]);
    const norm = normalizeForDiff(wf);
    const data = norm.nodes[0].data as Record<string, unknown>;
    expect(data.updateNodeData).toBeUndefined();
    expect(data.model).toBe('gpt-4');
  });

  it('handles empty / missing node & edge arrays', () => {
    const norm = normalizeForDiff({ name: 'x', version: '1.0' } as Workflow);
    expect(norm.nodes).toEqual([]);
    expect(norm.edges).toEqual([]);
  });
});

// --- getNodeLabel ---------------------------------------------------------------------------

describe('getNodeLabel', () => {
  it('prefers data.name', () => {
    expect(getNodeLabel(makeNode('a', {}, { name: 'My LLM' }))).toBe('My LLM');
  });

  it('falls back to the registry label for the node type', () => {
    const type = '__diffTestNode__';
    nodeRegistry.register({
      type,
      label: 'Diff Test Node',
      category: 'test',
      defaultData: {},
    } as unknown as NodeTypeDefinition<NodeData>);
    const node = { id: 'n1', type, position: { x: 0, y: 0 }, data: {} } as Node;
    expect(getNodeLabel(node)).toBe('Diff Test Node');
  });

  it('falls back to the type when no name/registry label', () => {
    const node = { id: 'n1', type: 'unknownType', position: { x: 0, y: 0 }, data: {} } as Node;
    expect(getNodeLabel(node)).toBe('unknownType');
  });

  it('falls back to the id when there is no type', () => {
    const node = { id: 'n1', position: { x: 0, y: 0 }, data: {} } as unknown as Node;
    expect(getNodeLabel(node)).toBe('n1');
  });
});

// --- diffNodeData ---------------------------------------------------------------------------

describe('diffNodeData', () => {
  it('returns an empty list when data is identical', () => {
    const a = makeNode('a', {}, { model: 'gpt-4', temp: 0.5 });
    const b = makeNode('a', {}, { model: 'gpt-4', temp: 0.5 });
    expect(diffNodeData(a, b)).toEqual([]);
  });

  it('reports a scalar field change with before/after', () => {
    const a = makeNode('a', {}, { model: 'gpt-4' });
    const b = makeNode('a', {}, { model: 'gpt-4o' });
    const changes = diffNodeData(a, b);
    expect(changes).toContainEqual({ key: 'model', before: 'gpt-4', after: 'gpt-4o' });
  });

  it('detects added and removed fields', () => {
    const a = makeNode('a', {}, { onlyBase: 1 });
    const b = makeNode('a', {}, { onlyTarget: 2 });
    const changes = diffNodeData(a, b);
    expect(changes).toContainEqual({ key: 'onlyBase', before: 1, after: undefined });
    expect(changes).toContainEqual({ key: 'onlyTarget', before: undefined, after: 2 });
  });

  it('detects nested object field changes', () => {
    const a = makeNode('a', {}, { config: { retries: 1, nested: { x: 1 } } });
    const b = makeNode('a', {}, { config: { retries: 1, nested: { x: 2 } } });
    const changes = diffNodeData(a, b);
    expect(changes).toHaveLength(1);
    expect(changes[0].key).toBe('config');
    expect(changes[0].before).toEqual({ retries: 1, nested: { x: 1 } });
    expect(changes[0].after).toEqual({ retries: 1, nested: { x: 2 } });
  });

  it('does not report a change for deeply-equal nested objects', () => {
    const a = makeNode('a', {}, { config: { list: [1, 2, 3] } });
    const b = makeNode('a', {}, { config: { list: [1, 2, 3] } });
    expect(diffNodeData(a, b)).toEqual([]);
  });

  it('synthesizes a `type` change when the node type differs', () => {
    const a = makeNode('a', { type: 'llmNode' });
    const b = makeNode('a', { type: 'toolNode' });
    const changes = diffNodeData(a, b);
    expect(changes).toContainEqual({ key: 'type', before: 'llmNode', after: 'toolNode' });
  });
});

// --- diffEdges ------------------------------------------------------------------------------

describe('diffEdges', () => {
  it('classifies added and removed connections with node labels', () => {
    const base = makeWorkflow(
      [makeNode('a', {}, { name: 'Alpha' }), makeNode('b', {}, { name: 'Beta' })],
      [makeEdge('e1', 'a', 'b')]
    );
    const target = makeWorkflow(
      [makeNode('a', {}, { name: 'Alpha' }), makeNode('c', {}, { name: 'Gamma' })],
      [makeEdge('e2', 'a', 'c')]
    );

    const diffs = diffEdges(base, target);
    const added = diffs.find((d) => d.status === 'added');
    const removed = diffs.find((d) => d.status === 'removed');

    expect(added).toMatchObject({ sourceLabel: 'Alpha', targetLabel: 'Gamma' });
    expect(removed).toMatchObject({ sourceLabel: 'Alpha', targetLabel: 'Beta' });
  });

  it('treats an edge with the same connection identity (different id) as unchanged', () => {
    const base = makeWorkflow([makeNode('a'), makeNode('b')], [makeEdge('e1', 'a', 'b')]);
    const target = makeWorkflow([makeNode('a'), makeNode('b')], [makeEdge('e999', 'a', 'b')]);
    expect(diffEdges(base, target)).toEqual([]);
  });

  it('distinguishes edges by handle', () => {
    const base = makeWorkflow([makeNode('a'), makeNode('b')], [makeEdge('e1', 'a', 'b', { sourceHandle: 'out1' })]);
    const target = makeWorkflow([makeNode('a'), makeNode('b')], [makeEdge('e1', 'a', 'b', { sourceHandle: 'out2' })]);
    const diffs = diffEdges(base, target);
    expect(diffs).toHaveLength(2);
    expect(diffs.filter((d) => d.status === 'added')).toHaveLength(1);
    expect(diffs.filter((d) => d.status === 'removed')).toHaveLength(1);
  });
});

// --- computeWorkflowDiff --------------------------------------------------------------------

describe('computeWorkflowDiff', () => {
  it('classifies added / removed / modified / unchanged and counts them', () => {
    const base = makeWorkflow([
      makeNode('keep', {}, { name: 'Keep', model: 'gpt-4' }),
      makeNode('mod', {}, { name: 'Mod', model: 'gpt-4' }),
      makeNode('gone', {}, { name: 'Gone' }),
    ]);
    const target = makeWorkflow([
      makeNode('keep', {}, { name: 'Keep', model: 'gpt-4' }),
      makeNode('mod', {}, { name: 'Mod', model: 'gpt-4o' }),
      makeNode('new', {}, { name: 'New' }),
    ]);

    const diff = computeWorkflowDiff(base, target);
    expect(diff.summary).toEqual({ added: 1, removed: 1, modified: 1, unchanged: 1 });

    const byId = Object.fromEntries(diff.nodes.map((n) => [n.id, n]));
    expect(byId.new.status).toBe('added');
    expect(byId.gone.status).toBe('removed');
    expect(byId.mod.status).toBe('modified');
    expect(byId.keep.status).toBe('unchanged');
    expect(byId.mod.fieldChanges).toContainEqual({ key: 'model', before: 'gpt-4', after: 'gpt-4o' });
    expect(byId.keep.fieldChanges).toEqual([]);
  });

  it('reports a node that only moved as unchanged (position is cosmetic)', () => {
    const base = makeWorkflow([makeNode('a', { position: { x: 0, y: 0 } }, { model: 'gpt-4' })]);
    const target = makeWorkflow([makeNode('a', { position: { x: 500, y: 300 } }, { model: 'gpt-4' })]);
    const diff = computeWorkflowDiff(base, target);
    expect(diff.summary).toEqual({ added: 0, removed: 0, modified: 0, unchanged: 1 });
    expect(diff.nodes[0].status).toBe('unchanged');
  });

  it('ignores cosmetic selection/drag/size differences', () => {
    const base = makeWorkflow([
      makeNode('a', { selected: false, dragging: false, width: 100, height: 50 }, { model: 'gpt-4' }),
    ]);
    const target = makeWorkflow([
      makeNode('a', { selected: true, dragging: true, width: 999, height: 999 }, { model: 'gpt-4' }),
    ]);
    const diff = computeWorkflowDiff(base, target);
    expect(diff.nodes[0].status).toBe('unchanged');
  });

  it('returns an all-unchanged, edge-free diff for identical workflows', () => {
    const nodes = [makeNode('a', {}, { model: 'gpt-4' }), makeNode('b')];
    const edges = [makeEdge('e1', 'a', 'b')];
    const diff = computeWorkflowDiff(makeWorkflow(nodes, edges), makeWorkflow(nodes, edges));
    expect(diff.summary).toEqual({ added: 0, removed: 0, modified: 0, unchanged: 2 });
    expect(diff.edges).toEqual([]);
  });

  it('includes added/removed edges in the diff result', () => {
    const base = makeWorkflow([makeNode('a'), makeNode('b')], [makeEdge('e1', 'a', 'b')]);
    const target = makeWorkflow(
      [makeNode('a'), makeNode('b'), makeNode('c')],
      [makeEdge('e1', 'a', 'b'), makeEdge('e2', 'b', 'c')]
    );
    const diff = computeWorkflowDiff(base, target);
    expect(diff.edges).toHaveLength(1);
    expect(diff.edges[0]).toMatchObject({ status: 'added' });
  });

  it('preserves the original (un-normalized) base/target for display', () => {
    const base = makeWorkflow([makeNode('a')], [], {
      version: '1.0',
      created_at: '2026-01-01',
    });
    const target = makeWorkflow([makeNode('a')], [], {
      version: '2.0',
      created_at: '2026-02-01',
    });
    const diff = computeWorkflowDiff(base, target);
    expect(diff.base.version).toBe('1.0');
    expect(diff.target.version).toBe('2.0');
    expect(diff.base.created_at).toBe('2026-01-01');
  });

  it('uses the human-readable label for node diff entries', () => {
    const base = makeWorkflow([]);
    const target = makeWorkflow([makeNode('a', {}, { name: 'Greeter' })]);
    const diff = computeWorkflowDiff(base, target);
    expect(diff.nodes[0].label).toBe('Greeter');
    expect(diff.nodes[0].status).toBe('added');
  });
});
