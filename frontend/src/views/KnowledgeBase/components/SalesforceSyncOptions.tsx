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
        <div className="text-sm font-medium text-foreground mb-3">Articles to copy</div>
        <div className="flex items-center justify-between">
          <div className="flex-1 pr-4">
            <label htmlFor="include_restricted_articles" className="text-sm text-foreground">
              Include restricted articles
            </label>
            <p className="text-sm text-muted-foreground mt-0.5">Not visible in the Public Knowledge Base.</p>
          </div>
          <Switch
            id="include_restricted_articles"
            checked={includeRestricted}
            onCheckedChange={(checked) => onChange('include_restricted_articles', checked)}
          />
        </div>
      </div>
    </div>
  );
};

export default SalesforceSyncOptions;
