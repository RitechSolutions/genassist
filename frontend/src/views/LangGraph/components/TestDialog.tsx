import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog';
import { Button } from '@/components/button';
import { Label } from '@/components/label';
import { Textarea } from '@/components/textarea';
import { Input } from '@/components/input';
import { Play, X } from 'lucide-react';

export interface TestInputField {
  id: string;
  label: string;
  type: 'text' | 'number' | 'boolean' | 'json';
  placeholder?: string;
  required?: boolean;
  defaultValue?: string;
}

interface TestDialogProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  inputFields: TestInputField[];
  onRun: (inputs: Record<string, string>) => Promise<void>;
  output: string;
  isLoading: boolean;
  error: string | null;
}

export const TestDialog: React.FC<TestDialogProps> = ({
  isOpen,
  onClose,
  title,
  description,
  inputFields,
  onRun,
  output,
  isLoading,
  error
}) => {
  const [formData, setFormData] = useState<Record<string, string>>({});

  const handleInputChange = (id: string, value: string) => {
    setFormData(prev => ({
      ...prev,
      [id]: value
    }));
  };

  const handleRun = async () => {
    await onRun(formData);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          {description && (
            <p className="text-sm text-gray-500">{description}</p>
          )}
        </DialogHeader>

        <div className="grid gap-4 py-4">
          <div className="space-y-4">
            {inputFields.map(field => (
              <div key={field.id} className="space-y-2">
                <Label htmlFor={field.id}>
                  {field.label}
                  {field.required && <span className="text-red-500 ml-1">*</span>}
                </Label>
                {field.type === 'json' ? (
                  <Textarea
                    id={field.id}
                    value={formData[field.id] || field.defaultValue || ''}
                    onChange={e => handleInputChange(field.id, e.target.value)}
                    placeholder={field.placeholder}
                    className="h-24 font-mono text-xs"
                  />
                ) : (
                  <Input
                    id={field.id}
                    type={field.type}
                    value={formData[field.id] || field.defaultValue || ''}
                    onChange={e => handleInputChange(field.id, e.target.value)}
                    placeholder={field.placeholder}
                  />
                )}
              </div>
            ))}
          </div>

          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <Label>Output</Label>
              {isLoading && <div className="text-xs text-blue-500">Loading...</div>}
            </div>
            
            {error && (
              <div className="bg-red-50 border border-red-200 text-red-600 p-2 rounded-md text-xs mb-2">
                {error}
              </div>
            )}
            
            <Textarea
              value={output}
              readOnly
              className="h-[200px] font-mono text-xs"
              placeholder="Output will appear here after execution"
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            <X className="h-4 w-4 mr-2" />
            Close
          </Button>
          <Button 
            onClick={handleRun} 
            disabled={isLoading || inputFields.some(field => field.required && !formData[field.id])}
          >
            <Play className="h-4 w-4 mr-2" />
            Run Test
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}; 