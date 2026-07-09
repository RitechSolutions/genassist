import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ArrowRight, Loader2, AlertTriangle, RefreshCw, List, Network } from 'lucide-react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/tabs';
import { Button } from '@/components/button';
import { cn } from '@/helpers/utils';
import { Workflow } from '@/interfaces/workflow.interface';
import { getWorkflowById } from '@/services/workflows';
import { computeWorkflowDiff } from '../../utils/versionDiff';
import DiffListView from './DiffListView';
import DiffGraphView from './DiffGraphView';

/**
 * Host dialog for the Workflow Version Diff Checker (spec FR-1/FR-2/FR-9/FR-10/FR-11/FR-13). Shows
 * which side is base (older) vs target (newer), and switches between the grouped-list and
 * side-by-side graph presentations via tabs. The two versions may be passed as full `Workflow`
 * objects (already loaded by the panel) or resolved on demand via `getWorkflowById`, with loading
 * and error+retry states. Strictly read-only: closing returns to the panel unchanged.
 */
export interface VersionDiffDialogProps {
  open: boolean;
  onClose: () => void;
  /** The older version (base). Full object preferred; if it lacks `nodes` it is fetched by id. */
  base: Workflow;
  /** The newer version (target). Full object preferred; if it lacks `nodes` it is fetched by id. */
  target: Workflow;
}

const hasGraph = (workflow: Workflow | undefined): boolean => !!workflow && Array.isArray(workflow.nodes);

const VersionDiffDialog: React.FC<VersionDiffDialogProps> = ({ open, onClose, base, target }) => {
  const [resolvedBase, setResolvedBase] = useState<Workflow | undefined>();
  const [resolvedTarget, setResolvedTarget] = useState<Workflow | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadVersions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [nextBase, nextTarget] = await Promise.all([
        hasGraph(base) ? Promise.resolve(base) : getWorkflowById(base.id ?? ''),
        hasGraph(target) ? Promise.resolve(target) : getWorkflowById(target.id ?? ''),
      ]);
      setResolvedBase(nextBase);
      setResolvedTarget(nextTarget);
    } catch {
      setError('Failed to load one or both versions. Please try again.');
    } finally {
      setLoading(false);
    }
  }, [base, target]);

  useEffect(() => {
    if (open) {
      loadVersions();
    } else {
      setResolvedBase(undefined);
      setResolvedTarget(undefined);
      setError(null);
    }
  }, [open, loadVersions]);

  const diff = useMemo(() => {
    if (!resolvedBase || !resolvedTarget) return null;
    return computeWorkflowDiff(resolvedBase, resolvedTarget);
  }, [resolvedBase, resolvedTarget]);

  const versionChip = (workflow: Workflow, side: 'base' | 'target') => {
    const isTarget = side === 'target';
    return (
      <span
        className={cn(
          'inline-flex min-w-0 items-center gap-2 rounded-lg border px-2.5 py-1.5',
          isTarget ? 'border-brand-600/25 bg-brand-50' : 'border-slate-200 bg-slate-50'
        )}
      >
        <span
          className={cn(
            'shrink-0 rounded px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider',
            isTarget ? 'bg-brand-600/10 text-brand-600' : 'bg-slate-200/70 text-slate-500'
          )}
        >
          {isTarget ? 'Target · newer' : 'Base · older'}
        </span>
        <span className="truncate text-sm font-medium text-slate-800" title={workflow.name}>
          {workflow.name}
        </span>
        <span
          className={cn(
            'shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold tabular-nums',
            isTarget ? 'border-brand-600/25 bg-white text-brand-600' : 'border-slate-200 bg-white text-slate-500'
          )}
        >
          v{workflow.version}
        </span>
      </span>
    );
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="flex h-[85vh] max-w-5xl flex-col gap-0 sm:max-w-5xl">
        <DialogHeader>
          <DialogTitle>Compare versions</DialogTitle>
          <DialogDescription>
            Read-only comparison of two saved versions — added, removed, and modified nodes and connections.
          </DialogDescription>
        </DialogHeader>

        {/* Base vs target identity (FR-2) */}
        <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 py-3">
          {versionChip(base, 'base')}
          <ArrowRight className="h-4 w-4 shrink-0 text-slate-400" aria-hidden="true" />
          {versionChip(target, 'target')}
        </div>

        {loading && (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 text-sm text-slate-500">
            <Loader2 className="h-6 w-6 animate-spin text-brand-600" aria-hidden="true" />
            Loading versions…
          </div>
        )}

        {!loading && error && (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 text-center" role="alert">
            <span className="flex h-11 w-11 items-center justify-center rounded-full bg-rose-50 ring-1 ring-rose-100">
              <AlertTriangle className="h-5 w-5 text-rose-500" aria-hidden="true" />
            </span>
            <p className="text-sm text-slate-700">{error}</p>
            <Button variant="outline" size="sm" onClick={loadVersions} className="gap-1.5">
              <RefreshCw className="h-4 w-4" />
              Retry
            </Button>
          </div>
        )}

        {!loading && !error && diff && (
          <Tabs defaultValue="list" className="flex min-h-0 flex-1 flex-col pt-3">
            <TabsList className="w-fit">
              <TabsTrigger value="list" className="gap-1.5">
                <List className="h-4 w-4" aria-hidden="true" />
                List
              </TabsTrigger>
              <TabsTrigger value="graph" className="gap-1.5">
                <Network className="h-4 w-4" aria-hidden="true" />
                Graph
              </TabsTrigger>
            </TabsList>
            <TabsContent value="list" className="min-h-0 flex-1 pt-3 data-[state=inactive]:hidden">
              <DiffListView diff={diff} />
            </TabsContent>
            <TabsContent value="graph" className="min-h-0 flex-1 pt-3 data-[state=inactive]:hidden">
              <DiffGraphView diff={diff} />
            </TabsContent>
          </Tabs>
        )}
      </DialogContent>
    </Dialog>
  );
};

export default VersionDiffDialog;
