import React from 'react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/select';
import { Switch } from '@/components/switch';
import { resolveSalesforceContentFormat } from '../utils/salesforceOptions';

interface SalesforceSyncOptionsProps {
  extraMetadata?: Record<string, unknown>;
  onChange: (key: string, value: unknown) => void;
}

const SalesforceSyncOptions: React.FC<SalesforceSyncOptionsProps> = ({ extraMetadata, onChange }) => {
  const contentFormat = resolveSalesforceContentFormat(extraMetadata);
  const includeRestricted = Boolean(extraMetadata?.include_restricted_articles);

  return (
    <div className="flex flex-col gap-6 mt-6">
      <div>
        <div className="mb-1">Content Format</div>
        <Select value={contentFormat} onValueChange={(value) => onChange('content_format', value)}>
          <SelectTrigger className="w-full">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="text">Plain text</SelectItem>
            <SelectItem value="markdown">Markdown</SelectItem>
            <SelectItem value="html">HTML</SelectItem>
          </SelectContent>
        </Select>
      </div>
      <div className="rounded-lg border bg-card dark:bg-zinc-900 p-4">
        <div className="flex items-center justify-between">
          <div className="flex-1 pr-4">
            <div className="text-sm font-medium text-foreground">Include Restricted Articles</div>
            <p className="text-sm text-muted-foreground mt-1">
              Also index articles not visible in the Public Knowledge Base (internal, customer or partner only).
            </p>
          </div>
          <Switch
            checked={includeRestricted}
            onCheckedChange={(checked) => onChange('include_restricted_articles', checked)}
          />
        </div>
      </div>
    </div>
  );
};

export default SalesforceSyncOptions;
