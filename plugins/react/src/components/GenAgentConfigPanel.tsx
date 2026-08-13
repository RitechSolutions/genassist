import React, { useEffect, useMemo, useState } from 'react';
import { ChevronDown, ChevronUp, Plus, Trash2, Pencil, X, Sparkles } from 'lucide-react';

/**
 * Tracks the host platform's dark mode by watching the `dark` class on <html>
 * (Genassist uses next-themes with the class strategy). The config panel is only
 * embedded in the Genassist platform, so its colors follow the platform theme with
 * a fixed palette — they are not user-customizable (unlike the chat widget's theme).
 */
function useIsDarkMode(): boolean {
  const getIsDark = () =>
    typeof document !== 'undefined' && document.documentElement.classList.contains('dark');
  const [isDark, setIsDark] = useState<boolean>(getIsDark);
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const root = document.documentElement;
    const update = () => setIsDark(root.classList.contains('dark'));
    update();
    const observer = new MutationObserver(update);
    observer.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);
  return isDark;
}

interface PanelPalette {
  panelBg: string;
  sectionBg: string;
  actionBarBg: string;
  border: string;
  inputBg: string;
  text: string;
  textStrong: string;
  textMuted: string;
  saveBg: string;
  saveText: string;
  saveBorder: string;
  cancelBg: string;
  metaValueBg: string;
  metaValueBorder: string;
  modalOverlay: string;
  shadow: string;
}

function getPanelPalette(isDark: boolean): PanelPalette {
  if (isDark) {
    return {
      panelBg: '#1e1e20',
      sectionBg: '#26262a',
      actionBarBg: '#1a1a1c',
      border: '#3f3f46',
      inputBg: '#2a2a2e',
      text: '#d4d4d8',
      textStrong: '#fafafa',
      textMuted: '#a1a1aa',
      saveBg: '#fafafa',
      saveText: '#18181b',
      saveBorder: '#fafafa',
      cancelBg: '#2a2a2e',
      metaValueBg: '#2a2a2e',
      metaValueBorder: '#3f3f46',
      modalOverlay: 'rgba(0,0,0,0.6)',
      shadow: '0 2px 10px rgba(0,0,0,0.5)',
    };
  }
  return {
    panelBg: '#ffffff',
    sectionBg: '#f9f9f9',
    actionBarBg: '#fafafa',
    border: '#e0e0e0',
    inputBg: '#ffffff',
    text: '#333',
    textStrong: '#111',
    textMuted: '#666',
    saveBg: '#111827',
    saveText: '#fff',
    saveBorder: '#0b1220',
    cancelBg: '#fff',
    metaValueBg: '#fafafa',
    metaValueBorder: '#e6e6e6',
    modalOverlay: 'rgba(0,0,0,0.25)',
    shadow: '0 2px 10px rgba(0,0,0,0.1)',
  };
}

export interface ChatTheme {
  primaryColor: string;
  secondaryColor: string;
  backgroundColor: string;
  textColor: string;
  fontFamily: string;
  fontSize: string;
  /** Background of the visitor's (customer) message bubble. */
  userBubbleColor: string;
  /** Background of the input field / docked bar. */
  inputBackgroundColor: string;
  /** Border color across the container, inputs, menus and dialogs. */
  borderColor: string;
  /** Secondary/muted text (timestamps, descriptions, disclaimers). */
  mutedTextColor: string;
}

export interface ChatSettingsConfig {
  name: string;
  description: string;
  agentName: string;
  logoUrl?: string;
  brandLogoUrl?: string;
}

export interface FeatureFlags {
  useAudio?: boolean;
  useFile?: boolean;
  useWs?: boolean;
  usePoll?: boolean;
  quickInput?: boolean;
  readReceipts?: boolean;
}

type ParamType = 'string' | 'number' | 'boolean';

interface MetadataParam {
  name: string;
  type: ParamType;
  description?: string;
  required: boolean;
  value?: string | number | boolean;
}

export interface GenAgentConfigPanelProps {
  theme?: ChatTheme;
  onThemeChange?: (next: ChatTheme) => void;

