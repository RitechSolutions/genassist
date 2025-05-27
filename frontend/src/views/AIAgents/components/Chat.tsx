import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { initializeAgent, queryAgent, getAgentConfig } from '@/services/api';
import { Button } from '@/components/button';
import { Input } from '@/components/input';
import { ArrowLeft, Send, Bot, User, Loader2 } from 'lucide-react';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/avatar';
import { Separator } from '@/components/separator';
import { Badge } from '@/components/badge';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/card';

interface Message {
  role: 'user' | 'assistant' | 'system';
  content: string;
}

interface AgentConfig {
  id: string;
  name: string;
  provider: string;
  model: string;
  system_prompt: string;
  knowledge_base_ids?: string[];
  [key: string]: unknown;
}

const Chat: React.FC = () => {
  const { agentId, threadId } = useParams<{ agentId: string; threadId: string }>();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [agentInfo, setAgentInfo] = useState<AgentConfig | null>(null);
  const [initializing, setInitializing] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const fetchAgentInfo = async () => {
      if (!agentId) return;
      
      try {
        const config = await getAgentConfig(agentId);
        setAgentInfo(config);
        
        setMessages([
          {
            role: 'assistant',
            content: `Hello! I'm your ${config.provider} assistant powered by ${config.model}. How can I help you today?`
          }
        ]);
      } catch (error) {
        console.error('Error fetching agent info:', error);
        setMessages([
          {
            role: 'system',
            content: 'Error initializing agent. Please try again later.'
          }
        ]);
        setInitializing(false);
      }
    };

    fetchAgentInfo();
  }, [agentId]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || loading || !agentId || !threadId) return;

    const userMessage = input.trim();
    setInput('');
    
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    
    setLoading(true);
    
    try {
      const response = await queryAgent(agentId, threadId, userMessage);
      
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: response.response || 'Sorry, I couldn\'t process your request.'
      }]);
    } catch (error) {
      console.error('Error sending message:', error);
      setMessages(prev => [...prev, { 
        role: 'system', 
        content: 'Error: Failed to get response from the agent.'
      }]);
    } finally {
      setLoading(false);
    }
  };

  const getProviderInitials = () => {
    if (!agentInfo?.provider) return 'AI';
    return agentInfo.provider.slice(0, 2).toUpperCase();
  };

  return (
    <Card className="flex flex-col h-screen max-w-4xl mx-auto border-none rounded-none shadow-none">
      <CardHeader className="border-b px-4 py-3 flex-row items-center justify-between gap-4 bg-background">
        <div className="flex items-center gap-2">
          <Button variant="ghost" size="icon" onClick={() => navigate('/ai-agents')} className="h-8 w-8">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <CardTitle className="text-lg font-medium">
            {agentInfo ? agentInfo.provider : 'Loading...'}
          </CardTitle>
          {agentInfo && (
            <Badge variant="outline" className="ml-2">
              {agentInfo.model}
            </Badge>
          )}
        </div>
        <div className="flex items-center text-xs text-muted-foreground space-x-2">
          <span className="inline-flex items-center">
            Agent ID: <code className="ml-1 px-1 bg-muted rounded">{agentId?.slice(0, 8)}</code>
          </span>
          <Separator orientation="vertical" className="h-4" />
          <span className="inline-flex items-center">
            Thread ID: <code className="ml-1 px-1 bg-muted rounded">{threadId?.slice(0, 8)}</code>
          </span>
        </div>
      </CardHeader>

      <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((message, index) => (
          <div 
            key={index} 
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div className={`flex gap-3 max-w-[85%] ${message.role === 'user' ? 'flex-row-reverse' : ''}`}>
              <Avatar className={`h-8 w-8 ${message.role === 'system' ? 'bg-yellow-500' : ''}`}>
                {message.role === 'assistant' && <AvatarFallback>{getProviderInitials()}</AvatarFallback>}
                {message.role === 'user' && <AvatarFallback><User className="h-4 w-4" /></AvatarFallback>}
                {message.role === 'system' && <AvatarFallback><Bot className="h-4 w-4" /></AvatarFallback>}
              </Avatar>
              <div className={`p-3 rounded-lg ${
                message.role === 'user' 
                  ? 'bg-primary text-primary-foreground' 
                  : message.role === 'assistant'
                    ? 'bg-card border text-card-foreground shadow-sm' 
                    : 'bg-yellow-100 border-yellow-200 border text-yellow-800'
              }`}>
                <p className="whitespace-pre-wrap">{message.content}</p>
              </div>
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="flex gap-3 max-w-[85%]">
              <Avatar>
                <AvatarFallback>{getProviderInitials()}</AvatarFallback>
              </Avatar>
              <div className="p-3 rounded-lg bg-card border text-card-foreground shadow-sm">
                <div className="flex items-center space-x-2">
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                  <p className="text-sm text-muted-foreground">Thinking...</p>
                </div>
              </div>
            </div>
          </div>
        )}
        {initializing && (
          <div className="flex justify-center">
            <div className="p-3 rounded-lg bg-muted border border-border max-w-[85%]">
              <div className="flex items-center space-x-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                <p>Initializing agent...</p>
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </CardContent>

      <CardFooter className="border-t p-4 bg-background">
        <form className="flex w-full gap-2" onSubmit={handleSendMessage}>
          <Input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message here..."
            disabled={loading || initializing}
            className="flex-1"
          />
          <Button 
            type="submit"
            size="icon"
            disabled={loading || initializing || !input.trim()}
          >
            <Send className="h-4 w-4" />
          </Button>
        </form>
      </CardFooter>
    </Card>
  );
};

export default Chat; 