import React, { useState, useRef, useEffect } from 'react';
import { ChatMessageComponent } from './ChatMessage';
import { useChat } from '../hooks/useChat';
import { ChatMessage, GenAgentChatProps } from '../types';
import { VoiceInput } from './VoiceInput';
import { AudioService } from '../services/audioService';

export const GenAgentChat: React.FC<GenAgentChatProps> = ({
  baseUrl,
  apiKey,
  userData,
  onError,
  theme,
  headerTitle = 'Chat',
  placeholder = 'Type a message...'
}) => {
  const [inputValue, setInputValue] = useState('');
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const { 
    messages, 
    isLoading, 
    sendMessage, 
    resetConversation,
    connectionState, 
    conversationId 
  } = useChat({
    baseUrl,
    apiKey,
    onError
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const audioService = useRef<AudioService | null>(null);

  useEffect(() => {
    audioService.current = new AudioService({ baseUrl, apiKey });
  }, [baseUrl, apiKey]);

  // Auto-scroll to the latest message
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (inputValue.trim() === '' || isLoading) return;

    try {
      setInputValue('');
      await sendMessage(inputValue);
    } catch (error) {
      console.error('Error sending message:', error);
    }
  };

  const handleVoiceTranscription = async (text: string) => {
    if (text.trim() === '') return;
    try {
      await sendMessage(text);
    } catch (error) {
      console.error('Error sending voice message:', error);
    }
  };

  const handleVoiceError = (error: Error) => {
    console.error('Voice input error:', error);
    if (onError) {
      onError(error);
    }
  };

  const playResponseAudio = async (text: string) => {
    if (!audioService.current || isPlayingAudio) return;

    try {
      setIsPlayingAudio(true);
      const audioBlob = await audioService.current.textToSpeech(text);
      await audioService.current.playAudio(audioBlob);
    } catch (error) {
      console.error('Error playing audio:', error);
      if (onError) {
        onError(error as Error);
      }
    } finally {
      setIsPlayingAudio(false);
    }
  };

  const handleResetClick = () => {
    setShowResetConfirm(true);
  };

  const handleConfirmReset = async () => {
    await resetConversation();
    setShowResetConfirm(false);
  };

  const handleCancelReset = () => {
    setShowResetConfirm(false);
  };

  const containerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    height: '100%',
    maxHeight: '600px',
    width: '100%',
    maxWidth: '400px',
    border: '1px solid #e0e0e0',
    borderRadius: '8px',
    overflow: 'hidden',
    backgroundColor: theme?.backgroundColor || '#ffffff',
    fontFamily: theme?.fontFamily || 'Arial, sans-serif',
    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)'
  };

  const headerStyle: React.CSSProperties = {
    padding: '15px',
    backgroundColor: theme?.primaryColor || '#007bff',
    color: '#ffffff',
    fontWeight: 'bold',
    borderBottom: '1px solid #e0e0e0',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  };

  const chatContainerStyle: React.CSSProperties = {
    flex: 1,
    overflowY: 'auto',
    padding: '15px 0',
    backgroundColor: theme?.backgroundColor || '#ffffff',
  };

  const inputContainerStyle: React.CSSProperties = {
    display: 'flex',
    borderTop: '1px solid #e0e0e0',
    padding: '10px',
    backgroundColor: '#f9f9f9',
    alignItems: 'center',
  };

  const inputStyle: React.CSSProperties = {
    flex: 1,
    padding: '12px 15px',
    border: '1px solid #ddd',
    borderRadius: '20px',
    outline: 'none',
    fontSize: theme?.fontSize || '14px',
    fontFamily: theme?.fontFamily || 'Arial, sans-serif',
  };

  const sendButtonStyle: React.CSSProperties = {
    backgroundColor: theme?.primaryColor || '#007bff',
    color: '#ffffff',
    border: 'none',
    borderRadius: '50%',
    width: '40px',
    height: '40px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginLeft: '10px',
    cursor: 'pointer',
    outline: 'none',
  };

  const connectionIndicatorStyle: React.CSSProperties = {
    width: '10px',
    height: '10px',
    borderRadius: '50%',
    marginLeft: '10px',
    backgroundColor: 
      connectionState === 'connected' ? '#4CAF50' : 
      connectionState === 'connecting' ? '#FFC107' : '#F44336'
  };

  const resetButtonStyle: React.CSSProperties = {
    backgroundColor: 'transparent',
    color: '#ffffff',
    border: 'none',
    borderRadius: '4px',
    padding: '5px 10px',
    fontSize: '12px',
    cursor: 'pointer',
    marginLeft: '10px',
    display: 'flex',
    alignItems: 'center',
  };

  const resetIconStyle: React.CSSProperties = {
    marginRight: '5px',
    width: '16px',
    height: '16px',
  };

  const confirmOverlayStyle: React.CSSProperties = {
    display: showResetConfirm ? 'flex' : 'none',
    position: 'absolute',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundColor: 'rgba(0, 0, 0, 0.5)',
    zIndex: 10,
    justifyContent: 'center',
    alignItems: 'center',
  };

  const confirmDialogStyle: React.CSSProperties = {
    backgroundColor: '#ffffff',
    padding: '20px',
    borderRadius: '8px',
    maxWidth: '300px',
    textAlign: 'center',
  };

  const confirmButtonsStyle: React.CSSProperties = {
    display: 'flex',
    justifyContent: 'center',
    marginTop: '15px',
    gap: '10px',
  };

  const confirmButtonStyle = (isConfirm: boolean): React.CSSProperties => ({
    padding: '8px 16px',
    backgroundColor: isConfirm ? '#F44336' : '#e0e0e0',
    color: isConfirm ? '#ffffff' : '#333333',
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
  });

  // Convert SVG to data URL for the reset icon
  const resetIconSvg = `
    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path>
      <path d="M3 3v5h5"></path>
    </svg>
  `;
  const resetIconUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(resetIconSvg)}`;

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <div style={{ display: 'flex', alignItems: 'center' }}>
          {headerTitle}
          <div style={connectionIndicatorStyle} title={`Status: ${connectionState}`} />
        </div>
        <button 
          style={resetButtonStyle} 
          onClick={handleResetClick}
          disabled={connectionState !== 'connected'}
          title="Reset conversation"
        >
          <img src={resetIconUrl} alt="Reset" style={resetIconStyle} />
          Reset
        </button>
      </div>
      
      <div style={chatContainerStyle}>
        {messages.map((message, index) => (
          <ChatMessageComponent 
            key={index} 
            message={message} 
            theme={theme}
            onPlayAudio={message.speaker === 'agent' ? playResponseAudio : undefined}
            isPlayingAudio={isPlayingAudio}
          />
        ))}
        <div ref={messagesEndRef} />
      </div>
      
      <form onSubmit={handleSubmit} style={inputContainerStyle}>
        <input
          style={inputStyle}
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          placeholder={placeholder}
          disabled={connectionState !== 'connected'}
        />
        <VoiceInput
          onTranscription={handleVoiceTranscription}
          onError={handleVoiceError}
          baseUrl={baseUrl}
          apiKey={apiKey}
          theme={theme}
        />
        <button 
          type="submit" 
          style={sendButtonStyle}
          disabled={inputValue.trim() === '' || connectionState !== 'connected'}
        >
          →
        </button>
      </form>

      <div style={confirmOverlayStyle}>
        <div style={confirmDialogStyle}>
          <h3>Reset Conversation</h3>
          <p>This will clear the current conversation history and start a new conversation. Are you sure?</p>
          <div style={confirmButtonsStyle}>
            <button style={confirmButtonStyle(false)} onClick={handleCancelReset}>Cancel</button>
            <button style={confirmButtonStyle(true)} onClick={handleConfirmReset}>Reset</button>
          </div>
        </div>
      </div>
    </div>
  );
}; 