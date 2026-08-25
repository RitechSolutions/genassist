import { describe, it, expect } from 'vitest';
import {
  buildExecutionViewModel,
  deriveExecutionViewState,
  formatDuration,
} from '@/views/AIAgents/Workflows/utils/executionView';

// A representative nested response mirroring the real backend wire format
// (`response.state.nodeExecutionStatus`, snake_case run-level fields).
const nestedResponse = {
  status: 'success',
  input: 'hi',
  output: 'done',
  state: {
    total_steps: 28,
    current_step: 28,
    execution_start_time: 1_000,
    execution_end_time: 1_900,
    nodeExecutionStatus: {
      start: { name: 'Start', type: 'startNode', status: 'success', startTime: 1_000, endTime: 1_010, time_taken: 10 },
      extractor: { name: 'Extractor', status: 'success', startTime: 1_010, endTime: 1_350, time_taken: 340 },
      normalizer: {
        name: 'Normalizer',
        status: 'failed',
        startTime: 1_350,
        endTime: 1_360,
        time_taken: 10,
        error: 'boom',
      },
    },
  },
};

describe('buildExecutionViewModel', () => {
  it('normalizes status (success -> completed) and reads nested state', () => {
    const m = buildExecutionViewModel(nestedResponse);
    expect(m.totalNodes).toBe(3);
    expect(m.byId.start.status).toBe('completed');
    expect(m.byId.extractor.status).toBe('completed');
    expect(m.byId.normalizer.status).toBe('failed');
    expect(m.totalSteps).toBe(28);
    expect(m.currentStep).toBe(28);
  });

  it('derives status counts', () => {
    const m = buildExecutionViewModel(nestedResponse);
    expect(m.counts.completed).toBe(2);
    expect(m.counts.failed).toBe(1);
    expect(m.counts.running).toBe(0);
  });

  it('maps time_taken to durationMs and picks the slowest node', () => {
    const m = buildExecutionViewModel(nestedResponse);
    expect(m.byId.extractor.durationMs).toBe(340);
    expect(m.slowestNodeId).toBe('extractor');
  });

  it('falls back to endTime-startTime when time_taken is absent', () => {
    const m = buildExecutionViewModel({
      state: {
        nodeExecutionStatus: {
          a: { status: 'success', startTime: 100, endTime: 250 },
        },
      },
    });
    expect(m.byId.a.durationMs).toBe(150);
  });

  it('computes overall duration from run-level times, else the node span', () => {
    expect(buildExecutionViewModel(nestedResponse).overallDurationMs).toBe(900);
    const spanOnly = buildExecutionViewModel({
      state: {
        nodeExecutionStatus: {
          a: { status: 'success', startTime: 100, endTime: 200 },
          b: { status: 'success', startTime: 200, endTime: 500 },
        },
      },
    });
    expect(spanOnly.overallDurationMs).toBe(400);
  });

  it('orders nodes by startTime', () => {
    const m = buildExecutionViewModel(nestedResponse);
    expect(m.nodes.map((n) => n.nodeId)).toEqual(['start', 'extractor', 'normalizer']);
    expect(m.nodes[0].order).toBe(0);
  });

  it('collapses archived re-run keys but keeps legitimate underscore ids', () => {
    const m = buildExecutionViewModel({
      state: {
        nodeExecutionStatus: {
          extractor: { status: 'success', time_taken: 5 },
          extractor_0: { status: 'failed', time_taken: 5 },
          extractor_1: { status: 'failed', time_taken: 5 },
          r2_destmissing: { status: 'success', time_taken: 5 },
        },
      },
    });
    expect(Object.keys(m.byId).sort()).toEqual(['extractor', 'r2_destmissing']);
    expect(m.byId.extractor.status).toBe('completed');
  });

  it('reads from the top level when there is no nested state', () => {
    const m = buildExecutionViewModel({
      total_steps: 2,
      nodeExecutionStatus: { a: { status: 'running', startTime: 1 } },
    });
    expect(m.totalNodes).toBe(1);
    expect(m.byId.a.status).toBe('running');
    expect(m.totalSteps).toBe(2);
  });

  it('uses the workflow node name as a fallback', () => {
    const workflow = {
      name: 'wf',
      nodes: [{ id: 'a', type: 'x', position: { x: 0, y: 0 }, data: { name: 'Node A' } }],
      edges: [],
    } as unknown as Parameters<typeof buildExecutionViewModel>[1];
    const m = buildExecutionViewModel({ state: { nodeExecutionStatus: { a: { status: 'success' } } } }, workflow);
    expect(m.byId.a.name).toBe('Node A');
  });

  it('degrades gracefully on missing / malformed input (never throws)', () => {
    for (const bad of [undefined, null, {}, 42, 'nope', [], { state: null }, { state: { nodeExecutionStatus: 'x' } }]) {
      const m = buildExecutionViewModel(bad as unknown);
      expect(m.totalNodes).toBe(0);
      expect(m.nodes).toEqual([]);
      expect(m.counts.completed).toBe(0);
    }
  });
});

