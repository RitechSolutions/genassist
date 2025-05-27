import React, { useState } from 'react';
import { GenAgentChat } from '../src';

const CustomThemeExample: React.FC = () => {
  const [theme, setTheme] = useState({
    primaryColor: '#8e44ad',
    secondaryColor: '#f5f5f5',
    backgroundColor: '#ffffff',
    textColor: '#333333',
    fontFamily: 'Roboto, sans-serif',
    fontSize: '15px',
  });

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

  return (
    <div style={{ 
      display: 'flex', 
      padding: '20px',
      gap: '20px',
      height: '100vh',
      boxSizing: 'border-box'
    }}>
      <div style={{ flex: '1' }}>
        <h2>Theme Controls</h2>
        <div style={{ marginBottom: '15px' }}>
          <label>Primary Color: </label>
          <input 
            type="color" 
            value={theme.primaryColor} 
            onChange={(e) => handleColorChange('primaryColor', e.target.value)} 
          />
        </div>
        <div style={{ marginBottom: '15px' }}>
          <label>Secondary Color: </label>
          <input 
            type="color" 
            value={theme.secondaryColor} 
            onChange={(e) => handleColorChange('secondaryColor', e.target.value)} 
          />
        </div>
        <div style={{ marginBottom: '15px' }}>
          <label>Background Color: </label>
          <input 
            type="color" 
            value={theme.backgroundColor} 
            onChange={(e) => handleColorChange('backgroundColor', e.target.value)} 
          />
        </div>
        <div style={{ marginBottom: '15px' }}>
          <label>Text Color: </label>
          <input 
            type="color" 
            value={theme.textColor} 
            onChange={(e) => handleColorChange('textColor', e.target.value)} 
          />
        </div>
        <div style={{ marginBottom: '15px' }}>
          <label>Font Size: </label>
          <select 
            value={theme.fontSize}
            onChange={(e) => handleColorChange('fontSize', e.target.value)}
          >
            <option value="12px">Small (12px)</option>
            <option value="15px">Medium (15px)</option>
            <option value="18px">Large (18px)</option>
          </select>
        </div>
        <div style={{ marginBottom: '15px' }}>
          <label>Font Family: </label>
          <select 
            value={theme.fontFamily}
            onChange={(e) => handleColorChange('fontFamily', e.target.value)}
          >
            <option value="Arial, sans-serif">Arial</option>
            <option value="Roboto, sans-serif">Roboto</option>
            <option value="'Times New Roman', serif">Times New Roman</option>
            <option value="monospace">Monospace</option>
          </select>
        </div>
      </div>
      
      <div style={{ flex: '1' }}>
        <GenAgentChat 
          baseUrl="https://api.example.com" 
          apiKey="your-api-key-here"
          userData={userData}
          theme={theme}
          headerTitle="Themed Chat"
          placeholder="Ask a question..."
          onError={(error) => console.error('Chat error:', error)}
        />
      </div>
    </div>
  );
};

export default CustomThemeExample; 