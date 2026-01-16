import React, { useState } from "react";
import { Input } from "@/components/input";
import { Button } from "@/components/button";
import { Sparkles, ArrowUp } from "lucide-react";

interface ChatInputBarProps {
  onSendMessage?: (message: string) => void;
  disabled?: boolean;
  placeholder?: string;
}

const ChatInputBar: React.FC<ChatInputBarProps> = ({
  onSendMessage,
  disabled = false,
  placeholder = "Ask AI by sending a message...",
}) => {
  const [message, setMessage] = useState("");

  const handleSend = () => {
    if (message.trim() && onSendMessage) {
      onSendMessage(message.trim());
      setMessage("");
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="fixed bottom-8 left-1/2 -translate-x-1/2 z-30">
      <div className="relative w-[480px]">
        <div className="absolute left-4 top-1/2 -translate-y-1/2 z-20 pointer-events-none">
          <Sparkles className="h-5 w-5 text-purple-500" />
        </div>
        <input
          type="text"
          value={message}
          onChange={(e) => setMessage(e.target.value)}
          onKeyDown={handleKeyPress}
          placeholder={placeholder}
          disabled={disabled}
          className="w-full h-[56px] bg-white/90 focus:bg-white backdrop-blur-md focus:backdrop-blur-none rounded-full pl-14 pr-16 text-base placeholder:text-gray-400 focus:outline-none animated-shadow-input transition-all"
        />
        <button
          onClick={handleSend}
          disabled={disabled || !message.trim()}
          className="absolute right-2 top-1/2 -translate-y-1/2 z-20 rounded-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed h-10 w-10 flex items-center justify-center transition-colors"
        >
          <ArrowUp className="h-4 w-4 text-white" />
        </button>
      </div>
    </div>
  );
};

export default ChatInputBar;
