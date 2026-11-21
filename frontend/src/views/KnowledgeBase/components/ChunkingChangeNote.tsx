import React from 'react';
import { Info } from 'lucide-react';
import { Alert, AlertDescription } from '@/components/alert';
import { CHUNKING_CHANGE_NOTE } from '../utils/chunkingChange';

/** Tells when a changed chunking strategy starts to apply. */
const ChunkingChangeNote: React.FC = () => (
  <Alert className="mt-4 ml-4 w-auto">
    <Info className="h-4 w-4" />
    <AlertDescription>{CHUNKING_CHANGE_NOTE}</AlertDescription>
  </Alert>
);

export default ChunkingChangeNote;
