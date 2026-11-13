import React from 'react';
import { cn } from '@/helpers/utils';
import { isSyncErrorStatus } from '../utils/syncStatus';
import KnowledgeBaseStatusBadge from './KnowledgeBaseStatusBadge';

interface KnowledgeBaseIndexingStatusProps {
  status?: string | null;
  details?: string | null;
}

/** How the indexing after the last save went, with the reason when documents were left out. */
const KnowledgeBaseIndexingStatus: React.FC<KnowledgeBaseIndexingStatusProps> = ({ status, details }) => {
  if (!status) return null;

  const detailsTone = isSyncErrorStatus(status) ? 'text-destructive' : 'text-muted-foreground';

  return (
    <div>
      <div className="mb-1">Status</div>
      <div className="flex flex-wrap items-center gap-2">
        <KnowledgeBaseStatusBadge status={status} />
        {details && <p className={cn('whitespace-pre-wrap break-words text-sm', detailsTone)}>{details}</p>}
      </div>
    </div>
  );
};

export default KnowledgeBaseIndexingStatus;
