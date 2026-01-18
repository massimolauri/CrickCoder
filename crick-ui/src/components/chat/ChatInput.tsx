import React, { useState, useEffect } from 'react';
import { ChevronRight, Square, Play, Palette } from 'lucide-react';
import { templateService } from '@/services/templateService';
import type { Template } from '@/types/api.types';

interface ChatInputProps {
  onSubmit: (value: string) => void;
  onCancel: () => void;
  streaming: boolean;
  disabled: boolean;
  placeholder: string;
  selectedThemeId: string | null;
  onThemeSelect: (themeId: string | null) => void;
}

const ChatInput = React.memo(function ChatInput(props: ChatInputProps) {

  const [localValue, setLocalValue] = useState('');
  const [templates, setTemplates] = useState<Template[]>([]);
  const [showTemplates, setShowTemplates] = useState(false);

  useEffect(() => {
    // Load templates on mount
    templateService.listTemplates((window as any).electron?.projectPath || "")
      .then(result => {
        if (result.success) {
          setTemplates(result.data.templates);
        }
      });
  }, []);

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
    <div className={`max-w-4xl mx-auto backdrop-blur-xl bg-crick-surface border border-gray-200 dark:border-[#3e3e42] shadow-2xl rounded-2xl p-2 flex items-center gap-3 transition-all focus-within:ring-1 focus-within:ring-crick-accent/30`}>
      <div className="relative">
        <button
          onClick={() => setShowTemplates(!showTemplates)}
          className={`p-1.5 rounded-md transition-colors ${props.selectedThemeId
            ? 'text-purple-500 bg-purple-500/10'
            : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300'}`}
          title="Select Theme Context"
        >
          <Palette size={18} />
        </button>

        {showTemplates && (
          <div className="absolute bottom-full mb-2 left-0 w-64 bg-white dark:bg-[#252526] border border-gray-200 dark:border-[#3e3e42] rounded-xl shadow-xl overflow-hidden z-50">
            <div className="p-2 border-b border-gray-100 dark:border-[#3e3e42]">
              <p className="text-xs font-medium text-gray-500 dark:text-gray-400 px-2 pb-1">SELECT THEME CONTEXT</p>
            </div>
            <div className="max-h-60 overflow-y-auto py-1">
              <button
                onClick={() => { props.onThemeSelect(null); setShowTemplates(false); }}
                className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-[#2d2d2d] flex items-center justify-between group ${!props.selectedThemeId ? 'text-purple-500' : 'text-gray-700 dark:text-gray-300'}`}
              >
                <span>No Theme</span>
                {!props.selectedThemeId && <div className="h-2 w-2 rounded-full bg-purple-500" />}
              </button>
              {templates.map(t => (
                <button
                  key={t.id}
                  onClick={() => { props.onThemeSelect(t.id); setShowTemplates(false); }}
                  className={`w-full text-left px-4 py-2 text-sm hover:bg-gray-100 dark:hover:bg-[#2d2d2d] flex items-center justify-between group ${props.selectedThemeId === t.id ? 'text-purple-500' : 'text-gray-700 dark:text-gray-300'}`}
                >
                  <span className="truncate">{t.name}</span>
                  {props.selectedThemeId === t.id && <div className="h-2 w-2 rounded-full bg-purple-500" />}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="text-crick-text-secondary">
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
