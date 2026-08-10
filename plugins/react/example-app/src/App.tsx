import React, { useMemo, useState, useCallback, useEffect } from "react";
import { FeatureFlags, GenAgentChat, GENASSIST_AGENT_METADATA_UPDATED } from "../../src";
import {
  ChevronDown,
  ChevronUp,
  Plus,
  Trash2,
  Pencil,
  Moon,
  Sun,
} from "lucide-react";

type ColorMode = "light" | "dark";

// Chat theme presets. Toggling the demo's Light/Dark switch swaps the whole chat
// theme so the new dark-mode-oriented tokens (userBubbleColor, inputBackgroundColor,
// borderColor, mutedTextColor) are exercised without hand-tuning each picker.
const LIGHT_THEME = {
  primaryColor: "#173DED",
  secondaryColor: "#f5f5f5",
  backgroundColor: "#ffffff",
  textColor: "#000000",
  fontFamily: "Inter, sans-serif",
  fontSize: "15px",
  userBubbleColor: "#E4E4E7",
  inputBackgroundColor: "#ffffff",
  borderColor: "#e5e7eb",
  mutedTextColor: "#6b7280",
};

const DARK_THEME = {
  primaryColor: "#6366F1",
  secondaryColor: "#1f2023",
  backgroundColor: "#141517",
  textColor: "#f4f4f5",
  fontFamily: "Inter, sans-serif",
  fontSize: "15px",
  userBubbleColor: "#3f3f46",
  inputBackgroundColor: "#26272b",
  borderColor: "#3f3f46",
  mutedTextColor: "#a1a1aa",
};

interface FileState {
  useCustom: boolean;
  file: File | null;
}

