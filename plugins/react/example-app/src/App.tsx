import React, { useMemo, useState, useCallback } from "react";
import { GenAgentChat } from "../../src";
import {
  ChevronDown,
  ChevronUp,
  Plus,
  Trash2,
  Pencil,
} from "lucide-react";

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

  const [theme, setTheme] = useState({
    primaryColor: "#4F46E5",
    secondaryColor: "#f5f5f5",
    backgroundColor: "#ffffff",
    textColor: "#000000",
    fontFamily: "Inter, sans-serif",
    fontSize: "15px",
  });

  const [chatSettings, setChatSettings] = useState({
    name: "Genassist Support",
    description: "Support",
    agentName: "Agent",
    logoUrl: "",
    baseUrl: "http://localhost:8000/",
    apiKey: "genagent123",
    // reCaptchaKey: "xx-yy-zz",
  });

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
    // Here you would typically save the settings to a server
    alert("Changes saved!");
  };

  // Memoize callbacks to prevent unnecessary re-renders of GenAgentChat
  const handleError = useCallback(() => {}, []);

  const containerStyle: React.CSSProperties = {
    display: "flex",
    padding: "20px",
    gap: "20px",
    height: "100vh",
    boxSizing: "border-box",
    fontFamily: "Inter, sans-serif",
    position: "relative",
  };

  const controlsPanelStyle: React.CSSProperties = {
    flex: "1",
    maxWidth: "300px",
    backgroundColor: "#ffffff",
    borderRadius: "8px",
    boxShadow: "0 2px 10px rgba(0, 0, 0, 0.1)",
    overflow: "hidden",
    display: "flex",
    flexDirection: "column",
  };


  const sectionHeaderStyle: React.CSSProperties = {
    padding: "16px",
    borderBottom: "1px solid #e0e0e0",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    cursor: "pointer",
    backgroundColor: "#f9f9f9",
  };

  const sectionTitleStyle: React.CSSProperties = {
    margin: 0,
    fontSize: "12px",
    fontWeight: "bold",
    color: "#666",
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
    color: "#333",
  };

  const colorPickerStyle: React.CSSProperties = {
    appearance: "none",
    width: "120px",
    height: "32px",
    padding: 0,
    border: "1px solid #e0e0e0",
    borderRadius: "4px",
    cursor: "pointer",
  };

  const selectStyle: React.CSSProperties = {
    width: "120px",
    height: "32px",
    padding: "0 8px",
    border: "1px solid #e0e0e0",
    borderRadius: "4px",
    backgroundColor: "#fff",
    fontSize: "14px",
  };

  const inputStyle: React.CSSProperties = {
    width: "100%",
    height: "32px",
    padding: "0 8px",
    border: "1px solid #e0e0e0",
    borderRadius: "4px",
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
    backgroundColor: "#f5f5f5",
    border: "1px solid #e0e0e0",
    borderRadius: "4px",
    fontSize: "12px",
    cursor: "pointer",
  };

  const actionBarStyle: React.CSSProperties = {
    display: "flex",
    justifyContent: "flex-end",
    gap: "8px",
    padding: "16px",
    borderTop: "1px solid #e0e0e0",
    marginTop: "auto",
  };

  const cancelButtonStyle: React.CSSProperties = {
    padding: "8px 16px",
    backgroundColor: "#fff",
    border: "1px solid #e0e0e0",
    borderRadius: "4px",
    fontSize: "14px",
    cursor: "pointer",
  };

  const saveButtonStyle: React.CSSProperties = {
    padding: "8px 16px",
    backgroundColor: "#000",
    color: "#fff",
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
    backgroundColor: "#fff",
    borderRadius: "12px",
    boxShadow: "0 10px 30px rgba(0,0,0,0.15)",
    overflow: "hidden",
  };

  const modalHeaderStyle: React.CSSProperties = {
    padding: "16px 20px",
    borderBottom: "1px solid #eee",
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
    borderTop: "1px solid #eee",
  };

  const pillButtonStyle: React.CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "6px 10px",
    border: "1px solid #e0e0e0",
    borderRadius: 6,
    backgroundColor: "#fff",
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
    border: "1px solid #e0e0e0",
    borderRadius: 8,
    backgroundColor: "#fff",
    cursor: "pointer",
    fontSize: 14,
    color: "#111",
  };

  const smallIconButton: React.CSSProperties = {
    border: "1px solid #e0e0e0",
    borderRadius: 8,
    width: 28,
    height: 28,
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: "#fff",
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
    color: "#222",
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
    color: "#111",
    border: "1px solid #e6e6e6",
    borderRadius: 12,
    padding: "6px 10px",
    backgroundColor: "#fafafa",
  };
  const metaInputStyle: React.CSSProperties = {
    height: 32,
    padding: "0 8px",
    border: "1px solid #e0e0e0",
    borderRadius: 8,
    backgroundColor: "#fff",
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
      <div style={controlsPanelStyle}>
        {/* Appearance Section */}
        <div style={{ borderBottom: "1px solid #e0e0e0" }}>
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
              <div style={{ padding: "0 16px 16px", borderBottom: "none" }}>
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

      {/* Chat Widget - Floating Mode */}
      <GenAgentChat
        baseUrl={chatSettings.baseUrl}
        apiKey={chatSettings.apiKey}
        tenant=""
        metadata={metadata}
        theme={theme}
        useAudio={true}
        useFile={true}
        headerTitle={chatSettings.name}
        agentName={chatSettings.agentName}
        logoUrl={chatSettings.logoUrl}
        useWs={true}
        onError={handleError}
        mode="floating"
        floatingConfig={{
          position: "bottom-right",
          offset: { x: 20, y: 20 },
        }}
      />

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
