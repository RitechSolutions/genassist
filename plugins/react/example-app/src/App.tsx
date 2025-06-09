import React, { useState } from 'react';
import { GenAgentChat } from '../../dist';
import { ChevronDown, ChevronUp, MessageSquareMore, X } from 'lucide-react';

interface FileState {
  useCustom: boolean;
  file: File | null;
}

function App() {
  const [theme, setTheme] = useState({
    primaryColor: '#2563EB',
    secondaryColor: '#f5f5f5',
    backgroundColor: '#ffffff',
    textColor: '#000000',
    fontFamily: 'Inter, sans-serif',
    fontSize: '15px',
  });

  const [chatSettings, setChatSettings] = useState({
    name: 'Genassist',
    description: 'Support'
  });

  const [customLogo, setCustomLogo] = useState<FileState>({
    useCustom: false,
    file: null
  });

  const [customBubbleIcon, setCustomBubbleIcon] = useState<FileState>({
    useCustom: false,
    file: null
  });

  const [showAppearance, setShowAppearance] = useState(true);
  const [showSettings, setShowSettings] = useState(false);
  const [showChat, setShowChat] = useState(false);

  const userData = {
    userId: 'user-123',
    name: 'John Doe',
    email: 'john@example.com',
    role: 'customer',
  };

  const handleColorChange = (property: string, value: string) => {
    setTheme(prevTheme => ({
      ...prevTheme,
      [property]: value
    }));
  };

  const handleSettingChange = (property: string, value: string) => {
    setChatSettings(prevSettings => ({
      ...prevSettings,
      [property]: value
    }));
  };

  const handleLogoChange = (useCustom: boolean) => {
    setCustomLogo({
      ...customLogo,
      useCustom
    });
  };

  const handleBubbleIconChange = (useCustom: boolean) => {
    setCustomBubbleIcon({
      ...customBubbleIcon,
      useCustom
    });
  };

  const handleFileUpload = (type: 'logo' | 'bubbleIcon', event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.files && event.target.files[0]) {
      if (type === 'logo') {
        setCustomLogo({
          useCustom: true,
          file: event.target.files[0]
        });
      } else {
        setCustomBubbleIcon({
          useCustom: true,
          file: event.target.files[0]
        });
      }
    }
  };

  const handleSaveChanges = () => {
    // Here you would typically save the settings to a server
    alert('Changes saved!');
  };

  const toggleChat = () => {
    setShowChat(!showChat);
  };

  const containerStyle: React.CSSProperties = {
    display: 'flex',
    padding: '20px',
    gap: '20px',
    height: '100vh',
    boxSizing: 'border-box',
    fontFamily: 'Inter, sans-serif',
    position: 'relative'
  };

  const controlsPanelStyle: React.CSSProperties = {
    flex: '1',
    maxWidth: '300px',
    backgroundColor: '#ffffff',
    borderRadius: '8px',
    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
    overflow: 'hidden',
    display: 'flex',
    flexDirection: 'column'
  };

  const chatContainerStyle: React.CSSProperties = {
    flex: '1',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'flex-start',
    padding: '20px'
  };

  const chatBubbleStyle: React.CSSProperties = {
    position: 'fixed',
    bottom: '20px',
    right: '20px',
    width: '60px',
    height: '60px',
    borderRadius: '50%',
    backgroundColor: theme.primaryColor,
    color: '#ffffff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    boxShadow: '0 4px 12px rgba(0, 0, 0, 0.15)',
    zIndex: 1000
  };

  const chatWidgetStyle: React.CSSProperties = {
    position: 'fixed',
    bottom: '100px',
    right: '20px',
    width: '400px',
    height: '600px',
    borderRadius: '8px',
    boxShadow: '0 4px 20px rgba(0, 0, 0, 0.2)',
    backgroundColor: '#ffffff',
    overflow: 'hidden',
    zIndex: 999,
    display: showChat ? 'block' : 'none'
  };

  const chatWidgetHeaderStyle: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '10px 15px',
    backgroundColor: theme.primaryColor,
    color: '#ffffff'
  };

  const closeButtonStyle: React.CSSProperties = {
    background: 'none',
    border: 'none',
    color: '#ffffff',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    padding: '4px'
  };

  const sectionHeaderStyle: React.CSSProperties = {
    padding: '16px',
    borderBottom: '1px solid #e0e0e0',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    cursor: 'pointer',
    backgroundColor: '#f9f9f9'
  };

  const sectionTitleStyle: React.CSSProperties = {
    margin: 0,
    fontSize: '12px',
    fontWeight: 'bold',
    color: '#666',
    letterSpacing: '1px'
  };

  const formGroupStyle: React.CSSProperties = {
    padding: '16px 16px 12px',
    display: 'flex',
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    borderBottom: 'none'
  };

  const labelStyle: React.CSSProperties = {
    fontSize: '14px',
    color: '#333'
  };

  const colorPickerStyle: React.CSSProperties = {
    appearance: 'none',
    width: '120px',
    height: '32px',
    padding: 0,
    border: '1px solid #e0e0e0',
    borderRadius: '4px',
    cursor: 'pointer'
  };

  const selectStyle: React.CSSProperties = {
    width: '120px',
    height: '32px',
    padding: '0 8px',
    border: '1px solid #e0e0e0',
    borderRadius: '4px',
    backgroundColor: '#fff',
    fontSize: '14px'
  };

  const inputStyle: React.CSSProperties = {
    width: '100%',
    height: '32px',
    padding: '0 8px',
    border: '1px solid #e0e0e0',
    borderRadius: '4px',
    fontSize: '14px'
  };

  const radioGroupStyle: React.CSSProperties = {
    display: 'flex',
    gap: '16px'
  };

  const radioLabelStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '4px',
    fontSize: '14px'
  };

  const fileUploadContainerStyle: React.CSSProperties = {
    display: 'flex',
    gap: '8px',
    marginTop: '8px'
  };

  const fileNameStyle: React.CSSProperties = {
    flex: 1,
    fontSize: '12px',
    padding: '4px 8px',
    border: '1px solid #e0e0e0',
    borderRadius: '4px',
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap'
  };

  const buttonStyle: React.CSSProperties = {
    padding: '4px 8px',
    backgroundColor: '#f5f5f5',
    border: '1px solid #e0e0e0',
    borderRadius: '4px',
    fontSize: '12px',
    cursor: 'pointer'
  };

  const actionBarStyle: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '8px',
    padding: '16px',
    borderTop: '1px solid #e0e0e0',
    marginTop: 'auto'
  };

  const cancelButtonStyle: React.CSSProperties = {
    padding: '8px 16px',
    backgroundColor: '#fff',
    border: '1px solid #e0e0e0',
    borderRadius: '4px',
    fontSize: '14px',
    cursor: 'pointer'
  };

  const saveButtonStyle: React.CSSProperties = {
    padding: '8px 16px',
    backgroundColor: '#000',
    color: '#fff',
    border: 'none',
    borderRadius: '4px',
    fontSize: '14px',
    cursor: 'pointer'
  };

  return (
    <div style={containerStyle}>
      <div style={controlsPanelStyle}>
        {/* Appearance Section */}
        <div style={{borderBottom: '1px solid #e0e0e0'}}>
          <div 
            style={sectionHeaderStyle} 
            onClick={() => setShowAppearance(!showAppearance)}
          >
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
                  onChange={(e) => handleColorChange('primaryColor', e.target.value)} 
                  style={colorPickerStyle}
                />
              </div>
              
              <div style={formGroupStyle}>
                <label style={labelStyle}>Secondary Color</label>
                <input 
                  type="color" 
                  value={theme.secondaryColor} 
                  onChange={(e) => handleColorChange('secondaryColor', e.target.value)} 
                  style={colorPickerStyle}
                />
              </div>
              
              <div style={formGroupStyle}>
                <label style={labelStyle}>Background Color</label>
                <input 
                  type="color" 
                  value={theme.backgroundColor} 
                  onChange={(e) => handleColorChange('backgroundColor', e.target.value)} 
                  style={colorPickerStyle}
                />
              </div>
              
              <div style={formGroupStyle}>
                <label style={labelStyle}>Text Color</label>
                <input 
                  type="color" 
                  value={theme.textColor} 
                  onChange={(e) => handleColorChange('textColor', e.target.value)} 
                  style={colorPickerStyle}
                />
              </div>
              
              <div style={formGroupStyle}>
                <label style={labelStyle}>Font Size</label>
                <select 
                  style={selectStyle}
                  value={theme.fontSize}
                  onChange={(e) => handleColorChange('fontSize', e.target.value)}
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
                    const value = e.target.value;
                    const fontFamily = value === 'Inter' 
                      ? 'Inter, sans-serif' 
                      : value === 'Arial' 
                        ? 'Arial, sans-serif' 
                        : value === 'Times New Roman' 
                          ? "'Times New Roman', serif" 
                          : 'monospace';
                    handleColorChange('fontFamily', fontFamily);
                  }}
                >
                  <option value="Inter">Inter</option>
                  <option value="Arial">Arial</option>
                  <option value="Times New Roman">Times New Roman</option>
                  <option value="monospace">Monospace</option>
                </select>
              </div>
              
              <div style={{...formGroupStyle, flexDirection: 'column', alignItems: 'flex-start'}}>
                <label style={{...labelStyle, marginBottom: '8px'}}>Logo (SVG)</label>
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
                      {customLogo.file ? customLogo.file.name : 'file.svg'}
                    </div>
                    <label style={buttonStyle}>
                      Browse...
                      <input 
                        type="file" 
                        accept=".svg" 
                        style={{display: 'none'}} 
                        onChange={(e) => handleFileUpload('logo', e)}
                      />
                    </label>
                  </div>
                )}
              </div>
              
              <div style={{...formGroupStyle, flexDirection: 'column', alignItems: 'flex-start', paddingBottom: '16px'}}>
                <label style={{...labelStyle, marginBottom: '8px'}}>Bubble Icon (SVG)</label>
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
                      {customBubbleIcon.file ? customBubbleIcon.file.name : 'file.svg'}
                    </div>
                    <label style={buttonStyle}>
                      Browse...
                      <input 
                        type="file" 
                        accept=".svg" 
                        style={{display: 'none'}} 
                        onChange={(e) => handleFileUpload('bubbleIcon', e)}
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
              <div style={{padding: '16px 16px 12px', borderBottom: 'none'}}>
                <label style={{...labelStyle, display: 'block', marginBottom: '8px'}}>Name</label>
                <input 
                  type="text"
                  style={{
                    width: '100%',
                    height: '40px',
                    padding: '0 12px',
                    border: '1px solid #e0e0e0',
                    borderRadius: '4px',
                    fontSize: '14px',
                    boxSizing: 'border-box'
                  }}
                  value={chatSettings.name}
                  onChange={(e) => handleSettingChange('name', e.target.value)}
                />
              </div>
              
              <div style={{padding: '0 16px 16px', borderBottom: 'none'}}>
                <label style={{...labelStyle, display: 'block', marginBottom: '8px'}}>Description</label>
                <input 
                  type="text"
                  style={{
                    width: '100%',
                    height: '40px',
                    padding: '0 12px',
                    border: '1px solid #e0e0e0',
                    borderRadius: '4px',
                    fontSize: '14px',
                    boxSizing: 'border-box'
                  }}
                  value={chatSettings.description}
                  onChange={(e) => handleSettingChange('description', e.target.value)}
                />
              </div>
            </>
          )}
        </div>
        
        {/* Action Buttons */}
        <div style={actionBarStyle}>
          <button style={cancelButtonStyle}>Cancel</button>
          <button style={saveButtonStyle} onClick={handleSaveChanges}>Save Changes</button>
        </div>
      </div>

      {/* Chat Widget Bubble */}
      <div style={chatBubbleStyle} onClick={toggleChat}>
        {showChat ? <X size={24} /> : <MessageSquareMore size={24} />}
      </div>

      {/* Chat Widget Popup */}
      <div style={chatWidgetStyle}>
        <GenAgentChat 
          baseUrl="http://localhost:8000/" 
          apiKey="agent123"
          userData={userData}
          theme={theme}
          headerTitle={chatSettings.name}
          placeholder="Ask a question..."
          onError={(error: Error) => console.error('Chat error:', error)}
        />
      </div>
    </div>
  );
}

export default App; 