describe('deriveExecutionViewState', () => {
  it('returns loading while testing', () => {
    expect(deriveExecutionViewState(null, true, null)).toBe('loading');
    expect(deriveExecutionViewState({ status: 'success' }, true, null)).toBe('loading');
  });

  it('returns error when an error is present and not testing', () => {
    expect(deriveExecutionViewState(null, false, 'failed')).toBe('error');
  });

  it('returns empty when there is no response', () => {
    expect(deriveExecutionViewState(null, false, null)).toBe('empty');
    expect(deriveExecutionViewState(undefined, false, null)).toBe('empty');
  });

  it('returns data when a response is present', () => {
    expect(deriveExecutionViewState({ status: 'success' }, false, null)).toBe('data');
  });
});

describe('formatDuration', () => {
  it('formats ms, seconds and minutes; guards bad input', () => {
    expect(formatDuration(12)).toBe('12 ms');
    expect(formatDuration(1_340)).toBe('1.34 s');
    expect(formatDuration(123_000)).toBe('2 m 03 s');
    expect(formatDuration(undefined)).toBe('—');
    expect(formatDuration(-5)).toBe('—');
  });
});

const WITHHELD = { requested: true, applied: false };
const APPLIED = { requested: true, applied: true };

const responseWith = (state: Record<string, unknown>) => ({ status: 'success', state });

describe('buildExecutionViewModel — prompt caching', () => {
  it('drops malformed diagnostics rather than half-rendering them', () => {
    const m = buildExecutionViewModel(
      responseWith({
        nodeExecutionStatus: { a: { status: 'success' }, b: { status: 'success' }, c: { status: 'success' } },
        promptCachingDiagnostics: { a: 'yes', b: { requested: 'true', applied: false } },
      })
    );
    expect(m.byId.a.promptCaching).toBeUndefined();
    expect(m.byId.b.promptCaching).toBeUndefined();
    expect(m.byId.c.promptCaching).toBeUndefined();
  });

  it('exposes standalone sub-agent diagnostics without touching counts', () => {
    const withDiagnostics = buildExecutionViewModel(
      responseWith({
        nodeExecutionStatus: { llm: { status: 'success', startTime: 1, endTime: 2 } },
        promptCachingDiagnostics: { child: WITHHELD, grandchild: APPLIED },
      })
    );
    const plain = buildExecutionViewModel(
      responseWith({ nodeExecutionStatus: { llm: { status: 'success', startTime: 1, endTime: 2 } } })
    );

    expect(Object.keys(withDiagnostics.promptCachingDiagnostics).sort()).toEqual(['child', 'grandchild']);
    expect(withDiagnostics.totalNodes).toBe(plain.totalNodes);
    expect(withDiagnostics.counts).toEqual(plain.counts);
    expect(Object.keys(withDiagnostics.byId)).toEqual(['llm']);
  });

  it('keeps every key — the backend never archives entries in this map', () => {
    const m = buildExecutionViewModel(
      responseWith({ nodeExecutionStatus: {}, promptCachingDiagnostics: { step: WITHHELD, step_2: APPLIED } })
    );
    expect(Object.keys(m.promptCachingDiagnostics).sort()).toEqual(['step', 'step_2']);
  });

  it('yields an empty collection for a malformed or absent bag', () => {
    for (const bad of [undefined, {}, responseWith({ promptCachingDiagnostics: 'x' })]) {
      expect(buildExecutionViewModel(bad as unknown).promptCachingDiagnostics).toEqual({});
    }
  });

  it('attaches a diagnostic from the standalone collection to its executed node', () => {
    const m = buildExecutionViewModel(
      responseWith({
        nodeExecutionStatus: { llm: { status: 'success' } },
        promptCachingDiagnostics: { llm: WITHHELD },
      })
    );
    expect(m.byId.llm.promptCaching).toEqual({ requested: true, applied: false });
  });

  it('normalizes observed cache activity and drops non-numeric values', () => {
    const m = buildExecutionViewModel(
      responseWith({
        nodeExecutionStatus: { a: { status: 'success' }, b: { status: 'success' } },
        promptCachingDiagnostics: {
          a: { ...APPLIED, cache_read_tokens: 950, cache_creation_tokens: 0 },
          b: { ...APPLIED, cache_read_tokens: 'lots' },
        },
      })
    );
    expect(m.byId.a.promptCaching).toEqual({
      requested: true,
      applied: true,
      cacheReadTokens: 950,
      cacheCreationTokens: 0,
    });
    expect(m.byId.b.promptCaching).toEqual({ requested: true, applied: true });
  });
});
