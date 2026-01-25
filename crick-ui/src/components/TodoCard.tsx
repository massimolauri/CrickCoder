import { useState, useEffect, useMemo } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
    Minimize2, RefreshCw, Loader2, ListTodo,
    CheckCircle2, Circle, Timer, Trash2, Maximize2
} from 'lucide-react';
import KanbanBoard from './KanbanBoard';

interface TodoCardProps {
    projectPath: string;
    sessionId?: string | null;
}

export default function TodoCard({ projectPath, sessionId }: TodoCardProps) {
    const [content, setContent] = useState<string>('');
    const [rawContent, setRawContent] = useState<string>('');
    const [isOpen, setIsOpen] = useState(true);
    const [loading, setLoading] = useState(false);
    const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
    const [showKanban, setShowKanban] = useState(false);

    const fetchTasks = async () => {
        if (!projectPath || !sessionId) return;
        console.log("Fetching tasks for project:", projectPath, "Session:", sessionId);
        setLoading(true);
        try {
            const response = await fetch(`/api/project/brain/task.md?project_path=${encodeURIComponent(projectPath)}&session_id=${encodeURIComponent(sessionId)}&t=${Date.now()}`);
            const data = await response.json();

            if (data.error) {
                if (data.error === "File not found") {
                    setContent("# No tasks found\nAsk the Planner to create a task list.");
                    setRawContent(""); // Fix: Clear raw content to reset Kanban view
                } else {
                    console.error("Error fetching tasks:", data.error);
                    setRawContent(""); // Fix: Clear on error too
                }
            } else {
                const rawContent = data.content || '';

                // Store raw content for Kanban parsing to strictly preserve IDs
                // But for the simple view, we still clean it

                // Remove metadata comments (<!-- id: ... -->)
                let cleanContent = rawContent.replace(/<!--.*?-->/g, '');

                // FIX: Ensure all [ ] or [x] start with a hyphen for correct Markdown list rendering
                cleanContent = cleanContent.replace(/^(\s*)(\[([ x/])\])/gm, '$1- $2');

                setContent(cleanContent);
                // We'll parse Kanban from rawContent inside useMemo logic below (need to update state or effect)
                setRawContent(rawContent);
                setLastUpdated(new Date());
            }
        } catch (err) {
            console.error("Failed to fetch tasks", err);
        } finally {
            setTimeout(() => setLoading(false), 300);
        }
    };

    useEffect(() => {
        if (projectPath && sessionId) {
            fetchTasks();
            const interval = setInterval(fetchTasks, 5000); // Poll every 5 seconds
            return () => clearInterval(interval);
        }
    }, [projectPath, sessionId]);

    // Parse tasks for Kanban
    const kanbanTasks = useMemo(() => {
        if (!rawContent) return [];
        const lines = rawContent.split('\n');
        const tasks: any[] = [];
        let idCounter = 1;

        lines.forEach(line => {
            // Match task line: - [x] Text <!-- id: 123 -->
            const todoMatch = line.match(/^(\s*)[-]\s*\[([ x/])\]\s*(.*?)(<!--\s*id:\s*(\w+)\s*-->)?$/);
            // Also lenient match if hyphens are missing in raw but added later? 
            // Better to match strictly standard or the one we use.
            // Our task.md usually has "- [ ]"

            if (todoMatch) {
                const statusChar = todoMatch[2];
                let text = todoMatch[3].trim();
                const explicitId = todoMatch[5]; // Capture group 5 is ID

                let status: 'todo' | 'in-progress' | 'done' = 'todo';

                if (statusChar === 'x') status = 'done';
                if (statusChar === '/') status = 'in-progress';

                tasks.push({
                    id: explicitId ? explicitId : `T${idCounter++}`, // Use explicit ID if found
                    text,
                    status
                });
            }
        });
        return tasks;
    }, [rawContent]);

    if (!projectPath) return null;

    if (!isOpen) {
        return (
            <button
                onClick={() => setIsOpen(true)}
                className="fixed top-20 right-4 z-50 glass-panel p-3 rounded-full shadow-lg border border-white/20 hover:scale-110 active:scale-95 transition-all duration-300 group animate-in slide-in-from-right-10"
                title="Show Tasks"
            >
                <div className="absolute top-0 right-0 w-3 h-3 bg-emerald-500 rounded-full animate-pulse"></div>
                <ListTodo size={20} className="text-crick-accent dark:text-emerald-400 group-hover:rotate-12 transition-transform" />
            </button>
        );
    }

    return (
        <>
            {showKanban && (
                <KanbanBoard
                    tasks={kanbanTasks}
                    onClose={() => setShowKanban(false)}
                    projectPath={projectPath}
                />
            )}

            <div className={`fixed top-20 right-4 z-50 w-80 md:w-96 max-h-[70vh] flex flex-col glass-panel rounded-2xl shadow-2xl animate-in zoom-in-95 slide-in-from-right-8 duration-300 border border-white/10 dark:border-white/5 overflow-hidden ${showKanban ? 'opacity-0 pointer-events-none' : 'opacity-100'}`}>
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b border-gray-100 dark:border-white/5 bg-white/40 dark:bg-black/20 hover:bg-white/60 dark:hover:bg-black/30 transition-colors backdrop-blur-xl cursor-move select-none">
                    <div className="flex items-center gap-2.5">
                        <div className="bg-emerald-500/10 p-1.5 rounded-lg border border-emerald-500/20">
                            <ListTodo size={16} className="text-emerald-500" />
                        </div>
                        <div className="flex flex-col">
                            <span className="font-bold text-sm text-crick-text-primary tracking-tight">Crick Tasks</span>
                            {lastUpdated && !loading && (
                                <span className="text-[10px] text-gray-400 font-mono">
                                    Updated {lastUpdated.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                                </span>
                            )}
                            {loading && (
                                <span className="text-[10px] text-emerald-500 font-mono animate-pulse">
                                    Syncing...
                                </span>
                            )}
                        </div>
                    </div>
                    <div className="flex items-center gap-1">
                        <button
                            onClick={() => setShowKanban(true)}
                            className="p-2 rounded-lg hover:bg-blue-500/10 hover:text-blue-500 text-gray-500 dark:text-gray-400 transition-colors"
                            title="Maximize Board View"
                        >
                            <Maximize2 size={14} />
                        </button>
                        <button
                            onClick={async (e) => {
                                e.stopPropagation();
                                if (!window.confirm("Are you sure you want to clear all tasks?")) return;
                                try {
                                    setLoading(true);
                                    await fetch(`/api/project/brain/task.md?project_path=${encodeURIComponent(projectPath)}&session_id=${encodeURIComponent(sessionId || '')}`, {
                                        method: 'DELETE'
                                    });
                                    await fetchTasks();
                                } catch (err) {
                                    console.error("Failed to clear tasks", err);
                                } finally {
                                    setLoading(false);
                                }
                            }}
                            className="p-2 rounded-lg hover:bg-red-500/10 hover:text-red-500 text-gray-500 dark:text-gray-400 transition-colors"
                            title="Clear All Tasks"
                        >
                            <Trash2 size={14} />
                        </button>
                        <button
                            onClick={fetchTasks}
                            className={`p-2 rounded-lg hover:bg-black/5 dark:hover:bg-white/5 text-gray-500 dark:text-gray-400 transition-all ${loading ? 'animate-spin text-emerald-500' : 'hover:rotate-180 duration-500'}`}
                            title="Sync Now"
                        >
                            {loading ? <Loader2 size={14} /> : <RefreshCw size={14} />}
                        </button>
                        <button
                            onClick={() => setIsOpen(false)}
                            className="p-2 rounded-lg hover:bg-red-500/10 hover:text-red-500 text-gray-500 dark:text-gray-400 transition-colors"
                            title="Minimize"
                        >
                            <Minimize2 size={14} />
                        </button>
                    </div>
                </div>

                {/* Content with Custom Renderers */}
                <div className={`flex-1 overflow-y-auto p-5 text-sm custom-scrollbar relative ${loading ? 'opacity-80' : 'opacity-100'} transition-all duration-300`}>
                    {loading && !content && (
                        <div className="space-y-3 animate-pulse">
                            <div className="h-4 bg-gray-200 dark:bg-white/5 rounded w-3/4"></div>
                            <div className="h-4 bg-gray-200 dark:bg-white/5 rounded w-1/2"></div>
                        </div>
                    )}

                    <div className="prose dark:prose-invert prose-sm max-w-none text-crick-text-secondary">
                        <ReactMarkdown
                            remarkPlugins={[remarkGfm]}
                            components={{
                                li: ({ children, ...props }) => {
                                    return <li className="flex items-start gap-2 my-1" {...props}>{children}</li>;
                                },
                                input: ({ checked }) => {
                                    if (checked) {
                                        return <CheckCircle2 size={16} className="text-emerald-500 mt-0.5 shrink-0" />;
                                    }
                                    return <Circle size={16} className="text-gray-400 mt-0.5 shrink-0" />;
                                },
                                p: ({ children }) => {
                                    const text = String(children);
                                    if (text.startsWith('[/]')) {
                                        return (
                                            <div className="flex items-center gap-2 my-2 py-1.5 px-2 bg-blue-500/5 rounded-lg border border-blue-500/10 shadow-sm">
                                                <Timer size={14} className="text-blue-500 animate-pulse shrink-0" />
                                                <span className="font-medium text-blue-500 text-xs">{text.replace('[/]', '').trim()}</span>
                                            </div>
                                        );
                                    }
                                    return <p className="leading-relaxed mb-2">{children}</p>;
                                },
                                h1: ({ children }) => (
                                    <h1 className="text-xs font-bold uppercase tracking-wider text-gray-500 dark:text-gray-400 mt-6 mb-3 flex items-center gap-2 after:h-[1px] after:flex-1 after:bg-gray-200 dark:after:bg-white/10">
                                        {children}
                                    </h1>
                                ),
                                h2: ({ children }) => {
                                    const text = String(children).toLowerCase();
                                    let colorClass = "bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border-zinc-500/20"; // Default

                                    if (text.includes('progress')) {
                                        colorClass = "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20";
                                    } else if (text.includes('done') || text.includes('complete')) {
                                        colorClass = "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20";
                                    } else if (text.includes('todo') || text.includes('to do')) {
                                        colorClass = "bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20";
                                    }

                                    return (
                                        <h2 className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wide border mt-4 mb-2 shadow-sm ${colorClass}`}>
                                            {children}
                                        </h2>
                                    );
                                },
                                h3: ({ children }) => (
                                    <h3 className="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-purple-500/10 text-purple-600 dark:text-purple-400 border border-purple-500/20 mt-2 mb-1">
                                        {children}
                                    </h3>
                                ),
                                hr: () => <hr className="my-4 border-gray-100 dark:border-white/5" />
                            }}
                        >
                            {content?.replace(/- \[\/\]/g, '\n\n[/]') || ""}
                        </ReactMarkdown>
                    </div>
                </div>

                {/* Footer Status */}
                <div className="px-4 py-2 border-t border-gray-100 dark:border-white/5 bg-gray-50/30 dark:bg-white/[0.02] text-[10px] flex justify-between items-center text-gray-400 font-mono">
                    <span className="flex items-center gap-1.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse"></span>
                        Brain Active
                    </span>
                </div>

                {/* Neon accent at bottom */}
                <div className="absolute bottom-0 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-emerald-500/50 to-transparent opacity-50"></div>
            </div>
        </>
    );
}
