import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import {
  Menu, ChevronRight, Settings, Folder, LayoutTemplate
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
    <div className={`flex h-screen w-full ${THEME.bg} text-slate-300 font-sans overflow-hidden selection:bg-emerald-500/30 selection:text-emerald-200`}>
      {/* Left sidebar */}
      <div className={`w-16 flex flex-col items-center py-6 ${THEME.sidebar} hidden sm:flex z-20`}>
        <button
          onClick={() => { setShowSessions(!showSessions); setShowSettings(false); setShowTemplates(false); }}
          className="p-2.5 bg-white/5 rounded-xl mb-6 border border-white/10 shadow-lg hover:bg-white/10 transition-colors cursor-pointer"
        >
          <Menu className="w-6 h-6 text-emerald-400" />
        </button>

        {/* Templates Button */}
        <button
          onClick={() => { setShowTemplates(!showTemplates); setShowSettings(false); setShowSessions(false); }}
          className={`p-2.5 rounded-xl mb-4 border transition-colors cursor-pointer relative group ${showTemplates ? 'bg-purple-500/20 border-purple-500/50' : 'bg-transparent border-transparent hover:bg-white/5'}`}
          title="Templates Library"
        >
          <LayoutTemplate className={`w-6 h-6 ${showTemplates ? 'text-purple-400' : 'text-slate-500 group-hover:text-purple-400'}`} />
          {!showTemplates && (
            <span className="absolute left-14 top-1/2 -translate-y-1/2 bg-[#0d1117] border border-[#30363d] text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50">
              Templates
            </span>
          )}
        </button>

        {/* Flexible space to push content to bottom */}
        <div className="flex-1" />

        {/* Settings button and indicators (at bottom) */}
        <div className="mt-auto flex flex-col items-center gap-3 py-4">
          <button
            onClick={() => { setShowSettings(!showSettings); setShowSessions(false); setShowTemplates(false); }}
            className={`p-3 rounded-xl transition-all ${showSettings ? 'bg-[#1f6feb]/20 text-blue-400' : 'text-slate-500 hover:text-slate-300'}`}
            title="Settings"
          >
            <Settings size={20} />
          </button>
          <HealthIndicator />
        </div>
      </div>

      {/* Sessions sidebar */}
      {showSessions && projectPath && (
        <div className={`w-80 ${THEME.sidebar} border-r border-[#30363d] flex flex-col py-6 overflow-y-auto z-10`}>
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
      <div className="flex-1 flex flex-col relative">
        {/* Header */}
        <header className="h-14 border-b border-[#30363d] flex items-center justify-between px-6 bg-[#010409]/90 backdrop-blur-md z-10">
          <div className="flex items-center gap-3">
            <span className="font-bold text-sm text-slate-100 tracking-wide">
              crick<span className="text-emerald-500">coder</span>
            </span>
            <div className="hidden md:flex items-center gap-2 text-[10px] font-mono text-slate-500 bg-[#0d1117] px-2 py-1 rounded border border-[#30363d]">
              <Folder size={10} /> {projectPath ? (projectPath.length > 50 ? '...' + projectPath.slice(-50) : projectPath) : 'NO PROJECT LINKED'}
            </div>
          </div>
        </header>

        {/* Settings panel */}
        {showSettings && (
          <div className="absolute top-14 left-0 right-0 z-30 bg-[#0d1117]/95 border-b border-[#30363d] p-6 animate-in slide-in-from-top-2 shadow-2xl">
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
                    className="flex-1 bg-[#010409] border border-[#30363d] rounded px-3 py-2 text-sm font-mono text-emerald-100 outline-none focus:border-emerald-500/50 transition-colors"
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
                    className="w-full bg-[#010409] border border-[#30363d] rounded px-3 py-2 text-sm text-slate-300 outline-none focus:border-[#1f6feb]/50 transition-colors"
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
                    className="w-full bg-[#010409] border border-[#30363d] rounded px-3 py-2 text-sm text-slate-300 outline-none focus:border-[#1f6feb]/50 transition-colors"
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
                    className="w-full bg-[#010409] border border-[#30363d] rounded px-3 py-2 text-sm text-slate-300 outline-none focus:border-emerald-500/50 transition-colors"
                    placeholder="sk-..."
                  />
                  <p className="text-xs text-slate-500 mt-1">The API key is stored locally in your browser.</p>
                </div>
              </div>

              {/* Save button */}
              <div className="flex justify-end pt-4">
                <button
                  onClick={() => setShowSettings(false)}
                  className="px-5 py-2 bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-bold rounded-lg transition-colors shadow-lg"
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
              <div className="flex flex-col items-center justify-center h-full py-16 text-center">

                <h2 className="text-2xl font-bold text-slate-200 mb-2">Crick<span className="text-emerald-500">Coder</span></h2>
                <p className="text-slate-400 max-w-md">
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
                      className="p-3 bg-[#1f6feb] hover:bg-[#388bfd] text-white rounded-full border border-[#30363d] shadow-lg transition-colors flex items-center justify-center"
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
        <div className="p-4 bg-[#0d1117] border-t border-[#30363d]">
          <ChatInput
            onSubmit={handleSubmit}
            onCancel={handleCancel}
            streaming={chat.streaming}
            disabled={chat.streaming || health.isOffline}
            placeholder={placeholder}
          />

          {/* Controls below chat */}
          <div className="max-w-4xl mx-auto mt-3 flex items-center justify-between">
            {/* Agent selector (left) */}
            <div className="flex items-center gap-2">
              <div className="flex bg-[#0d1117] border border-[#30363d] rounded-xl p-1 shadow-inner">
                <button
                  onClick={() => chat.setSelectedAgentId("ARCHITECT")}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${chat.selectedAgentId === "ARCHITECT" ? "bg-[#1f6feb] text-white shadow-md" : "text-slate-400 hover:text-slate-300 hover:bg-[#161b22]"}`}
                >
                  ARCHITECT
                </button>
                <button
                  onClick={() => chat.setSelectedAgentId("CODER")}
                  className={`px-4 py-1.5 rounded-lg text-sm font-medium transition-all ${chat.selectedAgentId === "CODER" ? "bg-emerald-600 text-white shadow-md" : "text-slate-400 hover:text-slate-300 hover:bg-[#161b22]"}`}
                >
                  CODER
                </button>
              </div>
              <div className="flex flex-col">
                <span className="ml-2 text-sm font-medium text-slate-500">
                  Talking to: {chat.selectedAgentId}
                </span>
                <span className="ml-2 text-xs text-slate-600 mt-0.5">
                  {chat.selectedAgentId === "ARCHITECT"
                    ? "Analyzes codebase, designs architecture - does not write code"
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