import React from 'react';
import { Switch } from '@/components/switch';

export interface ArticleOption {
  key: string;
  label: string;
  hint: string;
}

interface ArticlesToCopyProps {
  options: ArticleOption[];
  extraMetadata?: Record<string, unknown>;
  onChange: (key: string, value: boolean) => void;
}

const ArticlesToCopy: React.FC<ArticlesToCopyProps> = ({ options, extraMetadata, onChange }) => (
  <div className="rounded-lg border bg-card dark:bg-zinc-900 p-4">
    <div className="text-sm font-medium text-foreground mb-3">Articles to copy</div>
    <div className="flex flex-col gap-4">
      {options.map(({ key, label, hint }) => (
        <div key={key} className="flex items-center justify-between">
          <div className="flex-1 pr-4">
            <label htmlFor={key} className="text-sm text-foreground">
              {label}
            </label>
            <p className="text-sm text-muted-foreground mt-0.5">{hint}</p>
          </div>
          <Switch
            id={key}
            checked={Boolean(extraMetadata?.[key])}
            onCheckedChange={(checked) => onChange(key, checked)}
          />
        </div>
      ))}
    </div>
  </div>
);

export default ArticlesToCopy;
