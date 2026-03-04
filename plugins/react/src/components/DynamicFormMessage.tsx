import React, { useState, CSSProperties } from 'react';

interface FormField {
  name: string;
  type: 'text' | 'number' | 'select' | 'boolean' | 'date';
  label: string;
  required?: boolean;
  placeholder?: string;
  description?: string;
  options?: Array<{ value: string; label: string }>;
}

interface FormSchema {
  message: string;
  fields: FormField[];
  node_id: string;
}

interface DynamicFormMessageProps {
  schema: FormSchema;
  onSubmit: (data: Record<string, unknown>) => void;
  onCancel?: () => void;
  isSubmitting: boolean;
  isSubmitted: boolean;
  primaryColor?: string;
  fontFamily?: string;
  /** "card" = inline chat bubble (default), "footer" = compact footer layout */
  variant?: 'card' | 'footer';
}

const DynamicFormMessage: React.FC<DynamicFormMessageProps> = ({
  schema,
  onSubmit,
  onCancel,
  isSubmitting,
  isSubmitted,
  primaryColor = '#2563eb',
  fontFamily = 'inherit',
  variant = 'card',
}) => {
  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});

  const isFooter = variant === 'footer';
  const allFieldsOptional = schema.fields.every((f) => !f.required);
  const showCancel = !!onCancel && allFieldsOptional && !isSubmitted;

  const handleChange = (name: string, value: unknown) => {
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitted || isSubmitting) return;

    const newErrors: Record<string, string> = {};
    schema.fields.forEach((field) => {
      if (field.required && !formData[field.name] && formData[field.name] !== 0 && formData[field.name] !== false) {
        newErrors[field.name] = 'This field is required';
      }
    });

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    onSubmit(formData);
  };

  // ── Styles (variant-aware) ──

  const containerStyle: CSSProperties = isFooter
    ? { width: '100%' }
    : {
        backgroundColor: '#f9fafb',
        border: '1px solid #e5e7eb',
        borderRadius: '12px',
        padding: '16px',
        maxWidth: '100%',
      };

  const messageStyle: CSSProperties = {
    fontSize: isFooter ? '13px' : '14px',
    color: '#374151',
    marginBottom: isFooter ? '8px' : '12px',
    fontWeight: 500,
    fontFamily,
  };

  const fieldsWrapperStyle: CSSProperties = isFooter
    ? { maxHeight: '200px', overflowY: 'auto', paddingRight: '4px' }
    : {};

  const fieldContainerStyle: CSSProperties = {
    marginBottom: isFooter ? '8px' : '12px',
  };

  const labelStyle: CSSProperties = {
    display: 'block',
    fontSize: isFooter ? '12px' : '13px',
    fontWeight: 600,
    color: '#374151',
    marginBottom: '2px',
    fontFamily,
  };

  const descriptionStyle: CSSProperties = {
    fontSize: '11px',
    color: '#6b7280',
    marginBottom: '3px',
    fontFamily,
  };

  const inputStyle: CSSProperties = {
    width: '100%',
    padding: isFooter ? '6px 10px' : '8px 12px',
    fontSize: isFooter ? '13px' : '14px',
    border: '1px solid #d1d5db',
    borderRadius: '8px',
    outline: 'none',
    boxSizing: 'border-box',
    backgroundColor: isSubmitted ? '#f3f4f6' : '#ffffff',
    fontFamily,
  };

  const selectStyle: CSSProperties = {
    ...inputStyle,
    appearance: 'auto' as const,
  };

  const errorStyle: CSSProperties = {
    fontSize: '12px',
    color: '#ef4444',
    marginTop: '2px',
  };

  const buttonStyle: CSSProperties = {
    width: '100%',
    padding: isFooter ? '9px 16px' : '10px 16px',
    fontSize: isFooter ? '13px' : '14px',
    fontWeight: 600,
    color: '#ffffff',
    backgroundColor: isSubmitted ? '#9ca3af' : primaryColor,
    border: 'none',
    borderRadius: isFooter ? '10px' : '8px',
    cursor: isSubmitted || isSubmitting ? 'not-allowed' : 'pointer',
    opacity: isSubmitting ? 0.7 : 1,
    marginTop: isFooter ? '2px' : '4px',
    fontFamily,
  };

  const checkboxContainerStyle: CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
  };

  return (
    <form onSubmit={handleSubmit} style={containerStyle}>
      <div style={messageStyle}>{schema.message}</div>

      <div style={fieldsWrapperStyle}>
        {schema.fields.map((field) => (
          <div key={field.name} style={fieldContainerStyle}>
            <label style={labelStyle}>
              {field.label}
              {field.required && <span style={{ color: '#ef4444', marginLeft: '2px' }}>*</span>}
            </label>

            {field.description && (
              <div style={descriptionStyle}>{field.description}</div>
            )}

            {field.type === 'text' && (
              <input
                type="text"
                style={inputStyle}
                placeholder={field.placeholder || ''}
                value={(formData[field.name] as string) || ''}
                onChange={(e) => handleChange(field.name, e.target.value)}
                disabled={isSubmitted || isSubmitting}
              />
            )}

            {field.type === 'number' && (
              <input
                type="number"
                style={inputStyle}
                placeholder={field.placeholder || ''}
                value={formData[field.name] !== undefined ? String(formData[field.name]) : ''}
                onChange={(e) => handleChange(field.name, e.target.value ? Number(e.target.value) : '')}
                disabled={isSubmitted || isSubmitting}
              />
            )}

            {field.type === 'date' && (
              <input
                type="date"
                style={inputStyle}
                value={(formData[field.name] as string) || ''}
                onChange={(e) => handleChange(field.name, e.target.value)}
                disabled={isSubmitted || isSubmitting}
              />
            )}

            {field.type === 'select' && (
              <select
                style={selectStyle}
                value={(formData[field.name] as string) || ''}
                onChange={(e) => handleChange(field.name, e.target.value)}
                disabled={isSubmitted || isSubmitting}
              >
                <option value="">{field.placeholder || 'Select...'}</option>
                {field.options?.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            )}

            {field.type === 'boolean' && (
              <div style={checkboxContainerStyle}>
                <input
                  type="checkbox"
                  checked={(formData[field.name] as boolean) || false}
                  onChange={(e) => handleChange(field.name, e.target.checked)}
                  disabled={isSubmitted || isSubmitting}
                  style={{ width: '16px', height: '16px' }}
                />
                <span style={{ fontSize: '14px', color: '#374151' }}>
                  {field.placeholder || 'Yes'}
                </span>
              </div>
            )}

            {errors[field.name] && (
              <div style={errorStyle}>{errors[field.name]}</div>
            )}
          </div>
        ))}
      </div>

      <div style={{ display: 'flex', gap: '8px', marginTop: isFooter ? '2px' : '4px' }}>
        {showCancel && (
          <button
            type="button"
            style={{
              ...buttonStyle,
              marginTop: 0,
              backgroundColor: 'transparent',
              color: '#6b7280',
              border: '1px solid #d1d5db',
              cursor: isSubmitting ? 'not-allowed' : 'pointer',
            }}
            disabled={isSubmitting}
            onClick={onCancel}
          >
            Skip
          </button>
        )}
        <button
          type="submit"
          style={{ ...buttonStyle, marginTop: 0 }}
          disabled={isSubmitted || isSubmitting}
        >
          {isSubmitted ? 'Submitted' : isSubmitting ? 'Submitting...' : 'Submit'}
        </button>
      </div>
    </form>
  );
};

export default DynamicFormMessage;