function App() {
  type ParamType = "string" | "number" | "boolean";
  interface MetadataParam {
    name: string;
    type: ParamType;
    description?: string;
    required: boolean;
    defaultValue?: string | number | boolean;
    value?: string | number | boolean;
  }

  // Light/Dark demo mode, mirroring the Genassist platform: next-themes toggles the
  // `dark` class on <html> (attribute="class", storageKey="theme"). We reproduce that
  // here without the dependency so the config-panel dark logic (which watches that
  // class) and the chat theme presets can both be tested from one switch.
  const [mode, setMode] = useState<ColorMode>(() => {
    const stored = typeof window !== "undefined" ? localStorage.getItem("theme") : null;
    return stored === "dark" ? "dark" : "light";
  });

  const [theme, setTheme] = useState(mode === "dark" ? DARK_THEME : LIGHT_THEME);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.toggle("dark", mode === "dark");
    // Native form controls (inputs, selects, checkboxes) follow this, so the demo's
    // own controls panel renders dark without hand-styling every field.
    root.style.colorScheme = mode;
    try {
      localStorage.setItem("theme", mode);
    } catch {
      // ignore
    }
  }, [mode]);

  const toggleMode = () => {
    const next: ColorMode = mode === "dark" ? "light" : "dark";
    setMode(next);
    setTheme(next === "dark" ? DARK_THEME : LIGHT_THEME);
  };

  const [chatSettings, setChatSettings] = useState({
    name: "Genassist Support",
    description: "Support",
    agentName: "Agent",
    logoUrl: "",
    brandLogoUrl: "https://cdn.prod.website-files.com/689da2a76e017a77b0596d1c/694291f3d893f585af78bdd7_genassist_logo.svg",
    baseUrl: import.meta.env.VITE_GENASSIST_CHAT_APIURL || "",
    websocketUrl: import.meta.env.VITE_GENASSIST_CHAT_WEBSOCKET_URL || "",
    apiKey: import.meta.env.VITE_GENASSIST_CHAT_APIKEY || "",
    reCaptchaKey: import.meta.env.VITE_GENASSIST_CHAT_RECAPTCHA_KEY || "",
    tenant: import.meta.env.VITE_GENASSIST_CHAT_TENANT || "",
  });

  const [featureFlags, setFeatureFlags] = useState<FeatureFlags>({
    useAudio: false,
    useFile: true,
    useWs: false,
    usePoll: false,
    quickInput: true,
  });

  // Which presentation of the chat to render (see GenAgentChat `mode`).
  const [chatMode, setChatMode] = useState<"floating" | "inputbar" | "embedded">("floating");

  const [customLogo, setCustomLogo] = useState<FileState>({
    useCustom: false,
    file: null,
  });

  const [customBubbleIcon, setCustomBubbleIcon] = useState<FileState>({
    useCustom: false,
    file: null,
  });

  const [showAppearance, setShowAppearance] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [showMetadata, setShowMetadata] = useState(false);
  const [agentChatInputMetadata, setAgentChatInputMetadata] = useState<Record<string, any>>({});

  // Metadata builder state
  const [params, setParams] = useState<MetadataParam[]>([]);

  const [showAddParamModal, setShowAddParamModal] = useState(false);
  const [draftParam, setDraftParam] = useState<MetadataParam>({
    name: "param_1",
    type: "string",
    description: "",
    required: false,
    defaultValue: "",
    value: "",
  });

  // Edit parameter modal state
  const [showEditParamModal, setShowEditParamModal] = useState(false);
  const [editParamIndex, setEditParamIndex] = useState<number | null>(null);
  const [editDraftParam, setEditDraftParam] = useState<MetadataParam>({
    name: "",
    type: "string",
    description: "",
    required: false,
    defaultValue: "",
    value: "",
  });

  const metadata = useMemo(() => {
    const obj: Record<string, any> = {};
    params.forEach((p) => {
      const v = p.value ?? p.defaultValue;
      if (typeof v !== "undefined") {
        obj[p.name] = p.type === "number" && typeof v === "string" ? Number(v) : v;
      }
    });
    return obj;
  }, [params]);

  // Restore persisted metadata on mount (survives page refresh)
  const apiKey = chatSettings.apiKey;
  React.useEffect(() => {
    if (!apiKey) return;
    try {
      const storedAgent = localStorage.getItem(`genassist_agent_chat_input_metadata:${apiKey}`);
      if (storedAgent) {
        const parsed = JSON.parse(storedAgent);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          setAgentChatInputMetadata(parsed);
        }
      }
      const storedMeta = localStorage.getItem(`genassist_metadata:${apiKey}`);
      if (storedMeta) {
        const parsed = JSON.parse(storedMeta);
        if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
          const restored: MetadataParam[] = Object.entries(parsed).map(([name, value]) => {
            let type: ParamType = "string";
            if (typeof value === "number") type = "number";
            else if (typeof value === "boolean") type = "boolean";
            return { name, type, required: false, value: value as string | number | boolean };
          });
          setParams(restored);
        }
      }
    } catch {
      // ignore
    }
  }, [apiKey]);

  // Subscribe to service-level metadata updates (fired by ChatService on each start conversation)
  React.useEffect(() => {
    if (!apiKey) return;
    const handler = (e: CustomEvent<{ apiKey: string; metadata: Record<string, any> }>) => {
      if (e.detail?.apiKey !== apiKey || e.detail?.metadata == null) return;
      const next =
        typeof e.detail.metadata === "object" && !Array.isArray(e.detail.metadata)
          ? e.detail.metadata
          : {};
      setAgentChatInputMetadata(next);
    };
    window.addEventListener(GENASSIST_AGENT_METADATA_UPDATED, handler as EventListener);
    return () =>
      window.removeEventListener(GENASSIST_AGENT_METADATA_UPDATED, handler as EventListener);
  }, [apiKey]);

  // When agent_chat_input_metadata arrives (after "Start conversation"), merge into params and expand METADATA section
  React.useEffect(() => {
    if (!agentChatInputMetadata || Object.keys(agentChatInputMetadata).length === 0) return;
    const fromAgent: MetadataParam[] = Object.entries(agentChatInputMetadata).map(([name, value]) => {
      let type: ParamType = "string";
      if (typeof value === "number") type = "number";
      else if (typeof value === "boolean") type = "boolean";
      return { name, type, required: false, value: value as string | number | boolean };
    });
    setParams((prev) => {
      const byName = new Map<string, MetadataParam>();
      fromAgent.forEach((p) => byName.set(p.name, p));
      prev.forEach((p) => byName.set(p.name, p));
      return Array.from(byName.values());
    });
    setShowMetadata(true);
  }, [agentChatInputMetadata]);

  React.useEffect(() => {
    const ls = localStorage.getItem(`genassist_feature_flags:${chatSettings.apiKey}`);
    if (ls) {
      const parsed = JSON.parse(ls);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        setFeatureFlags(parsed);
      }
    }
  }, [chatSettings.apiKey]);

  const handleColorChange = (property: string, value: string) => {
    setTheme((prevTheme) => ({
      ...prevTheme,
      [property]: value,
    }));
  };

  const handleSettingChange = (property: string, value: string) => {
    setChatSettings((prevSettings) => ({
      ...prevSettings,
      [property]: value,
    }));
  };

  const handleFeatureFlagChange = (property: keyof typeof featureFlags, value: boolean) => {
    const ls = localStorage.getItem(`genassist_feature_flags:${chatSettings.apiKey}`);
    if (ls) {
      const parsed = JSON.parse(ls);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        setFeatureFlags(parsed);
      }
    }
    const next = { ...featureFlags, [property]: value };
    setFeatureFlags(next);
    localStorage.setItem(`genassist_feature_flags:${chatSettings.apiKey}`, JSON.stringify(next));
  };

  const handleLogoChange = (useCustom: boolean) => {
    setCustomLogo({
      ...customLogo,
      useCustom,
    });
  };

  const handleBubbleIconChange = (useCustom: boolean) => {
    setCustomBubbleIcon({
      ...customBubbleIcon,
      useCustom,
    });
  };

  const handleFileUpload = (
    type: "logo" | "bubbleIcon",
    event: React.ChangeEvent<HTMLInputElement>
  ) => {
    if (event.target.files && event.target.files[0]) {
      if (type === "logo") {
        setCustomLogo({
          useCustom: true,
          file: event.target.files[0],
        });
      } else {
        setCustomBubbleIcon({
          useCustom: true,
          file: event.target.files[0],
        });
      }
    }
  };

  const handleSaveChanges = () => {
    try {
      localStorage.setItem(
        `genassist_metadata:${chatSettings.apiKey}`,
        JSON.stringify(metadata)
      );
    } catch {
      // ignore
    }
    alert("Changes saved!");
  };

  // Memoize callbacks to prevent unnecessary re-renders of GenAgentChat
  const handleError = useCallback(() => {}, []);

  // Demo chrome palette (the controls panel + page), light/dark. This is the demo's
  // own dev UI — separate from the chat theme and from the plugin's config panel.
  const isDark = mode === "dark";
  const ui = isDark
    ? {
        pageBg: "#0b0b0d",
        panelBg: "#1a1a1c",
        sectionBg: "#232326",
        border: "#3f3f46",
        text: "#d4d4d8",
        textMuted: "#a1a1aa",
      }
    : {
        pageBg: "#f3f4f6",
        panelBg: "#ffffff",
        sectionBg: "#f9f9f9",
        border: "#e0e0e0",
        text: "#333",
        textMuted: "#666",
      };

  const containerStyle: React.CSSProperties = {
    display: "flex",
    padding: "20px",
    gap: "20px",
    height: "100vh",
    boxSizing: "border-box",
    fontFamily: "Inter, sans-serif",
    position: "relative",
    background: ui.pageBg,
    color: ui.text,
  };

  const controlsPanelStyle: React.CSSProperties = {
    flex: "1",
    maxWidth: "300px",
    backgroundColor: ui.panelBg,
    color: ui.text,
    borderRadius: "8px",
    boxShadow: isDark ? "0 2px 10px rgba(0, 0, 0, 0.5)" : "0 2px 10px rgba(0, 0, 0, 0.1)",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
    maxHeight: "100%",
    overflowY: "auto",
  };


  const sectionHeaderStyle: React.CSSProperties = {
    padding: "16px",
    borderBottom: `1px solid ${ui.border}`,
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    cursor: "pointer",
    backgroundColor: ui.sectionBg,
  };

  const sectionTitleStyle: React.CSSProperties = {
    margin: 0,
    fontSize: "12px",
    fontWeight: "bold",
    color: ui.textMuted,
    letterSpacing: "1px",
  };

  const formGroupStyle: React.CSSProperties = {
    padding: "16px 16px 12px",
    display: "flex",
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    borderBottom: "none",
  };

  const labelStyle: React.CSSProperties = {
    fontSize: "14px",
    color: ui.text,
  };

  const colorPickerStyle: React.CSSProperties = {
    appearance: "none",
    width: "120px",
    height: "32px",
    padding: 0,
    border: `1px solid ${ui.border}`,
    borderRadius: "4px",
    cursor: "pointer",
    backgroundColor: ui.panelBg,
  };

  const selectStyle: React.CSSProperties = {
    width: "120px",
    height: "32px",
    padding: "0 8px",
    border: `1px solid ${ui.border}`,
    borderRadius: "4px",
    backgroundColor: ui.panelBg,
    color: ui.text,
    fontSize: "14px",
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    height: "32px",
    padding: "0 8px",
    border: `1px solid ${ui.border}`,
    borderRadius: "4px",
    backgroundColor: ui.panelBg,
    color: ui.text,
    fontSize: "14px",
  };

  const radioGroupStyle: React.CSSProperties = {
    display: "flex",
    gap: "16px",
  };

  const radioLabelStyle: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: "4px",
    fontSize: "14px",
  };

  const fileUploadContainerStyle: React.CSSProperties = {
    display: "flex",
    gap: "8px",
    marginTop: "8px",
  };

  const fileNameStyle: React.CSSProperties = {
    flex: 1,
    fontSize: "12px",
    padding: "4px 8px",
    border: "1px solid #e0e0e0",
    borderRadius: "4px",
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  };

  const buttonStyle: React.CSSProperties = {
    padding: "4px 8px",
    backgroundColor: ui.sectionBg,
    color: ui.text,
    border: `1px solid ${ui.border}`,
    borderRadius: "4px",
    fontSize: "12px",
    cursor: "pointer",
  };

  const actionBarStyle: React.CSSProperties = {
    display: "flex",
    justifyContent: "flex-end",
    gap: "8px",
    padding: "16px",
    borderTop: `1px solid ${ui.border}`,
    marginTop: "auto",
  };

  const cancelButtonStyle: React.CSSProperties = {
    padding: "8px 16px",
    backgroundColor: ui.panelBg,
    color: ui.text,
    border: `1px solid ${ui.border}`,
    borderRadius: "4px",
    fontSize: "14px",
    cursor: "pointer",
  };

  const saveButtonStyle: React.CSSProperties = {
    padding: "8px 16px",
    backgroundColor: isDark ? "#f4f4f5" : "#000",
    color: isDark ? "#18181b" : "#fff",
    border: "none",
    borderRadius: "4px",
    fontSize: "14px",
    cursor: "pointer",
  };

  // Modal styles
  const modalOverlayStyle: React.CSSProperties = {
    position: "fixed",
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: "rgba(0,0,0,0.3)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 2000,
  };

  const modalStyle: React.CSSProperties = {
    width: "520px",
    maxWidth: "90vw",
    backgroundColor: ui.panelBg,
    color: ui.text,
    border: `1px solid ${ui.border}`,
    borderRadius: "12px",
    boxShadow: "0 10px 30px rgba(0,0,0,0.15)",
    overflow: "hidden",
  };

  const modalHeaderStyle: React.CSSProperties = {
    padding: "16px 20px",
    borderBottom: `1px solid ${ui.border}`,
    fontWeight: 600,
  };

  const modalBodyStyle: React.CSSProperties = {
    padding: "16px 20px",
    display: "flex",
    flexDirection: "column",
    gap: "12px",
  };

  const modalFooterStyle: React.CSSProperties = {
    display: "flex",
    justifyContent: "flex-end",
    gap: "8px",
    padding: "12px 20px 16px",
    borderTop: `1px solid ${ui.border}`,
  };

  const pillButtonStyle: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "6px 10px",
    border: `1px solid ${ui.border}`,
    borderRadius: 6,
    backgroundColor: ui.panelBg,
    color: ui.text,
    cursor: "pointer",
    fontSize: 12,
  };

  // Full-width action button style (used for Add Parameter)
  const fullWidthActionButton: React.CSSProperties = {
    display: "flex",
    alignItems: "center",
    gap: 8,
    width: "100%",
    padding: "10px 12px",
    border: `1px solid ${ui.border}`,
    borderRadius: 8,
    backgroundColor: ui.panelBg,
    cursor: "pointer",
    fontSize: 14,
    color: ui.text,
  };

  const smallIconButton: React.CSSProperties = {
    border: `1px solid ${ui.border}`,
    borderRadius: 8,
    width: 28,
    height: 28,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: ui.panelBg,
    color: ui.text,
    cursor: "pointer",
  };

  // Metadata list row aesthetics
  const metaRowStyle: React.CSSProperties = {
    display: "grid",
    gridTemplateColumns: "1fr minmax(90px, 150px) 28px 28px",
    alignItems: "center",
    gap: 8,
    padding: "6px 0",
  };
  const metaNameStyle: React.CSSProperties = {
    fontSize: 13,
    color: ui.text,
    fontWeight: 500,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
  };

  const metaValueStyle: React.CSSProperties = {
    maxWidth: 150,
    overflow: "hidden",
    textOverflow: "ellipsis",
    whiteSpace: "nowrap",
    fontSize: 13,
    color: ui.text,
    border: `1px solid ${ui.border}`,
    borderRadius: 12,
    padding: "6px 10px",
    backgroundColor: ui.sectionBg,
  };
  const metaInputStyle: React.CSSProperties = {
    height: 32,
    padding: "0 8px",
    border: `1px solid ${ui.border}`,
    borderRadius: 8,
    backgroundColor: ui.panelBg,
    color: ui.text,
    fontSize: 13,
    maxWidth: 200,
  };

  const handleAddDraftParam = () => {
    // prevent duplicates by name
    if (!draftParam.name.trim()) return;
    if (params.some((p) => p.name === draftParam.name.trim())) {
      alert("A parameter with this name already exists.");
      return;
    }

    const normalized: MetadataParam = {
      ...draftParam,
      name: draftParam.name.trim(),
      value:
        typeof draftParam.defaultValue !== "undefined"
          ? draftParam.defaultValue
          : draftParam.type === "number"
          ? 0
          : draftParam.type === "boolean"
          ? false
          : "",
    };
    setParams((prev) => [...prev, normalized]);
    setShowAddParamModal(false);
    setDraftParam({
      name: "param_1",
      type: "string",
      description: "",
      required: false,
      defaultValue: "",
      value: "",
    });
  };

  const handleParamValueChange = (
    index: number,
    rawValue: string | boolean
  ) => {
    setParams((prev) => {
      const next = [...prev];
      const p = { ...next[index] };
      if (p.type === "number") {
        const v = typeof rawValue === "string" ? Number(rawValue) : rawValue;
        p.value = isNaN(v as number) ? 0 : (v as number);
      } else if (p.type === "boolean") {
        p.value = typeof rawValue === "boolean" ? rawValue : rawValue === "true";
      } else {
        p.value = String(rawValue);
      }
      next[index] = p;
      return next;
    });
  };

  const handleRemoveParam = (index: number) => {
    setParams((prev) => prev.filter((_, i) => i !== index));
  };

  const openEditParam = (idx: number) => {
    const p = params[idx];
    setEditDraftParam({ ...p });
    setEditParamIndex(idx);
    setShowEditParamModal(true);
  };

  const coerceValueForType = (value: any, type: ParamType) => {
    if (type === "number") {
      const n = typeof value === "number" ? value : Number(value);
      return isNaN(n) ? 0 : n;
    }
    if (type === "boolean") {
      if (typeof value === "boolean") return value;
      const s = String(value).toLowerCase();
      return s === "true" || s === "1" || s === "yes";
    }
    return String(value ?? "");
  };

  const handleUpdateParam = () => {
    if (editParamIndex === null) return;
    const newName = editDraftParam.name.trim();
    if (!newName) return;
    if (params.some((p, i) => i !== editParamIndex && p.name === newName)) {
      alert("A parameter with this name already exists.");
      return;
    }

    setParams((prev) => {
      const next = [...prev];
      const old = next[editParamIndex!];
      const updated: MetadataParam = {
        ...old,
        ...editDraftParam,
      };
      // Ensure value is valid for the selected type
      updated.value = coerceValueForType(old.value, editDraftParam.type);
      next[editParamIndex!] = updated;
      return next;
    });

    setShowEditParamModal(false);
    setEditParamIndex(null);
  };

  return (
    <div style={containerStyle}>
      {/* Light/Dark toggle — mirrors the Genassist platform (toggles the `dark` class
          on <html>) and swaps the chat theme preset so the widget's dark mode is visible. */}
      <button
        type="button"
        onClick={toggleMode}
        aria-label={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"}
        style={{
          position: "fixed",
          top: 20,
          right: 20,
          zIndex: 3000,
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          padding: "8px 14px",
          borderRadius: 999,
          border: `1px solid ${ui.border}`,
          backgroundColor: ui.panelBg,
          color: ui.text,
          fontSize: 13,
          fontWeight: 600,
          cursor: "pointer",
          boxShadow: isDark ? "0 2px 10px rgba(0,0,0,0.5)" : "0 2px 10px rgba(0,0,0,0.12)",
        }}
      >
        {mode === "dark" ? <Sun size={16} /> : <Moon size={16} />}
        <span>{mode === "dark" ? "Light" : "Dark"}</span>
      </button>

      <div style={controlsPanelStyle}>
        {/* Appearance Section */}
        <div style={{ borderBottom: `1px solid ${ui.border}` }}>
          <div
            style={sectionHeaderStyle}
            onClick={() => setShowAppearance(!showAppearance)}
          >
            <h3 style={sectionTitleStyle}>APPEARANCE</h3>
            {showAppearance ? (
              <ChevronUp size={16} />
            ) : (
              <ChevronDown size={16} />
            )}
          </div>

          {showAppearance && (
            <>
              <div style={formGroupStyle}>
                <label style={labelStyle}>Primary Color</label>
                <input
                  type="color"
                  value={theme.primaryColor}
                  onChange={(e) =>
                    handleColorChange("primaryColor", e.target.value)
                  }
                  style={colorPickerStyle}
                />
              </div>

              <div style={formGroupStyle}>
                <label style={labelStyle}>Secondary Color</label>
                <input
                  type="color"
                  value={theme.secondaryColor}
                  onChange={(e) =>
                    handleColorChange("secondaryColor", e.target.value)
                  }
                  style={colorPickerStyle}
                />
              </div>

              <div style={formGroupStyle}>
                <label style={labelStyle}>Background Color</label>
                <input
                  type="color"
                  value={theme.backgroundColor}
                  onChange={(e) =>
                    handleColorChange("backgroundColor", e.target.value)
                  }
                  style={colorPickerStyle}
                />
              </div>

              <div style={formGroupStyle}>
                <label style={labelStyle}>Text Color</label>
                <input
                  type="color"
                  value={theme.textColor}
                  onChange={(e) =>
                    handleColorChange("textColor", e.target.value)
                  }
                  style={colorPickerStyle}
                />
              </div>

              <div style={formGroupStyle}>
                <label style={labelStyle}>User Bubble Color</label>
                <input
                  type="color"
                  value={theme.userBubbleColor}
                  onChange={(e) =>
                    handleColorChange("userBubbleColor", e.target.value)
                  }
                  style={colorPickerStyle}
                />
              </div>

              <div style={formGroupStyle}>
                <label style={labelStyle}>Input Background</label>
                <input
                  type="color"
                  value={theme.inputBackgroundColor}
                  onChange={(e) =>
                    handleColorChange("inputBackgroundColor", e.target.value)
                  }
                  style={colorPickerStyle}
                />
              </div>

              <div style={formGroupStyle}>
                <label style={labelStyle}>Border Color</label>
                <input
                  type="color"
                  value={theme.borderColor}
                  onChange={(e) =>
                    handleColorChange("borderColor", e.target.value)
                  }
                  style={colorPickerStyle}
                />
              </div>

              <div style={formGroupStyle}>
                <label style={labelStyle}>Muted Text Color</label>
                <input
                  type="color"
                  value={theme.mutedTextColor}
                  onChange={(e) =>
                    handleColorChange("mutedTextColor", e.target.value)
                  }
                  style={colorPickerStyle}
                />
              </div>

              <div style={formGroupStyle}>
                <label style={labelStyle}>Font Size</label>
                <select
                  style={selectStyle}
                  value={theme.fontSize}
                  onChange={(e) =>
                    handleColorChange("fontSize", e.target.value)
                  }
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
                  value={theme.fontFamily.split(",")[0].trim()}
                  onChange={(e) => {
                    const value = e.target.value;
                    const fontFamily =
                      value === "Inter"
                        ? "Inter, sans-serif"
                        : value === "Arial"
                        ? "Arial, sans-serif"
                        : value === "Times New Roman"
                        ? "'Times New Roman', serif"
                        : "monospace";
                    handleColorChange("fontFamily", fontFamily);
                  }}
                >
                  <option value="Inter">Inter</option>
                  <option value="Arial">Arial</option>
                  <option value="Times New Roman">Times New Roman</option>
                  <option value="monospace">Monospace</option>
                </select>
              </div>

              <div
                style={{
                  ...formGroupStyle,
                  flexDirection: "column",
                  alignItems: "flex-start",
                }}
              >
                <label style={{ ...labelStyle, marginBottom: "8px" }}>
                  Logo (SVG)
                </label>
                <div style={radioGroupStyle}>
                  <label style={radioLabelStyle}>
                    <input
                      type="radio"
                      checked={!customLogo.useCustom}
                      onChange={() => handleLogoChange(false)}
                    />
                    Default
                  </label>
                  <label style={radioLabelStyle}>
                    <input
                      type="radio"
                      checked={customLogo.useCustom}
                      onChange={() => handleLogoChange(true)}
                    />
                    Custom
                  </label>
                </div>
                {customLogo.useCustom && (
                  <div style={fileUploadContainerStyle}>
                    <div style={fileNameStyle}>
                      {customLogo.file ? customLogo.file.name : "file.svg"}
                    </div>
                    <label style={buttonStyle}>
                      Browse...
                      <input
                        type="file"
                        accept=".svg"
                        style={{ display: "none" }}
                        onChange={(e) => handleFileUpload("logo", e)}
                      />
                    </label>
                  </div>
                )}
              </div>

              <div
                style={{
                  ...formGroupStyle,
                  flexDirection: "column",
                  alignItems: "flex-start",
                  paddingBottom: "16px",
                }}
              >
                <label style={{ ...labelStyle, marginBottom: "8px" }}>
                  Bubble Icon (SVG)
                </label>
                <div style={radioGroupStyle}>
                  <label style={radioLabelStyle}>
                    <input
                      type="radio"
                      checked={!customBubbleIcon.useCustom}
                      onChange={() => handleBubbleIconChange(false)}
                    />
                    Default
                  </label>
                  <label style={radioLabelStyle}>
                    <input
                      type="radio"
                      checked={customBubbleIcon.useCustom}
                      onChange={() => handleBubbleIconChange(true)}
                    />
                    Custom
                  </label>
                </div>
                {customBubbleIcon.useCustom && (
                  <div style={fileUploadContainerStyle}>
                    <div style={fileNameStyle}>
                      {customBubbleIcon.file
                        ? customBubbleIcon.file.name
                        : "file.svg"}
                    </div>
                    <label style={buttonStyle}>
                      Browse...
                      <input
                        type="file"
                        accept=".svg"
                        style={{ display: "none" }}
                        onChange={(e) => handleFileUpload("bubbleIcon", e)}
                      />
                    </label>
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Settings Section */}
        <div>
          <div
            style={sectionHeaderStyle}
            onClick={() => setShowSettings(!showSettings)}
          >
            <h3 style={sectionTitleStyle}>SETTINGS</h3>
            {showSettings ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>

      {showSettings && (
        <>
              <div style={{ padding: "16px 16px 12px", borderBottom: "none" }}>
                <label
                  style={{
                    ...labelStyle,
                    display: "block",
                    marginBottom: "8px",
                  }}
                >
                  Name
                </label>
                <input
                  type="text"
                  style={{
                    width: "100%",
                    height: "40px",
                    padding: "0 12px",
                    border: "1px solid #e0e0e0",
                    borderRadius: "4px",
                    fontSize: "14px",
                    boxSizing: "border-box",
                  }}
                  value={chatSettings.name}
                  onChange={(e) => handleSettingChange("name", e.target.value)}
                />
              </div>

              <div style={{ padding: "0 16px 12px", borderBottom: "none" }}>
                <label
                  style={{
                    ...labelStyle,
                    display: "block",
                    marginBottom: "8px",
                  }}
                >
                  Description
                </label>
                <input
                  type="text"
                  style={{
                    width: "100%",
                    height: "40px",
                    padding: "0 12px",
                    border: "1px solid #e0e0e0",
                    borderRadius: "4px",
                    fontSize: "14px",
                    boxSizing: "border-box",
                  }}
                  value={chatSettings.description}
                  onChange={(e) =>
                    handleSettingChange("description", e.target.value)
                  }
                />
              </div>

              <div style={{ padding: "0 16px 12px", borderBottom: "none" }}>
                <label
                  style={{
                    ...labelStyle,
                    display: "block",
                    marginBottom: "8px",
                  }}
                >
                  Agent Name
                </label>
                <input
                  type="text"
                  style={{
                    width: "100%",
                    height: "40px",
                    padding: "0 12px",
                    border: "1px solid #e0e0e0",
                    borderRadius: "4px",
                    fontSize: "14px",
                    boxSizing: "border-box",
                  }}
                  value={chatSettings.agentName}
                  onChange={(e) =>
                    handleSettingChange("agentName", e.target.value)
                  }
                />
              </div>
              <div style={{ padding: "0 16px 12px" }}>
                <label
                  style={{
                    ...labelStyle,
                    display: "block",
                    marginBottom: "8px",
                  }}
                >
                  Logo URL
                </label>
                <input
                  type="text"
                  style={{
                    width: "100%",
                    height: "40px",
                    padding: "0 12px",
                    border: "1px solid #e0e0e0",
                    borderRadius: "4px",
                    fontSize: "14px",
                    boxSizing: "border-box",
                  }}
                  value={chatSettings.logoUrl || ""}
                  onChange={(e) =>
                    handleSettingChange("logoUrl", e.target.value)
                  }
                  placeholder="https://example.com/logo.png"
                />
              </div>
              <div style={{ padding: "0 16px 16px", borderBottom: "none" }}>
                <label
                  style={{
                    ...labelStyle,
                    display: "block",
                    marginBottom: "8px",
                  }}
                >
                  Full Logo URL
                </label>
                <input
                  type="text"
                  style={{
                    width: "100%",
                    height: "40px",
                    padding: "0 12px",
                    border: "1px solid #e0e0e0",
                    borderRadius: "4px",
                    fontSize: "14px",
                    boxSizing: "border-box",
                  }}
                  value={chatSettings.brandLogoUrl || ""}
                  onChange={(e) =>
                    handleSettingChange("brandLogoUrl", e.target.value)
                  }
                  placeholder="https://example.com/full-logo.png"
                />
                <div style={{ fontSize: 11, color: "#888", marginTop: 6 }}>
                  When set, replaces the small logo + name with this full logo.
                </div>
              </div>
              <div style={{ padding: "16px", borderTop: `1px solid ${ui.border}`, marginTop: 8 }}>
                <div style={{ fontSize: 13, color: "#555", marginBottom: 12, fontWeight: 500 }}>
                  Features
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Use Audio</label>
                  <input
                    type="checkbox"
                    checked={featureFlags.useAudio}
                    onChange={(e) => handleFeatureFlagChange("useAudio", e.target.checked)}
                    style={{ width: 20, height: 20, cursor: "pointer" }}
                  />
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Use File</label>
                  <input
                    type="checkbox"
                    checked={featureFlags.useFile}
                    onChange={(e) => handleFeatureFlagChange("useFile", e.target.checked)}
                    style={{ width: 20, height: 20, cursor: "pointer" }}
                  />
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Use WebSocket</label>
                  <input
                    type="checkbox"
                    checked={featureFlags.useWs}
                    onChange={(e) => handleFeatureFlagChange("useWs", e.target.checked)}
                    style={{ width: 20, height: 20, cursor: "pointer" }}
                  />
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Use Heartbeat Polling</label>
                  <input
                    type="checkbox"
                    checked={featureFlags.usePoll}
                    onChange={(e) => handleFeatureFlagChange("usePoll", e.target.checked)}
                    style={{ width: 20, height: 20, cursor: "pointer" }}
                  />
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Quick Message Input</label>
                  <input
                    type="checkbox"
                    checked={!!featureFlags.quickInput}
                    onChange={(e) => handleFeatureFlagChange("quickInput", e.target.checked)}
                    style={{ width: 20, height: 20, cursor: "pointer" }}
                  />
                </div>
                <div style={formGroupStyle}>
                  <label style={labelStyle}>Chat Mode</label>
                  <select
                    style={selectStyle}
                    value={chatMode}
                    onChange={(e) => setChatMode(e.target.value as "floating" | "inputbar" | "embedded")}
                  >
                    <option value="floating">Floating</option>
                    <option value="inputbar">Input Bar</option>
                    <option value="embedded">Embedded</option>
                  </select>
                </div>
              </div>
        </>
      )}
    </div>

        {/* Metadata Section */}
        <div>
          <div
            style={sectionHeaderStyle}
            onClick={() => setShowMetadata(!showMetadata)}
          >
            <h3 style={sectionTitleStyle}>METADATA</h3>
            {showMetadata ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          </div>

          {showMetadata && (
            <>
              <div style={{ padding: "12px 16px" }}>
                <div style={{ fontSize: 13, color: "#555", marginBottom: 10 }}>
                  Define key/value parameters sent as chat metadata.
                </div>
                <button style={fullWidthActionButton} onClick={() => setShowAddParamModal(true)}>
                  <Plus size={18} />
                  <span>Add Parameter</span>
                </button>
              </div>

              {/* Parameters list */}
              {params.length > 0 && (
                <div style={{ padding: "2px 16px 12px", display: "flex", flexDirection: "column", gap: 6 }}>
                  {params.map((p, idx) => {
                    const displayVal = p.type === "boolean" ? (p.value ? "True" : "False") : String(p.value ?? "");
                    return (
                      <div key={p.name} style={metaRowStyle}>
                        <div style={metaNameStyle}>{p.name}</div>
                        <div style={metaValueStyle} title={displayVal}>{displayVal}</div>
                        <button
                          title="Edit"
                          style={smallIconButton}
                          onClick={() => openEditParam(idx)}
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
          <button style={cancelButtonStyle}>Cancel</button>
          <button style={saveButtonStyle} onClick={handleSaveChanges}>
            Save Changes
          </button>
        </div>
      </div>

      {/* Chat Widget */}
      {(() => {
        const chatWidget = (
          <GenAgentChat
            baseUrl={chatSettings.baseUrl}
            websocketUrl={chatSettings.websocketUrl}
            apiKey={chatSettings.apiKey}
            tenant={chatSettings.tenant || undefined}
            metadata={metadata}
            theme={theme}
            useAudio={featureFlags.useAudio}
            useFile={featureFlags.useFile}
            headerTitle={chatSettings.name}
            description={chatSettings.description}
            agentName={chatSettings.agentName}
            logoUrl={chatSettings.logoUrl}
            brandLogoUrl={chatSettings.brandLogoUrl}
            useWs={featureFlags.useWs}
            usePoll={featureFlags.usePoll}
            quickInput={featureFlags.quickInput}
            serverUnavailableMessage="Support is currently offline. Please try again later or contact us."
            serverUnavailableContactUrl="https://www.ritech.co/"
            serverUnavailableContactLabel="Contact Support"
            onError={handleError}
            mode={chatMode}
            floatingConfig={{
              position: "bottom-right",
              offset: { x: 20, y: 20 },
            }}
            onConfigLoaded={({ chatInputMetadata }: { chatInputMetadata?: any }) => {
              const next = (chatInputMetadata && typeof chatInputMetadata === "object" && !Array.isArray(chatInputMetadata))
                ? (chatInputMetadata as Record<string, any>)
                : {};
              setAgentChatInputMetadata(next);
              try {
                localStorage.setItem(
                  `genassist_agent_chat_input_metadata:${chatSettings.apiKey}`,
                  JSON.stringify(next)
                );
              } catch {
                // ignore
              }
            }}
          />
        );

        // The input-bar variant docks itself to the bottom-center of the viewport
        // (fixed positioning) — no wrapper needed. Embedded gets a sized box.
        if (chatMode === "embedded") {
          return (
            <div style={{ position: "fixed", right: 24, bottom: 24, width: 384, height: 620, zIndex: 1000 }}>
              {chatWidget}
            </div>
          );
        }
        return chatWidget;
      })()}

      {/* Add Parameter Modal */}
      {showAddParamModal && (
        <div style={modalOverlayStyle}>
          <div style={modalStyle}>
            <div style={modalHeaderStyle}>Add Parameter</div>
            <div style={modalBodyStyle}>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ fontSize: 12, color: "#777" }}>Parameter Name</label>
                <input
                  type="text"
                  style={inputStyle}
                  value={draftParam.name}
                  onChange={(e) => setDraftParam((d) => ({ ...d, name: e.target.value }))}
                  placeholder="param_1"
                />
              </div>

              <div style={{ display: "flex", gap: 12 }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
                  <label style={{ fontSize: 12, color: "#777" }}>Type</label>
                  <select
                    style={selectStyle}
                    value={draftParam.type}
                    onChange={(e) =>
                      setDraftParam((d) => ({ ...d, type: e.target.value as ParamType, defaultValue: e.target.value === "boolean" ? false : e.target.value === "number" ? 0 : "" }))
                    }
                  >
                    <option value="string">String</option>
                    <option value="number">Number</option>
                    <option value="boolean">Boolean</option>
                  </select>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
                  <label style={{ fontSize: 12, color: "#777" }}>Required</label>
                  <select
                    style={selectStyle}
                    value={draftParam.required ? "yes" : "no"}
                    onChange={(e) => setDraftParam((d) => ({ ...d, required: e.target.value === "yes" }))}
                  >
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ fontSize: 12, color: "#777" }}>Description</label>
                <input
                  type="text"
                  style={inputStyle}
                  value={draftParam.description}
                  onChange={(e) => setDraftParam((d) => ({ ...d, description: e.target.value }))}
                  placeholder="Parameter description"
                />
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ fontSize: 12, color: "#777" }}>Default Value</label>
                {draftParam.type === "boolean" ? (
                  <select
                    style={selectStyle}
                    value={String(draftParam.defaultValue)}
                    onChange={(e) => setDraftParam((d) => ({ ...d, defaultValue: e.target.value === "true" }))}
                  >
                    <option value="true">True</option>
                    <option value="false">False</option>
                  </select>
                ) : (
                  <input
                    type={draftParam.type === "number" ? "number" : "text"}
                    style={inputStyle}
                    value={draftParam.defaultValue as any}
                    onChange={(e) =>
                      setDraftParam((d) => ({
                        ...d,
                        defaultValue:
                          draftParam.type === "number" ? Number(e.target.value) : e.target.value,
                      }))
                    }
                    placeholder="Default value (optional)"
                  />
                )}
              </div>
            </div>
            <div style={modalFooterStyle}>
              <button style={cancelButtonStyle} onClick={() => setShowAddParamModal(false)}>
                Cancel
              </button>
              <button style={saveButtonStyle} onClick={handleAddDraftParam}>
                Add Parameter
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Edit Parameter Modal */}
      {showEditParamModal && (
        <div style={modalOverlayStyle}>
          <div style={modalStyle}>
            <div style={modalHeaderStyle}>Edit Parameter</div>
            <div style={modalBodyStyle}>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ fontSize: 12, color: "#777" }}>Parameter Name</label>
                <input
                  type="text"
                  style={inputStyle}
                  value={editDraftParam.name}
                  onChange={(e) => setEditDraftParam((d) => ({ ...d, name: e.target.value }))}
                />
              </div>

              <div style={{ display: "flex", gap: 12 }}>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
                  <label style={{ fontSize: 12, color: "#777" }}>Type</label>
                  <select
                    style={selectStyle}
                    value={editDraftParam.type}
                    onChange={(e) => {
                      const newType = e.target.value as ParamType;
                      setEditDraftParam((d) => ({
                        ...d,
                        type: newType,
                        defaultValue:
                          newType === "boolean" ? false : newType === "number" ? 0 : "",
                      }));
                    }}
                  >
                    <option value="string">String</option>
                    <option value="number">Number</option>
                    <option value="boolean">Boolean</option>
                  </select>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 6, flex: 1 }}>
                  <label style={{ fontSize: 12, color: "#777" }}>Required</label>
                  <select
                    style={selectStyle}
                    value={editDraftParam.required ? "yes" : "no"}
                    onChange={(e) => setEditDraftParam((d) => ({ ...d, required: e.target.value === "yes" }))}
                  >
                    <option value="no">No</option>
                    <option value="yes">Yes</option>
                  </select>
                </div>
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ fontSize: 12, color: "#777" }}>Description</label>
                <input
                  type="text"
                  style={inputStyle}
                  value={editDraftParam.description}
                  onChange={(e) => setEditDraftParam((d) => ({ ...d, description: e.target.value }))}
                />
              </div>

              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <label style={{ fontSize: 12, color: "#777" }}>Default Value</label>
                {editDraftParam.type === "boolean" ? (
                  <select
                    style={selectStyle}
                    value={String(editDraftParam.defaultValue)}
                    onChange={(e) => setEditDraftParam((d) => ({ ...d, defaultValue: e.target.value === "true" }))}
                  >
                    <option value="true">True</option>
                    <option value="false">False</option>
                  </select>
                ) : (
                  <input
                    type={editDraftParam.type === "number" ? "number" : "text"}
                    style={inputStyle}
                    value={editDraftParam.defaultValue as any}
                    onChange={(e) =>
                      setEditDraftParam((d) => ({
                        ...d,
                        defaultValue:
                          editDraftParam.type === "number" ? Number(e.target.value) : e.target.value,
                      }))
                    }
                  />
                )}
              </div>
            </div>
            <div style={modalFooterStyle}>
              <button style={cancelButtonStyle} onClick={() => { setShowEditParamModal(false); setEditParamIndex(null); }}>
                Cancel
              </button>
              <button style={saveButtonStyle} onClick={handleUpdateParam}>
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