  chatSettings?: ChatSettingsConfig;
  onChatSettingsChange?: (next: ChatSettingsConfig) => void;

  metadata?: Record<string, any>;
  onMetadataChange?: (next: Record<string, any>) => void;

  agentChatInputMetadata?: Record<string, any>;

  featureFlags?: FeatureFlags;
  onFeatureFlagsChange?: (next: FeatureFlags) => void;

  defaultOpen?: { appearance?: boolean; settings?: boolean; metadata?: boolean };
  onSave?: (payload: { theme: ChatTheme; chatSettings: ChatSettingsConfig; metadata: Record<string, any>; featureFlags: FeatureFlags }) => void;
  onCancel?: () => void;

  style?: React.CSSProperties;
}

const defaultTheme: ChatTheme = {
  primaryColor: '#4F46E5',
  secondaryColor: '#f5f5f5',
  backgroundColor: '#ffffff',
  textColor: '#000000',
  fontFamily: 'Inter, sans-serif',
  fontSize: '15px',
  userBubbleColor: '#E4E4E7',
  inputBackgroundColor: '#ffffff',
  borderColor: '#e5e7eb',
  mutedTextColor: '#6b7280',
};

const defaultSettings: ChatSettingsConfig = {
  name: 'Genassist',
  description: 'Support',
  agentName: 'Agent',
  logoUrl: '',
  brandLogoUrl: '',
};

const defaultFeatureFlags: FeatureFlags = {
  useAudio: false,
  useFile: false,
  useWs: false,
  usePoll: false,
  quickInput: false,
};

function objectToParams(obj: Record<string, any> | undefined): MetadataParam[] {
  if (!obj) return [];
  return Object.keys(obj).map((k) => {
    const v = obj[k];
    let type: ParamType = 'string';
    if (typeof v === 'number') type = 'number';
    else if (typeof v === 'boolean') type = 'boolean';
    return { name: k, type, required: false, value: v };
  });
}

function paramsToObject(params: MetadataParam[]): Record<string, any> {
  const o: Record<string, any> = {};
  params.forEach((p) => {
    if (typeof p.value !== 'undefined') {
      o[p.name] = p.value;
    }
  });
  return o;
}

