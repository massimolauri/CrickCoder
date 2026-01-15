import React, { useState } from 'react';
import { ChevronRight, Square, Play } from 'lucide-react';

interface ChatInputProps {
  onSubmit: (value: string) => void;
  onCancel: () => void;
  streaming: boolean;
  disabled: boolean;
  placeholder: string;
}

const ChatInput = React.memo(function ChatInput(props: ChatInputProps) {

  const [localValue, setLocalValue] = useState('');

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (props.streaming) return;
      if (!localValue.trim()) return;

      // Invio al padre e pulisco locale
      props.onSubmit(localValue);
      setLocalValue('');
    }
  };

  const handleButtonClick = () => {
    if (props.streaming) {
      props.onCancel();
    } else {
      if (!localValue.trim()) return;
      props.onSubmit(localValue);
      setLocalValue('');
    }
  };

  const isButtonDisabled = !props.streaming && (props.disabled || !localValue.trim());

  return (
    <div className={`max-w-4xl mx-auto backdrop-blur-xl bg-white/80 dark:bg-[#1E1F20] border border-gray-200 dark:border-none shadow-2xl rounded-2xl p-2 flex items-center gap-3 transition-all focus-within:ring-1 focus-within:ring-crick-accent/30`}>
      <div className="pl-3 text-crick-text-secondary">
        <ChevronRight size={18} />
      </div>
      <input
        type="text"
        value={localValue}
        onChange={(e) => setLocalValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={props.placeholder}
        className="flex-1 bg-transparent border-none outline-none text-crick-text-primary h-10 px-2 text-sm font-sans placeholder:text-gray-500 dark:placeholder:text-gray-600"
        disabled={props.disabled}
      />
      <button
        onClick={handleButtonClick}
        disabled={isButtonDisabled}
        className={`p-2.5 rounded-lg text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors shadow-lg ${props.streaming
          ? 'bg-red-600 hover:bg-red-500 shadow-red-900/20'
          : 'bg-[#1a73e8] hover:bg-[#1557b0] shadow-blue-900/20'
          }`}
      >
        {props.streaming ? <Square size={16} fill="currentColor" /> : <Play size={16} fill="currentColor" />}
      </button>
    </div>
  );
});

export default ChatInput;
