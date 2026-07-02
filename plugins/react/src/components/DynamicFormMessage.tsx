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
  /**
   * "card"       = inline chat bubble
   * "footer"     = compact footer layout
   * "fullscreen" = fills the chat panel; message shown as a heading on top
   */
  variant?: 'card' | 'footer' | 'fullscreen';
  /** Optional heading above the message (e.g. the agent name) for the fullscreen layout. */
  title?: string;
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
  title,
}) => {
  const [formData, setFormData] = useState<Record<string, unknown>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [focused, setFocused] = useState<string | null>(null);

  const isFooter = variant === 'footer';
  const isFullscreen = variant === 'fullscreen';
  const allFieldsOptional = schema.fields.every((f) => !f.required);
  const showCancel = !!onCancel && allFieldsOptional && !isSubmitted;
  const disabled = isSubmitted || isSubmitting;

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

  const formStyle: CSSProperties = isFullscreen
    ? { display: 'flex', flexDirection: 'column', height: '100%', width: '100%', fontFamily }
    : isFooter
    ? { width: '100%', fontFamily }
    : {
        backgroundColor: '#ffffff',
        border: '1px solid #e5e7eb',
        borderRadius: '14px',
        padding: '16px',
        maxWidth: '100%',
        fontFamily,
        boxShadow: '0 1px 2px rgba(0,0,0,0.04)',
      };

  const headerStyle: CSSProperties = {
    padding: isFullscreen ? '20px 22px 16px' : 0,
    borderBottom: isFullscreen ? '1px solid #eef0f3' : 'none',
    flexShrink: 0,
  };

  const titleStyle: CSSProperties = {
    fontSize: '13px',
    fontWeight: 700,
    color: primaryColor,
    letterSpacing: '0.02em',
    textTransform: 'uppercase',
    marginBottom: '6px',
  };

  const messageStyle: CSSProperties = {
    fontSize: isFullscreen ? '18px' : isFooter ? '13px' : '15px',
    lineHeight: 1.4,
    color: isFullscreen ? '#111827' : '#374151',
    marginBottom: isFullscreen ? 0 : isFooter ? '10px' : '14px',
    fontWeight: isFullscreen ? 700 : 500,
  };

  const bodyStyle: CSSProperties = isFullscreen
    ? { flex: 1, overflowY: 'auto', padding: '18px 22px', display: 'flex', flexDirection: 'column', gap: '18px' }
    : isFooter
    ? { maxHeight: '220px', overflowY: 'auto', paddingRight: '4px', display: 'flex', flexDirection: 'column', gap: '12px' }
    : { display: 'flex', flexDirection: 'column', gap: '14px' };

  const labelStyle: CSSProperties = {
    display: 'block',
    fontSize: '13px',
    fontWeight: 600,
    color: '#1f2937',
    marginBottom: '6px',
  };

  const descriptionStyle: CSSProperties = {
    fontSize: '12px',
    color: '#6b7280',
    marginTop: '-2px',
    marginBottom: '7px',
    lineHeight: 1.4,
  };

  const baseInputStyle = (name: string): CSSProperties => ({
    width: '100%',
    padding: '10px 12px',
    fontSize: '14px',
    border: `1.5px solid ${focused === name ? primaryColor : '#e5e7eb'}`,
    borderRadius: '10px',
    outline: 'none',
    boxSizing: 'border-box',
    backgroundColor: disabled ? '#f3f4f6' : '#ffffff',
    color: '#111827',
    fontFamily,
    transition: 'border-color 120ms ease, box-shadow 120ms ease',
    boxShadow: focused === name ? `0 0 0 3px ${hexToSoftRing(primaryColor)}` : 'none',
  });

  const errorStyle: CSSProperties = {
    fontSize: '12px',
    color: '#ef4444',
    marginTop: '5px',
  };

  const footerStyle: CSSProperties = {
    display: 'flex',
    gap: '10px',
    flexShrink: 0,
    ...(isFullscreen
      ? { padding: '16px 22px', borderTop: '1px solid #eef0f3' }
      : { marginTop: isFooter ? '8px' : '14px' }),
  };

  const primaryButtonStyle: CSSProperties = {
    flex: 1,
    padding: '11px 16px',
    fontSize: '14px',
    fontWeight: 600,
    color: '#ffffff',
    backgroundColor: disabled ? '#9ca3af' : primaryColor,
    border: 'none',
    borderRadius: '10px',
    cursor: disabled ? 'not-allowed' : 'pointer',
    opacity: isSubmitting ? 0.75 : 1,
    fontFamily,
    transition: 'opacity 120ms ease',
  };

  const skipButtonStyle: CSSProperties = {
    padding: '11px 16px',
    fontSize: '14px',
    fontWeight: 600,
    color: '#6b7280',
    backgroundColor: 'transparent',
    border: '1.5px solid #e5e7eb',
    borderRadius: '10px',
    cursor: isSubmitting ? 'not-allowed' : 'pointer',
    fontFamily,
  };

  const renderField = (field: FormField) => (
    <div key={field.name}>
      <label style={labelStyle}>
        {field.label}
        {field.required && <span style={{ color: '#ef4444', marginLeft: '3px' }}>*</span>}
      </label>

      {field.description && <div style={descriptionStyle}>{field.description}</div>}

      {field.type === 'text' && (
        <input
          type="text"
          style={baseInputStyle(field.name)}
          placeholder={field.placeholder || ''}
          value={(formData[field.name] as string) || ''}
          onChange={(e) => handleChange(field.name, e.target.value)}
          onFocus={() => setFocused(field.name)}
          onBlur={() => setFocused(null)}
          disabled={disabled}
        />
      )}

      {field.type === 'number' && (
        <input
          type="number"
          style={baseInputStyle(field.name)}
          placeholder={field.placeholder || ''}
          value={formData[field.name] !== undefined ? String(formData[field.name]) : ''}
          onChange={(e) => handleChange(field.name, e.target.value ? Number(e.target.value) : '')}
          onFocus={() => setFocused(field.name)}
          onBlur={() => setFocused(null)}
          disabled={disabled}
        />
      )}

      {field.type === 'date' && (
        <input
          type="date"
          style={baseInputStyle(field.name)}
          value={(formData[field.name] as string) || ''}
          onChange={(e) => handleChange(field.name, e.target.value)}
          onFocus={() => setFocused(field.name)}
          onBlur={() => setFocused(null)}
          disabled={disabled}
        />
      )}

      {field.type === 'select' && (
        <select
          style={{ ...baseInputStyle(field.name), appearance: 'auto' as const, cursor: disabled ? 'not-allowed' : 'pointer' }}
          value={(formData[field.name] as string) || ''}
          onChange={(e) => handleChange(field.name, e.target.value)}
          onFocus={() => setFocused(field.name)}
          onBlur={() => setFocused(null)}
          disabled={disabled}
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
        <label style={{ display: 'flex', alignItems: 'center', gap: '10px', cursor: disabled ? 'not-allowed' : 'pointer' }}>
          <input
            type="checkbox"
            checked={(formData[field.name] as boolean) || false}
            onChange={(e) => handleChange(field.name, e.target.checked)}
            disabled={disabled}
            style={{ width: '17px', height: '17px', accentColor: primaryColor, cursor: 'inherit' }}
          />
          <span style={{ fontSize: '14px', color: '#374151' }}>{field.placeholder || 'Yes'}</span>
        </label>
      )}

      {errors[field.name] && <div style={errorStyle}>{errors[field.name]}</div>}
    </div>
  );

  const buttons = (
    <div style={footerStyle}>
      {showCancel && (
        <button type="button" style={skipButtonStyle} disabled={isSubmitting} onClick={onCancel}>
          Skip
        </button>
      )}
      <button type="submit" style={primaryButtonStyle} disabled={disabled}>
        {isSubmitted ? 'Submitted' : isSubmitting ? 'Submitting…' : 'Submit'}
      </button>
    </div>
  );

  return (
    <form onSubmit={handleSubmit} style={formStyle}>
      {(schema.message || (isFullscreen && title)) && (
        <div style={headerStyle}>
          {isFullscreen && title && <div style={titleStyle}>{title}</div>}
          {schema.message && <div style={messageStyle}>{schema.message}</div>}
        </div>
      )}

      <div style={bodyStyle}>{schema.fields.map(renderField)}</div>

      {buttons}
    </form>
  );
};

/** Translucent version of the primary color for the focus ring (accepts #rgb/#rrggbb). */
function hexToSoftRing(hex: string): string {
  const m = hex.replace('#', '');
  const full = m.length === 3 ? m.split('').map((c) => c + c).join('') : m;
  const int = parseInt(full, 16);
  if (full.length !== 6 || Number.isNaN(int)) return 'rgba(37,99,235,0.15)';
  const r = (int >> 16) & 255;
  const g = (int >> 8) & 255;
  const b = int & 255;
  return `rgba(${r}, ${g}, ${b}, 0.15)`;
}

export default DynamicFormMessage;