export const GenAgentConfigPanel: React.FC<GenAgentConfigPanelProps> = ({
  theme: themeProp,
  onThemeChange,
  chatSettings: chatSettingsProp,
  onChatSettingsChange,
  metadata: metadataProp,
  onMetadataChange,
  agentChatInputMetadata,
  featureFlags: featureFlagsProp,
  onFeatureFlagsChange,
  defaultOpen,
  onSave,
  onCancel,
  style,
}) => {
  // Merge workflow chat input metadata with user metadata
  const mergedMetadata = useMemo(
    () => ({ ...(agentChatInputMetadata || {}), ...(metadataProp || {}) }),
    [agentChatInputMetadata, metadataProp]
  );

  // Controlled or internal state fallbacks
  const [theme, setTheme] = useState<ChatTheme>(themeProp || defaultTheme);
  const [chatSettings, setChatSettings] = useState<ChatSettingsConfig>(chatSettingsProp || defaultSettings);
  const [params, setParams] = useState<MetadataParam[]>(() => objectToParams(mergedMetadata));
  const [featureFlags, setFeatureFlags] = useState<FeatureFlags>(featureFlagsProp || defaultFeatureFlags);

  useEffect(() => {
    if (themeProp) setTheme(themeProp);
  }, [themeProp]);

  useEffect(() => {
    if (chatSettingsProp) setChatSettings(chatSettingsProp);
  }, [chatSettingsProp]);

  useEffect(() => {
    setParams(objectToParams(mergedMetadata));
  }, [agentChatInputMetadata, metadataProp]);

  useEffect(() => {
    if (featureFlagsProp) setFeatureFlags(featureFlagsProp);
  }, [featureFlagsProp]);

  const [showAppearance, setShowAppearance] = useState(
    typeof defaultOpen?.appearance === 'boolean' ? !!defaultOpen?.appearance : true
  );
  const [showSettings, setShowSettings] = useState(
    typeof defaultOpen?.settings === 'boolean' ? !!defaultOpen?.settings : false
  );
  const [showMetadata, setShowMetadata] = useState(
    typeof defaultOpen?.metadata === 'boolean' ? !!defaultOpen?.metadata : false
  );

  // Auto-expand Metadata section
  const prevMetaKeyCountRef = React.useRef<number>(0);
  useEffect(() => {
    const keyCount = agentChatInputMetadata ? Object.keys(agentChatInputMetadata).length : 0;
    if (keyCount > 0 && prevMetaKeyCountRef.current === 0) {
      setShowMetadata(true);
    }
    prevMetaKeyCountRef.current = keyCount;
  }, [agentChatInputMetadata]);

  const [showAddParam, setShowAddParam] = useState(false);
  const [draftParam, setDraftParam] = useState<MetadataParam>({
    name: 'param_1',
    type: 'string',
    required: false,
    value: '',
  });

  const [showEditParam, setShowEditParam] = useState(false);
  const [editIndex, setEditIndex] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<MetadataParam>({ name: '', type: 'string', required: false, value: '' });

  const metadata = useMemo(() => paramsToObject(params), [params]);

  const handleThemeChange = (key: keyof ChatTheme, value: string) => {
    const next = { ...theme, [key]: value } as ChatTheme;
    if (!themeProp) setTheme(next);
    onThemeChange?.(next);
  };

  const handleSettingChange = (key: keyof ChatSettingsConfig, value: string) => {
    const next = { ...chatSettings, [key]: value } as ChatSettingsConfig;
    if (!chatSettingsProp) setChatSettings(next);
    onChatSettingsChange?.(next);
  };

  const handleFeatureFlagChange = (key: keyof FeatureFlags, value: boolean) => {
    const next = { ...featureFlags, [key]: value } as FeatureFlags;
    if (!featureFlagsProp) setFeatureFlags(next);
    onFeatureFlagsChange?.(next);
  };

  const handleAddParam = () => {
    const name = draftParam.name.trim();
    if (!name) return;
    if (params.some((p) => p.name === name)) return;
    const normalized: MetadataParam = {
      ...draftParam,
      name,
      value:
        typeof draftParam.value !== 'undefined'
          ? draftParam.value
          : draftParam.type === 'number'
          ? 0
          : draftParam.type === 'boolean'
          ? false
          : '',
    };
    const next = [...params, normalized];
    setParams(next);
    onMetadataChange?.(paramsToObject(next));
    setDraftParam({ name: 'param_1', type: 'string', required: false, value: '' });
    setShowAddParam(false);
  };

  const coerceForType = (val: any, type: ParamType) => {
    if (type === 'number') {
      const n = Number(val);
      return isNaN(n) ? 0 : n;
    }
    if (type === 'boolean') {
      if (typeof val === 'boolean') return val;
      const s = String(val).toLowerCase();
      return s === 'true' || s === '1' || s === 'yes';
    }
    return String(val ?? '');
  };

  const handleEditSave = () => {
    if (editIndex === null) return;
    const newName = editDraft.name.trim();
    if (!newName) return;
    if (params.some((p, i) => i !== editIndex && p.name === newName)) return;
    const next = [...params];
    const old = next[editIndex];
    const updated: MetadataParam = { ...old, ...editDraft };
    updated.value = coerceForType(old.value, editDraft.type);
    next[editIndex] = updated;
    setParams(next);
    onMetadataChange?.(paramsToObject(next));
    setShowEditParam(false);
    setEditIndex(null);
  };

  const handleRemoveParam = (index: number) => {
    const next = params.filter((_, i) => i !== index);
    setParams(next);
    onMetadataChange?.(paramsToObject(next));
  };

  // Fixed palette that follows the platform's light/dark theme (not user-customizable).
  const isDark = useIsDarkMode();
  const ui = getPanelPalette(isDark);

  const containerStyle: React.CSSProperties = {
    flex: '1',
    maxWidth: 300,
    backgroundColor: ui.panelBg,
    borderRadius: 8,
    boxShadow: ui.shadow,
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column',
    ...style,
  };

  const sectionHeaderStyle: React.CSSProperties = {
    padding: 16,
    borderBottom: `1px solid ${ui.border}`,
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    cursor: 'pointer',
    backgroundColor: ui.sectionBg,
    color: ui.textStrong,
  };

  const sectionTitleStyle: React.CSSProperties = {
    margin: 0,
    fontSize: 12,
    fontWeight: 'bold',
    color: ui.textMuted,
    letterSpacing: 1,
  } as React.CSSProperties;

  const formGroupStyle: React.CSSProperties = {
    padding: '16px 16px 12px',
    display: 'flex',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: 'none',
  };

  const labelStyle: React.CSSProperties = { fontSize: 14, color: ui.text };
  const colorPickerStyle: React.CSSProperties = {
    appearance: 'none',
    width: 120,
    height: 32,
    padding: 0,
    border: `1px solid ${ui.border}`,
    borderRadius: 4,
    cursor: 'pointer',
    backgroundColor: ui.inputBg,
  } as React.CSSProperties;

  const selectStyle: React.CSSProperties = {
    width: 140,
    height: 32,
    padding: '0 8px',
    border: `1px solid ${ui.border}`,
    borderRadius: 4,
    backgroundColor: ui.inputBg,
    color: ui.text,
    fontSize: 14,
  } as React.CSSProperties;

  const inputStyle: React.CSSProperties = {
    width: '100%',
    height: 32,
    padding: '0 8px',
    border: `1px solid ${ui.border}`,
    borderRadius: 4,
    backgroundColor: ui.inputBg,
    color: ui.text,
    fontSize: 14,
  };

  const actionBarStyle: React.CSSProperties = {
    padding: 12,
    display: 'flex',
    justifyContent: 'flex-end',
    gap: 8,
    borderTop: `1px solid ${ui.border}`,
    backgroundColor: ui.actionBarBg,
  };

  const cancelButtonStyle: React.CSSProperties = {
    padding: '8px 12px',
    backgroundColor: ui.cancelBg,
    color: ui.text,
    border: `1px solid ${ui.border}`,
    borderRadius: 6,
    cursor: 'pointer',
  };
  const saveButtonStyle: React.CSSProperties = {
    padding: '8px 12px',
    backgroundColor: ui.saveBg,
    color: ui.saveText,
    border: `1px solid ${ui.saveBorder}`,
    borderRadius: 6,
    cursor: 'pointer',
  };

  const fullWidthActionButton: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    width: '100%',
    padding: '10px 12px',
    border: `1px solid ${ui.border}`,
    borderRadius: 8,
    backgroundColor: ui.inputBg,
    cursor: 'pointer',
    fontSize: 14,
    color: ui.textStrong,
  };

  const smallIconButton: React.CSSProperties = {
    border: `1px solid ${ui.border}`,
    borderRadius: 8,
    width: 28,
    height: 28,
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: ui.inputBg,
    color: ui.text,
    cursor: 'pointer',
  };

  const metaRowStyle: React.CSSProperties = {
    display: 'grid',
    gridTemplateColumns: '1fr minmax(90px, 150px) 28px 28px',
    alignItems: 'center',
    gap: 8,
    padding: '6px 0',
  };
  const metaNameStyle: React.CSSProperties = {
    fontSize: 13,
    color: ui.textStrong,
    fontWeight: 500,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  };
  const metaValueStyle: React.CSSProperties = {
    maxWidth: 150,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
    fontSize: 13,
    color: ui.textStrong,
    border: `1px solid ${ui.metaValueBorder}`,
    borderRadius: 12,
    padding: '6px 10px',
    backgroundColor: ui.metaValueBg,
  };

  const handleSave = () => {
    onSave?.({ theme, chatSettings, metadata, featureFlags });
  };

  return (
    <div style={containerStyle}>
      {/* Appearance Section */}
      <div style={{ borderBottom: '1px solid #e0e0e0' }}>
        <div style={sectionHeaderStyle} onClick={() => setShowAppearance(!showAppearance)}>
          <h3 style={sectionTitleStyle}>APPEARANCE</h3>
          {showAppearance ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
        {showAppearance && (
          <>
            <div style={formGroupStyle}>
              <label style={labelStyle}>Primary Color</label>
              <input
                type="color"
                value={theme.primaryColor}
                onChange={(e) => handleThemeChange('primaryColor', e.target.value)}
                style={colorPickerStyle}
              />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>Secondary Color</label>
              <input
                type="color"
                value={theme.secondaryColor}
                onChange={(e) => handleThemeChange('secondaryColor', e.target.value)}
                style={colorPickerStyle}
              />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>Background Color</label>
              <input
                type="color"
                value={theme.backgroundColor}
                onChange={(e) => handleThemeChange('backgroundColor', e.target.value)}
                style={colorPickerStyle}
              />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>Text Color</label>
              <input
                type="color"
                value={theme.textColor}
                onChange={(e) => handleThemeChange('textColor', e.target.value)}
                style={colorPickerStyle}
              />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>User Bubble Color</label>
              <input
                type="color"
                value={theme.userBubbleColor ?? defaultTheme.userBubbleColor}
                onChange={(e) => handleThemeChange('userBubbleColor', e.target.value)}
                style={colorPickerStyle}
              />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>Input Background</label>
              <input
                type="color"
                value={theme.inputBackgroundColor ?? defaultTheme.inputBackgroundColor}
                onChange={(e) => handleThemeChange('inputBackgroundColor', e.target.value)}
                style={colorPickerStyle}
              />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>Border Color</label>
              <input
                type="color"
                value={theme.borderColor ?? defaultTheme.borderColor}
                onChange={(e) => handleThemeChange('borderColor', e.target.value)}
                style={colorPickerStyle}
              />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>Muted Text Color</label>
              <input
                type="color"
                value={theme.mutedTextColor ?? defaultTheme.mutedTextColor}
                onChange={(e) => handleThemeChange('mutedTextColor', e.target.value)}
                style={colorPickerStyle}
              />
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>Font Size</label>
              <select
                style={selectStyle}
                value={theme.fontSize}
                onChange={(e) => handleThemeChange('fontSize', e.target.value)}
              >
                <option value="12px">Small (12px)</option>
                <option value="15px">Medium (15px)</option>
                <option value="18px">Large (18px)</option>
              </select>
            </div>
            <div style={formGroupStyle}>
              <label style={labelStyle}>Font Family</label>
              <select
                style={selectStyle}
                value={theme.fontFamily.split(',')[0].trim()}
                onChange={(e) => {
                  const v = e.target.value;
                  const ff =
                    v === 'Inter'
                      ? 'Inter, sans-serif'
                      : v === 'Arial'
                      ? 'Arial, sans-serif'
                      : v === 'Times New Roman'
                      ? "'Times New Roman', serif"
                      : 'monospace';
                  handleThemeChange('fontFamily', ff);
                }}
              >
                <option value="Inter">Inter</option>
                <option value="Arial">Arial</option>
                <option value="Times New Roman">Times New Roman</option>
                <option value="monospace">Monospace</option>
              </select>
            </div>
          </>
        )}
      </div>

      {/* Settings Section */}
      <div>
        <div style={sectionHeaderStyle} onClick={() => setShowSettings(!showSettings)}>
          <h3 style={sectionTitleStyle}>SETTINGS</h3>
          {showSettings ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
        {showSettings && (
          <>
            <div style={{ padding: '16px 16px 12px' }}>
              <label style={{ ...labelStyle, display: 'block', marginBottom: 8 }}>Name</label>
              <input
                type="text"
                style={{ ...inputStyle, height: 40, padding: '0 12px', boxSizing: 'border-box' }}
                value={chatSettings.name}
                onChange={(e) => handleSettingChange('name', e.target.value)}
              />
            </div>
            <div style={{ padding: '0 16px 12px' }}>
              <label style={{ ...labelStyle, display: 'block', marginBottom: 8 }}>Description</label>
              <input
                type="text"
                style={{ ...inputStyle, height: 40, padding: '0 12px', boxSizing: 'border-box' }}
                value={chatSettings.description}
                onChange={(e) => handleSettingChange('description', e.target.value)}
              />
            </div>
            <div style={{ padding: '0 16px 12px' }}>
              <label style={{ ...labelStyle, display: 'block', marginBottom: 8 }}>Agent Name</label>
              <input
                type="text"
                style={{ ...inputStyle, height: 40, padding: '0 12px', boxSizing: 'border-box' }}
                value={chatSettings.agentName}
                onChange={(e) => handleSettingChange('agentName', e.target.value)}
              />
            </div>
            <div style={{ padding: '0 16px 12px' }}>
              <label style={{ ...labelStyle, display: 'block', marginBottom: 8 }}>Logo URL</label>
              <input
                type="text"
                style={{ ...inputStyle, height: 40, padding: '0 12px', boxSizing: 'border-box' }}
                value={chatSettings.logoUrl || ''}
                onChange={(e) => handleSettingChange('logoUrl', e.target.value)}
                placeholder="https://example.com/logo.png"
              />
            </div>
            <div style={{ padding: '0 16px 16px' }}>
              <label style={{ ...labelStyle, display: 'block', marginBottom: 8 }}>Full Logo URL</label>
              <input
                type="text"
                style={{ ...inputStyle, height: 40, padding: '0 12px', boxSizing: 'border-box' }}
                value={chatSettings.brandLogoUrl || ''}
                onChange={(e) => handleSettingChange('brandLogoUrl', e.target.value)}
                placeholder="https://example.com/full-logo.png"
              />
              <div style={{ fontSize: 11, color: ui.textMuted, marginTop: 6 }}>
                When set, replaces the small logo + name with this full logo.
              </div>
            </div>
            <div style={{ padding: '16px', borderTop: '1px solid #e0e0e0', marginTop: 8 }}>
              <div style={{ fontSize: 13, color: ui.textMuted, marginBottom: 12, fontWeight: 500 }}>
                Features
              </div>
              <div style={formGroupStyle}>
                <label style={labelStyle}>Use Audio</label>
                <input
                  type="checkbox"
                  checked={!!featureFlags.useAudio}
                  onChange={(e) => handleFeatureFlagChange('useAudio', e.target.checked)}
                  style={{ width: 20, height: 20, cursor: 'pointer' }}
                />
              </div>
              <div style={formGroupStyle}>
                <label style={labelStyle}>Use File</label>
                <input
                  type="checkbox"
                  checked={!!featureFlags.useFile}
                  onChange={(e) => handleFeatureFlagChange('useFile', e.target.checked)}
                  style={{ width: 20, height: 20, cursor: 'pointer' }}
                />
              </div>
              <div style={formGroupStyle}>
                <label style={labelStyle}>Use WebSocket</label>
                <input
                  type="checkbox"
                  checked={!!featureFlags.useWs}
                  onChange={(e) => handleFeatureFlagChange('useWs', e.target.checked)}
                  style={{ width: 20, height: 20, cursor: 'pointer' }}
                />
              </div>
              <div style={formGroupStyle}>
                <label style={labelStyle}>Use Heartbeat Polling</label>
                <input
                  type="checkbox"
                  checked={!!featureFlags.usePoll}
                  onChange={(e) => handleFeatureFlagChange('usePoll', e.target.checked)}
                  style={{ width: 20, height: 20, cursor: 'pointer' }}
                />
              </div>
              <div style={formGroupStyle}>
                <label style={labelStyle}>Quick Message Input</label>
                <input
                  type="checkbox"
                  checked={!!featureFlags.quickInput}
                  onChange={(e) => handleFeatureFlagChange('quickInput', e.target.checked)}
                  style={{ width: 20, height: 20, cursor: 'pointer' }}
                />
              </div>
            </div>
          </>
        )}
      </div>

      {/* Metadata Section */}
      <div>
        <div style={sectionHeaderStyle} onClick={() => setShowMetadata(!showMetadata)}>
          <h3 style={sectionTitleStyle}>METADATA</h3>
          {showMetadata ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
        {showMetadata && (
          <>
            <div style={{ padding: '12px 16px' }}>
              <div style={{ fontSize: 13, color: ui.textMuted, marginBottom: 10 }}>
                Define key/value parameters sent as chat metadata.
                {Object.keys(agentChatInputMetadata || {}).length > 0 && (
                  <span style={{ display: 'block', marginTop: 4, color: ui.textMuted }}>
                    Parameters from the workflow&apos;s Chat Input node are shown below.
                  </span>
                )}
              </div>
              <button style={fullWidthActionButton} onClick={() => setShowAddParam(true)}>
                <Plus size={18} />
                <span>Add Parameter</span>
              </button>
            </div>
            {params.length > 0 && (
              <div style={{ padding: '2px 16px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                {params.map((p, idx) => {
                  const displayVal = p.type === 'boolean' ? (p.value ? 'True' : 'False') : String(p.value ?? '');
                  return (
                    <div key={p.name} style={metaRowStyle}>
                      <div style={metaNameStyle}>{p.name}</div>
                      <div style={metaValueStyle} title={displayVal}>
                        {displayVal}
                      </div>
                      <button
                        title="Edit"
                        style={smallIconButton}
                        onClick={() => {
                          setEditIndex(idx);
                          setEditDraft({ ...p });
                          setShowEditParam(true);
                        }}
                        aria-label={`Edit ${p.name}`}
                      >
                        <Pencil size={16} />
                      </button>
                      <button
                        title="Remove"
                        style={smallIconButton}
                        onClick={() => handleRemoveParam(idx)}
                        aria-label={`Remove ${p.name}`}
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>

      {/* Action Buttons */}
      <div style={actionBarStyle}>
        <button style={cancelButtonStyle} onClick={() => onCancel?.()}>Cancel</button>
        <button style={saveButtonStyle} onClick={handleSave}>Save Changes</button>
      </div>

      {/* Simple Parameter Modals */}
      {showAddParam && (
        <div style={getModalOverlayStyle(ui)}>
          <div style={getModalStyle(ui)}>
            <div style={getModalHeaderStyle(ui)}>Add Parameter</div>
            <div style={modalBodyStyle}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: 12, color: ui.textMuted }}>Parameter Name</label>
                <input
                  type="text"
                  style={inputStyle}
                  value={draftParam.name}
                  onChange={(e) => setDraftParam((d) => ({ ...d, name: e.target.value }))}
                  placeholder="param_1"
                />
              </div>

              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
                  <label style={{ fontSize: 12, color: ui.textMuted }}>Type</label>
                  <select
                    style={selectStyle}
                    value={draftParam.type}
                    onChange={(e) =>
                      setDraftParam((d) => ({
                        ...d,
                        type: e.target.value as ParamType,
                        value: e.target.value === 'boolean' ? false : e.target.value === 'number' ? 0 : '',
                      }))
                    }
                  >
                    <option value="string">String</option>
                    <option value="number">Number</option>
                    <option value="boolean">Boolean</option>
                  </select>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
                  <label style={{ fontSize: 12, color: ui.textMuted }}>Required</label>
                  <select
                    style={selectStyle}
                    value={draftParam.required ? 'yes' : 'no'}
                    onChange={(e) => setDraftParam((d) => ({ ...d, required: e.target.value === 'yes' }))}
                  >
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: 12, color: ui.textMuted }}>Default / Value</label>
                {draftParam.type === 'boolean' ? (
                  <select
                    style={selectStyle}
                    value={draftParam.value ? 'true' : 'false'}
                    onChange={(e) => setDraftParam((d) => ({ ...d, value: e.target.value === 'true' }))}
                  >
                    <option value="false">False</option>
                    <option value="true">True</option>
                  </select>
                ) : (
                  <input
                    type={draftParam.type === 'number' ? 'number' : 'text'}
                    style={inputStyle}
                    value={String(draftParam.value ?? '')}
                    onChange={(e) =>
                      setDraftParam((d) => ({
                        ...d,
                        value: draftParam.type === 'number' ? Number(e.target.value) : e.target.value,
                      }))
                    }
                  />
                )}
              </div>
            </div>

            <div style={getModalFooterStyle(ui)}>
              <button style={cancelButtonStyle} onClick={() => setShowAddParam(false)}>
                Cancel
              </button>
              <button style={saveButtonStyle} onClick={handleAddParam}>
                Add
              </button>
            </div>
          </div>
        </div>
      )}

      {showEditParam && (
        <div style={getModalOverlayStyle(ui)}>
          <div style={getModalStyle(ui)}>
            <div style={getModalHeaderStyle(ui)}>Edit Parameter</div>
            <div style={modalBodyStyle}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: 12, color: ui.textMuted }}>Parameter Name</label>
                <input
                  type="text"
                  style={inputStyle}
                  value={editDraft.name}
                  onChange={(e) => setEditDraft((d) => ({ ...d, name: e.target.value }))}
                />
              </div>

              <div style={{ display: 'flex', gap: 12 }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
                  <label style={{ fontSize: 12, color: ui.textMuted }}>Type</label>
                  <select
                    style={selectStyle}
                    value={editDraft.type}
                    onChange={(e) =>
                      setEditDraft((d) => ({
                        ...d,
                        type: e.target.value as ParamType,
                        value:
                          e.target.value === 'boolean'
                            ? false
                            : e.target.value === 'number'
                            ? 0
                            : typeof d.value === 'string'
                            ? d.value
                            : '',
                      }))
                    }
                  >
                    <option value="string">String</option>
                    <option value="number">Number</option>
                    <option value="boolean">Boolean</option>
                  </select>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: 6, flex: 1 }}>
                  <label style={{ fontSize: 12, color: ui.textMuted }}>Required</label>
                  <select
                    style={selectStyle}
                    value={editDraft.required ? 'yes' : 'no'}
                    onChange={(e) => setEditDraft((d) => ({ ...d, required: e.target.value === 'yes' }))}
                  >
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </div>
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                <label style={{ fontSize: 12, color: ui.textMuted }}>Value</label>
                {editDraft.type === 'boolean' ? (
                  <select
                    style={selectStyle}
                    value={editDraft.value ? 'true' : 'false'}
                    onChange={(e) => setEditDraft((d) => ({ ...d, value: e.target.value === 'true' }))}
                  >
                    <option value="false">False</option>
                    <option value="true">True</option>
                  </select>
                ) : (
                  <input
                    type={editDraft.type === 'number' ? 'number' : 'text'}
                    style={inputStyle}
                    value={String(editDraft.value ?? '')}
                    onChange={(e) =>
                      setEditDraft((d) => ({
                        ...d,
                        value: editDraft.type === 'number' ? Number(e.target.value) : e.target.value,
                      }))
                    }
                  />
                )}
              </div>
            </div>

            <div style={getModalFooterStyle(ui)}>
              <button style={cancelButtonStyle} onClick={() => setShowEditParam(false)}>
                Cancel
              </button>
              <button style={saveButtonStyle} onClick={handleEditSave}>
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Modal styles (shared) — take the palette so the modals follow the platform theme.
const getModalOverlayStyle = (ui: PanelPalette): React.CSSProperties => ({
  position: 'fixed',
  inset: 0,
  backgroundColor: ui.modalOverlay,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1005,
});

const getModalStyle = (ui: PanelPalette): React.CSSProperties => ({
  width: 420,
  maxWidth: '92vw',
  backgroundColor: ui.panelBg,
  color: ui.text,
  borderRadius: 12,
  border: `1px solid ${ui.border}`,
  boxShadow: '0 8px 24px rgba(0,0,0,0.18)',
  overflow: 'hidden',
});

const getModalHeaderStyle = (ui: PanelPalette): React.CSSProperties => ({
  padding: '12px 16px',
  fontWeight: 600,
  color: ui.textStrong,
  borderBottom: `1px solid ${ui.border}`,
});

const modalBodyStyle: React.CSSProperties = {
  padding: 16,
  display: 'flex',
  flexDirection: 'column',
  gap: 12,
};

const getModalFooterStyle = (ui: PanelPalette): React.CSSProperties => ({
  padding: 12,
  display: 'flex',
  justifyContent: 'flex-end',
  gap: 8,
  borderTop: `1px solid ${ui.border}`,
  backgroundColor: ui.actionBarBg,
});