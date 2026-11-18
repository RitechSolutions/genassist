import React from 'react';
import { Badge } from '@/components/badge';
import { knowledgeBaseStatusLabel, syncStatusBadgeVariant } from '../utils/syncStatus';

interface KnowledgeBaseStatusBadgeProps {
  status?: string | null;
}

/** Whether a knowledge base is ready to be searched: Indexing, Ready or Failed. */
const KnowledgeBaseStatusBadge: React.FC<KnowledgeBaseStatusBadgeProps> = ({ status }) => {
  if (!status) return null;

  return <Badge variant={syncStatusBadgeVariant(status)}>{knowledgeBaseStatusLabel(status)}</Badge>;
};

export default KnowledgeBaseStatusBadge;
