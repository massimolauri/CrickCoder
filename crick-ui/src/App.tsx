import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
  Menu, ChevronRight, Settings, Folder, LayoutTemplate, Moon, Sun
} from 'lucide-react';

// Import servizi e hook
import { useChat } from '@/hooks/useChat';
import { useHealth } from '@/hooks/useHealth';
import { sessionService } from '@/services/sessionService';
import { projectStorage, llmSettingsStorage, type LLMSettings } from '@/utils/storage';

// Import componenti UI
import SessionList from '@/components/SessionList/SessionList';
import HealthIndicator from '@/components/HealthStatus/HealthIndicator';
import TemplatesPanel from '@/components/Templates/TemplatesPanel';
// Import componenti chat
import MessageList from '@/components/chat/MessageList';
import ChatInput from '@/components/chat/ChatInput';
import { renderTimelineItem } from '@/components/chat/renderTimelineItem';


// --- THEME CONFIGURATION ---
import { THEME } from '@/constants/theme';




// --- MAIN COMPONENT ---

export default function CrickInterface() {
  // Stato progetto
  const [projectPath, setProjectPath] = useState(() => projectStorage.get() || '');
  const [llmSettings, setLlmSettings] = useState<LLMSettings>(() => llmSettingsStorage.get() || {
    provider: "DeepSeek",
    model_id: "deepseek-chat",
    api_key: "",
  });
  const [showSettings, setShowSettings] = useState(false);
  const [showTemplates, setShowTemplates] = useState(false);
  const [showSessions, setShowSessions] = useState(true);

  // Theme Toggle State
  const [isDarkMode, setIsDarkMode] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('theme') === 'dark' ||
        (!localStorage.getItem('theme') && window.matchMedia('(prefers-color-scheme: dark)').matches);
    }
    return false;
  });

  // Apply Theme Effect
  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
    } else {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
    }
  }, [isDarkMode]);

  // State for selected session badge
  const [sessionBadge, setSessionBadge] = useState<{
    sessionId: string | null;
    isNew: boolean;
    visible: boolean;
  }>({
    sessionId: null,
    isNew: false,
    visible: false,
  });

  // Hook per chat, sessioni e health
  const onStreamStart = useCallback(() => { }, []);
  const onStreamEnd = useCallback(() => { }, []);
  const onError = useCallback((error: Error) => console.error('Chat error:', error), []);

  const chat = useChat({
    projectPath,
    llmSettings,
    onStreamStart,
    onStreamEnd,
    onError,
  });

  const health = useHealth();


  const bottomRef = useRef<HTMLDivElement>(null);
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [autoScrollEnabled, setAutoScrollEnabled] = useState(true);
  const [, setUserHasScrolled] = useState(false);
  const userHasScrolledRef = useRef(false);
  const isAutoScrollingRef = useRef(false);

  // Auto-scroll quando arrivano nuovi messaggi
  useEffect(() => {
    if (!autoScrollEnabled) return;

    isAutoScrollingRef.current = true;
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });

    // Resetta il flag dopo che lo scroll è completato
    const timer = setTimeout(() => {
      isAutoScrollingRef.current = false;
    }, 300); // Tempo sufficiente per lo scroll smooth

    return () => clearTimeout(timer);
  }, [chat.messages, autoScrollEnabled]);

  // Gestione scroll utente per determinare se abilitare auto-scroll
  useEffect(() => {
    const container = scrollContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      // Ignora gli eventi di scroll causati dall'auto-scroll
      if (isAutoScrollingRef.current) return;

      const { scrollTop, scrollHeight, clientHeight } = container;
      const isNearBottom = scrollHeight - scrollTop - clientHeight < 150;

      // L'utente ha scrollato manualmente
      userHasScrolledRef.current = true;
      setUserHasScrolled(true);

      // Auto-scroll enabled if: user is near bottom OR never scrolled
      const shouldAutoScroll = isNearBottom || !userHasScrolledRef.current;
      setAutoScrollEnabled(shouldAutoScroll);

      // If near bottom, reset manual scroll flag
      if (isNearBottom) {
        userHasScrolledRef.current = false;
        setUserHasScrolled(false);
      }
    };

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, []);


  // Salva projectPath quando cambia
  useEffect(() => {
    if (projectPath) {
      projectStorage.set(projectPath);
    }
  }, [projectPath]);

  // Salva llmSettings quando cambiano
  useEffect(() => {
    llmSettingsStorage.set(llmSettings);
  }, [llmSettings]);

  // Handler invio messaggio
  const handleSubmit = useCallback((message: string) => {
    if (health.isOffline) return;
    if (!message.trim() || !projectPath) return;
    chat.sendMessage(message);
  }, [health.isOffline, projectPath, chat.sendMessage]);

  // Handler cancellazione streaming
  const handleCancel = useCallback(() => {
    chat.cancelStream();
  }, [chat.cancelStream]);

  // Placeholder memoizzato
  const placeholder = useMemo(() => {
    if (health.isOffline) return 'Server offline - unable to chat';
    return projectPath ? 'Ask team to build/fix something...' : 'Link a project path in settings first...';
  }, [health.isOffline, projectPath]);

  // Show session selection badge
  const showSessionSelectionBadge = (sessionId: string, isNew: boolean = false) => {
    setSessionBadge({
      sessionId,
      isNew,
      visible: true,
    });

    // Nascondi automaticamente dopo 3 secondi
    setTimeout(() => {
      setSessionBadge(prev => ({ ...prev, visible: false }));
    }, 3000);
  };

  // Create new session
  const handleNewSession = () => {
    const newSessionId = sessionService.generateLocalSessionId();
    chat.switchSession(newSessionId);
    showSessionSelectionBadge(newSessionId, true);
  };

  // Manual scroll to bottom
  const scrollToBottom = () => {
    userHasScrolledRef.current = false;
    setUserHasScrolled(false);
    setAutoScrollEnabled(true);

    isAutoScrollingRef.current = true;
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });

    // Resetta il flag dopo che lo scroll è completato
    setTimeout(() => {
      isAutoScrollingRef.current = false;
    }, 300);
  };



  return (
    <div className={`flex h-screen w-full ${THEME.bg} text-crick-text-primary font-sans overflow-hidden selection:bg-crick-accent/30 selection:text-crick-accent`}>
      <div className="neon-glow" />
      {/* Left sidebar */}
      <div className={`w-18 flex flex-col items-center py-6 bg-crick-surface hidden sm:flex z-20`}>
        <button
          onClick={() => { setShowSessions(!showSessions); setShowSettings(false); setShowTemplates(false); }}
          className="p-3 bg-crick-surface/80 dark:bg-white/5 rounded-full mb-6 border border-gray-200 dark:border-[#3e3e42] shadow-sm hover:shadow-md hover:scale-105 transition-all cursor-pointer group text-gray-600 dark:text-gray-300"
        >
          <Menu className="w-5 h-5 text-gray-600 group-hover:text-crick-accent" />
        </button>

        {/* Templates Button */}
        <button
          onClick={() => { setShowTemplates(!showTemplates); setShowSettings(false); setShowSessions(false); }}
          className={`p-3 rounded-full mb-4 border transition-all cursor-pointer relative group ${showTemplates ? 'bg-purple-100 dark:bg-purple-900/30 border-purple-200 dark:border-purple-800/50 shadow-inner' : 'bg-transparent border-transparent hover:bg-gray-100 dark:hover:bg-white/5'}`}
          title="Templates Library"
        >
          <LayoutTemplate className={`w-6 h-6 ${showTemplates ? 'text-purple-600' : 'text-gray-400 group-hover:text-purple-500'}`} />
          {!showTemplates && (
            <span className="absolute left-16 top-1/2 -translate-y-1/2 bg-gray-900 text-white text-xs px-2 py-1 rounded-md opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50">
              Templates
            </span>
          )}
        </button>

        {/* Flexible space to push content to bottom */}
        <div className="flex-1" />

        {/* Settings button and indicators (at bottom) */}
        <div className="mt-auto flex flex-col items-center gap-4 py-4">
          <button
            onClick={() => setIsDarkMode(!isDarkMode)}
            className="p-3 rounded-full text-gray-400 hover:text-crick-accent hover:bg-crick-surface transition-all"
            title={isDarkMode ? "Switch to Light Mode" : "Switch to Dark Mode"}
          >
            {isDarkMode ? <Sun size={20} /> : <Moon size={20} />}
          </button>
          <button
            onClick={() => { setShowSettings(!showSettings); setShowSessions(false); setShowTemplates(false); }}
            className={`p-3 rounded-full transition-all ${showSettings ? 'bg-blue-100 dark:bg-blue-900/30 text-crick-accent' : 'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'}`}
            title="Settings"
          >
            <Settings size={22} />
          </button>
          <HealthIndicator />
        </div>
      </div>

      {/* Sessions sidebar */}
      {showSessions && projectPath && (
        <div className={`w-80 ${THEME.sidebar} border-r border-gray-100 flex flex-col py-6 overflow-y-auto z-10 glass-panel`}>
          <SessionList
            projectPath={projectPath}
            selectedSessionId={chat.currentSessionId}
            onSelectSession={(sessionId) => {
              chat.switchSession(sessionId);
              showSessionSelectionBadge(sessionId, false);
            }}
            onNewSession={handleNewSession}
          />
        </div>
      )}

      {/* Contenuto principale */}
      <div className="flex-1 flex flex-col relative z-0">
        {/* Header */}
        <header className="h-16 border-b border-gray-100 dark:border-[#3e3e42] flex items-center justify-between px-8 bg-crick-bg z-10 sticky top-0 transition-colors">
          <div className="flex items-center gap-3">
            <div className="flex items-center">
              <span className="font-bold text-lg text-crick-text-primary tracking-tight typewriter inline-block">
                crick<span className="text-crick-accent">coder</span>
              </span>
            </div>
            <div className="hidden md:flex items-center gap-2 text-[11px] font-mono text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-white/5 px-3 py-1.5 rounded-full border border-gray-200 dark:border-[#3e3e42]">
              <Folder size={12} className="text-gray-400" /> {projectPath ? (projectPath.length > 50 ? '...' + projectPath.slice(-50) : projectPath) : 'NO PROJECT LINKED'}
            </div>
          </div>
        </header>

        {/* Settings panel */}
        {showSettings && (
          <div className="absolute top-16 left-0 right-0 z-30 glass-panel border-b border-gray-100 dark:border-[#3e3e42] p-6 animate-in slide-in-from-top-2">
            <div className="max-w-2xl mx-auto space-y-6">
              {/* Sezione Project Root Path */}
              <div className="space-y-3">
                <label className="text-xs font-mono text-slate-500 uppercase tracking-wider">Project Root Path</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={projectPath}
                    onChange={(e) => {
                      const newPath = e.target.value;
                      setProjectPath(newPath);
                    }}
                    className="flex-1 bg-crick-surface border border-gray-200 dark:border-[#3e3e42] rounded-full px-4 py-2 text-sm font-mono text-crick-text-primary outline-none focus:border-crick-accent transition-colors pl-4"
                    placeholder="e.g. C:/Dev/MyProject"
                  />
                </div>
              </div>

              {/* Sezione LLM Settings */}
              <div className="space-y-4">
                <label className="text-xs font-mono text-slate-500 uppercase tracking-wider">LLM Configuration</label>

                {/* Provider */}
                <div className="space-y-2">
                  <label className="text-sm text-slate-400">Provider</label>
                  <select
                    value={llmSettings.provider}
                    onChange={(e) => setLlmSettings({ ...llmSettings, provider: e.target.value })}
                    className="w-full bg-crick-surface border border-gray-200 rounded-full px-4 py-2 text-sm text-crick-text-primary outline-none focus:border-crick-accent transition-colors appearance-none"
                  >
                    <option value="DeepSeek">DeepSeek</option>
                    <option value="OpenAiLike">OpenAiLike</option>
                    <option value="OpenAIChat">OpenAIChat</option>
                    <option value="Gemini">Gemini</option>
                    <option value="Nvidia">Nvidia</option>
                    <option value="Ollama">Ollama</option>
                    <option value="OpenRouter">OpenRouter</option>
                    <option value="Claude">Claude</option>
                  </select>
                </div>

                {/* Model ID */}
                <div className="space-y-2">
                  <label className="text-sm text-slate-400">Model ID</label>
                  <input
                    type="text"
                    value={llmSettings.model_id}
                    onChange={(e) => setLlmSettings({ ...llmSettings, model_id: e.target.value })}
                    className="w-full bg-crick-surface border border-gray-200 rounded-full px-4 py-2 text-sm text-crick-text-primary outline-none focus:border-crick-accent transition-colors"
                    placeholder="deepseek-chat, gpt-4o, claude-3-5-sonnet"
                  />
                </div>

                {/* API Key */}
                <div className="space-y-2">
                  <label className="text-sm text-slate-400">API Key</label>
                  <input
                    type="password"
                    value={llmSettings.api_key}
                    onChange={(e) => setLlmSettings({ ...llmSettings, api_key: e.target.value })}
                    className="w-full bg-crick-surface border border-gray-200 rounded-full px-4 py-2 text-sm text-crick-text-primary outline-none focus:border-crick-accent transition-colors"
                    placeholder="sk-..."
                  />
                  <p className="text-xs text-slate-500 mt-1">The API key is stored locally in your browser.</p>
                </div>
              </div>

              {/* Save button */}
              <div className="flex justify-end pt-4">
                <button
                  onClick={() => setShowSettings(false)}
                  className="px-6 py-2.5 bg-[#1a73e8] hover:bg-[#1557b0] text-white text-sm font-medium rounded-full transition-colors shadow-lg hover:shadow-xl"
                >
                  SAVE SETTINGS
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Templates Panel */}
        {showTemplates && (
          <TemplatesPanel
            projectPath={projectPath}
            onClose={() => setShowTemplates(false)}
          />
        )}

        {/* Session selection badge */}
        {sessionBadge.visible && sessionBadge.sessionId && (
          <div className="absolute top-20 left-1/2 transform -translate-x-1/2 z-30 animate-in fade-in slide-in-from-top-2 duration-300">
            <div className={`flex items-center gap-2 px-4 py-2.5 rounded-full border shadow-lg ${sessionBadge.isNew
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
              : 'bg-[#1f6feb]/10 border-[#1f6feb]/30 text-[#58a6ff]'
              }`}>
              <div className={`w-2 h-2 rounded-full ${sessionBadge.isNew ? 'bg-emerald-500 animate-pulse' : 'bg-[#58a6ff]'}`} />
              <span className="text-sm font-medium">
                {sessionBadge.isNew ? 'New session created' : 'Session selected'}
              </span>
              <span className="text-xs font-mono opacity-70 ml-1">
                {sessionBadge.sessionId.slice(0, 8)}...
              </span>
            </div>
          </div>
        )}

        {/* Chat area */}
        <div ref={scrollContainerRef} className="flex-1 overflow-y-auto p-4 sm:p-8 scrollbar-thin scrollbar-thumb-[#30363d] scrollbar-track-transparent">
          <div className="max-w-4xl mx-auto">
            {chat.messages.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-full py-16 text-center animate-in fade-in zoom-in-95 duration-700 slide-in-from-bottom-4">
                <h2 className="text-5xl md:text-6xl font-bold text-crick-text-primary mb-6 tracking-tight">
                  Crick<span className="text-crick-accent">Coder</span>
                </h2>
                <p className="text-crick-text-secondary max-w-4xl text-xl md:text-2xl leading-relaxed typewriter-long inline-block">
                  Start a new conversation with the AI agent team to develop, fix, or improve your project.
                </p>
              </div>
            ) : (
              <>
                <MessageList
                  messages={chat.messages}
                  streaming={chat.streaming}
                  lastMessageId={chat.lastMessage?.id}
                  renderTimelineItem={renderTimelineItem}
                />
                <div ref={bottomRef} className="h-4" />

                {/* "Go to bottom" button when user is not at bottom and there is streaming */}
                {chat.streaming && !autoScrollEnabled && (
                  <div className="absolute bottom-24 right-8 z-20 animate-in fade-in duration-300">
                    <button
                      onClick={scrollToBottom}
                      className="p-3 bg-crick-accent hover:bg-blue-600 text-white rounded-full border border-blue-400 shadow-xl transition-colors flex items-center justify-center"
                      title="Go to bottom"
                    >
                      <ChevronRight size={16} className="rotate-90" />
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>

        {/* Chat input */}
        <div className="p-4 bg-crick-bg border-t border-gray-100 dark:border-[#3e3e42] z-20">
          <ChatInput
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            streaming={chat.streaming}
            disabled={chat.streaming || health.isOffline}
            placeholder={placeholder}
            selectedThemeId={chat.selectedThemeId}
            onThemeSelect={chat.setSelectedThemeId}
          />

          {/* Controls below chat */}
          <div className="max-w-4xl mx-auto mt-3 flex items-center justify-between">
            {/* Agent selector (left) */}
            <div className="flex items-center gap-2">
              <div className="flex bg-gray-100 dark:bg-white/5 border border-gray-200 dark:border-[#3e3e42] rounded-full p-1 shadow-inner">
                <button
                  onClick={() => chat.setSelectedAgentId("PLANNER")}
                  className={`relative px-6 py-2 rounded-full text-xs font-bold tracking-wide transition-all duration-300 ${chat.selectedAgentId === "PLANNER" ? "bg-purple-600 text-white shadow-lg shadow-purple-900/20 animate-ripple" : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-white/50"}`}
                >
                  PLANNER
                </button>
                <button
                  onClick={() => chat.setSelectedAgentId("CODER")}
                  className={`relative px-6 py-2 rounded-full text-xs font-bold tracking-wide transition-all duration-300 ${chat.selectedAgentId === "CODER" ? "bg-emerald-500 text-white shadow-lg shadow-emerald-900/20 animate-ripple" : "text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-white/50"}`}
                >
                  CODER
                </button>
              </div>
              <div className="flex flex-col">
                <span className="ml-2 text-sm font-medium text-gray-500 dark:text-gray-400">
                  Talking to: {chat.selectedAgentId}
                </span>
                <span className="ml-2 text-xs text-gray-400 dark:text-gray-500 mt-0.5">
                  {chat.selectedAgentId === "PLANNER"
                    ? "Breaks down requests into logical tasks - Technical Lead"
                    : "Writes and implements code - switch to Coder to write the project"}
                </span>
              </div>
            </div>

            {/* Approve/Reject buttons (right) - visible only when paused */}
            {chat.pausedRunId && (
              <div className="flex items-center gap-3">
                <span className="text-sm text-slate-500">{chat.pausedAgentName} wants to run {chat.pausedTool}. Approve or reject?</span>
                <button
                  onClick={() => chat.continueRun('approve')}
                  className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium rounded-lg transition-colors shadow-lg"
                >
                  Approve
                </button>
                <button
                  onClick={() => chat.continueRun('reject')}
                  className="px-4 py-1.5 bg-red-600 hover:bg-red-500 text-white text-sm font-medium rounded-lg transition-colors shadow-lg"
                >
                  Reject
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
