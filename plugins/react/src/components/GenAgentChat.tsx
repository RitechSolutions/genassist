import React, { useState, useRef, useEffect } from 'react';
import { ChatMessageComponent } from './ChatMessage';
import { useChat } from '../hooks/useChat';
import { ChatMessage, GenAgentChatProps } from '../types';
import { VoiceInput } from './VoiceInput';
import { AudioService } from '../services/audioService';
import { Send, Paperclip, MoreVertical, RefreshCw } from 'lucide-react';
import chatLogo from '../../assets/chat-logo.png';

export const GenAgentChat: React.FC<GenAgentChatProps> = ({
  baseUrl,
  apiKey,
  userData,
  onError,
  onTakeover,
  theme,
  headerTitle = 'Genassist',
  placeholder = 'Ask a question'
}) => {
  const [inputValue, setInputValue] = useState('');
  const [showResetConfirm, setShowResetConfirm] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const [isPlayingAudio, setIsPlayingAudio] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const { 
    messages, 
    isLoading, 
    sendMessage, 
    resetConversation,
    connectionState, 
    conversationId,
    possibleQueries,
    isTakenOver
  } = useChat({
    baseUrl,
    apiKey,
    onError,
    onTakeover
  });
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const audioService = useRef<AudioService | null>(null);

  const hasUserMessages = messages.some(message => message.speaker === 'customer');

  useEffect(() => {
    audioService.current = new AudioService({ baseUrl, apiKey });
  }, [baseUrl, apiKey]);

  // Auto-scroll to the latest message
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Close menu when clicking outside
  // useEffect(() => {
  //   const handleClickOutside = (event: MouseEvent) => {
  //     if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
  //       setShowMenu(false);
  //     }
  //   };

  //   document.addEventListener('mousedown', handleClickOutside);
  //   return () => {
  //     document.removeEventListener('mousedown', handleClickOutside);
  //   };
  // }, []);

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
    setInputValue(text);
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

  const handleQueryClick = async (query: string) => {
    if (isLoading) return;
    
    try {
      await sendMessage(query);
    } catch (error) {
      console.error('Error sending quick query:', error);
    }
  };

  const handleMenuClick = () => {
    setShowMenu(prev => !prev);
  };

  const handleResetClick = () => {
    setShowMenu(false);
    setShowResetConfirm(true);
  };

  const handleConfirmReset = async () => {
    await resetConversation();
    setShowResetConfirm(false);
  };

  const handleCancelReset = () => {
    setShowResetConfirm(false);
  };

  // Extract theme colors or use defaults
  const primaryColor = theme?.primaryColor || '#2962FF';
  const backgroundColor = theme?.backgroundColor || '#ffffff';
  const textColor = theme?.textColor || '#000000';
  const fontFamily = theme?.fontFamily || 'Roboto, Arial, sans-serif';
  const fontSize = theme?.fontSize || '14px';

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
    backgroundColor,
    fontFamily,
    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
    position: 'relative'
  };

  const headerStyle: React.CSSProperties = {
    padding: '15px',
    backgroundColor: primaryColor,
    color: '#ffffff',
    fontWeight: 'bold',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    position: 'relative'
  };

  const logoContainerStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '10px'
  };

  const logoStyle: React.CSSProperties = {
    width: '28px',
    height: '28px',
  };

  const headerTitleContainerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
  };

  const headerTitleStyle: React.CSSProperties = {
    fontSize: '16px',
    fontWeight: 'bold',
    margin: 0,
    fontFamily,
  };

  const headerSubtitleStyle: React.CSSProperties = {
    fontSize: '14px',
    fontWeight: 'normal',
    margin: 0,
    fontFamily,
  };

  const menuButtonStyle: React.CSSProperties = {
    backgroundColor: 'transparent',
    color: '#ffffff',
    border: 'none',
    borderRadius: '50%',
    width: '32px',
    height: '32px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    outline: 'none',
  };

  const menuPopupStyle: React.CSSProperties = {
    position: 'absolute',
    top: '50px',
    right: '15px',
    backgroundColor: backgroundColor,
    borderRadius: '8px',
    boxShadow: '0 2px 10px rgba(0, 0, 0, 0.1)',
    zIndex: 10,
    display: showMenu ? 'block' : 'none',
    minWidth: '150px',
    overflow: 'hidden',
  };

  const menuItemStyle: React.CSSProperties = {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    padding: '10px 15px',
    color: textColor,
    cursor: 'pointer',
    fontSize,
    fontFamily,
    borderBottom: '1px solid #f0f0f0',
  };

  const chatContainerStyle: React.CSSProperties = {
    flex: 1,
    overflowY: 'auto',
    padding: '15px',
    backgroundColor,
    display: 'flex',
    flexDirection: 'column',
  };

  const inputContainerStyle: React.CSSProperties = {
    display: 'flex',
    padding: '15px',
    backgroundColor: '#f5f5f5',
    alignItems: 'center',
    gap: '8px',
    borderTop: '1px solid #e0e0e0',
  };

  const inputWrapperStyle: React.CSSProperties = {
    display: 'flex',
    flex: 1,
    alignItems: 'center',
    backgroundColor: '#ffffff',
    borderRadius: '8px',
    padding: '0 15px',
    height: '48px',
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
  };

  const inputStyle: React.CSSProperties = {
    flex: 1,
    border: 'none',
    outline: 'none',
    background: 'transparent',
    fontSize,
    fontFamily,
    padding: '0 10px',
    color: textColor,
  };

  const attachButtonStyle: React.CSSProperties = {
    backgroundColor: 'transparent',
    border: 'none',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    outline: 'none',
    color: '#757575',
    padding: 0,
  };

  const sendButtonStyle: React.CSSProperties = {
    backgroundColor: primaryColor,
    color: '#ffffff',
    border: 'none',
    borderRadius: '8px',
    width: '48px',
    height: '48px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    cursor: 'pointer',
    outline: 'none',
    flexShrink: 0,
    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)',
  };

  const possibleQueriesContainerStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    padding: '0',
    paddingLeft: '28px',
    paddingRight: '28px',
    marginTop: '5px',
    marginBottom: '15px',
    width: '100%',
    fontFamily,
  };
  
  const queryButtonStyle: React.CSSProperties = {
    padding: '12px 15px',
    backgroundColor: theme?.secondaryColor || '#f5f5f5',
    color: textColor,
    border: 'none',
    borderRadius: '6px',
    fontSize,
    cursor: 'pointer',
    textAlign: 'left',
    fontWeight: 'normal',
    boxShadow: 'none',
    width: '100%',
    maxWidth: '240px',
    fontFamily,
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
    backgroundColor: backgroundColor,
    padding: '20px',
    borderRadius: '8px',
    maxWidth: '300px',
    textAlign: 'center',
    fontFamily,
    color: textColor,
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
    color: isConfirm ? '#ffffff' : textColor,
    border: 'none',
    borderRadius: '4px',
    cursor: 'pointer',
    fontFamily,
    fontSize,
  });

  return (
    <div style={containerStyle}>
      <div style={headerStyle}>
        <div style={logoContainerStyle}>
          <img src={chatLogo} alt="Logo" style={logoStyle} />
          <div style={headerTitleContainerStyle}>
            <div style={headerTitleStyle}>{headerTitle}</div>
            <div style={headerSubtitleStyle}>Support</div>
          </div>
        </div>
        <button 
          style={menuButtonStyle} 
          onClick={handleMenuClick}
          title="Menu"
        >
          <MoreVertical size={24} color="#ffffff" />
        </button>

        <div ref={menuRef} style={menuPopupStyle}>
          <div style={menuItemStyle} onClick={handleResetClick}>
            <RefreshCw size={16} />
            Reset conversation
          </div>
        </div>
      </div>
      
      <div style={chatContainerStyle}>
        {messages.map((message, index) => {
          const isNextSameSpeaker = index < messages.length - 1 && messages[index + 1].speaker === message.speaker;
          const isPrevSameSpeaker = index > 0 && messages[index - 1].speaker === message.speaker;
          
          return (
            <ChatMessageComponent 
              key={index} 
              message={message} 
              theme={theme}
              onPlayAudio={message.speaker === 'agent' ? playResponseAudio : undefined}
              isPlayingAudio={isPlayingAudio}
              isFirstMessage={index === 0 && message.speaker === 'agent' && !hasUserMessages}
              isNextSameSpeaker={isNextSameSpeaker}
              isPrevSameSpeaker={isPrevSameSpeaker}
            />
          );
        })}
        <div ref={messagesEndRef} />
      </div>

      {possibleQueries.length > 0 && !hasUserMessages && (
        <div style={possibleQueriesContainerStyle}>
          {possibleQueries.map((query, index) => (
            <button 
              key={index}
              style={queryButtonStyle}
              onClick={() => handleQueryClick(query)}
              disabled={isLoading}
            >
              {query}
            </button>
          ))}
        </div>
      )}
      
      <form onSubmit={handleSubmit} style={inputContainerStyle}>
        <div style={inputWrapperStyle}>
          <button 
            type="button" 
            style={attachButtonStyle}
            title="Attach"
          >
            <Paperclip size={24} color="#757575" />
          </button>
          <input
            style={inputStyle}
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder={placeholder}
            disabled={connectionState !== 'connected'}
          />
        </div>
        
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
          <Send size={20} color="#ffffff" />
        </button>
      </form>

      <div style={confirmOverlayStyle}>
        <div style={confirmDialogStyle}>
          <h3 style={{fontFamily, marginTop: 0}}>Reset Conversation</h3>
          <p style={{fontFamily, fontSize}}>This will clear the current conversation history and start a new conversation. Are you sure?</p>
          <div style={confirmButtonsStyle}>
            <button style={confirmButtonStyle(false)} onClick={handleCancelReset}>Cancel</button>
            <button style={confirmButtonStyle(true)} onClick={handleConfirmReset}>Reset</button>
          </div>
        </div>
      </div>
    </div>
  );
}; 