import { useState, useEffect, useRef } from 'react';
import { Upload, X, LayoutTemplate, CheckCircle, Loader2, Trash2 } from 'lucide-react';

interface Template {
    id: string;
    name: string;
    description?: string;
    author?: string;
    version?: string;
    preview_url: string | null;
}

interface LogEvent {
    status: 'extracting' | 'validating' | 'indexing' | 'complete' | 'error' | 'warning';
    message?: string;
    total?: number;
    current?: number;
    filename?: string;
    template_id?: string;
    preview_url?: string;
}

interface TemplatesPanelProps {
    onClose: () => void;
    projectPath: string;
}

export default function TemplatesPanel({ onClose, projectPath }: TemplatesPanelProps) {
    const [templates, setTemplates] = useState<Template[]>([]);
    const [loading, setLoading] = useState(true);
    const [uploading, setUploading] = useState(false);
    const [logs, setLogs] = useState<LogEvent[]>([]);
    const [progress, setProgress] = useState(0);
    const logsEndRef = useRef<HTMLDivElement>(null);

    // Fetch Templates
    useEffect(() => {
        fetchTemplates();
    }, [projectPath]);

    const fetchTemplates = async () => {
        try {
            setLoading(true);
            const res = await fetch('/api/templates');
            const data = await res.json();
            setTemplates(data.templates || []);
        } catch (err) {
            console.error("Failed to fetch templates", err);
        } finally {
            setLoading(false);
        }
    };

    // New Delete Handler
    const handleDelete = async (templateId: string, event: React.MouseEvent) => {
        event.stopPropagation(); // Prevent card click

        if (!confirm('Sei sicuro di voler eliminare questo template?')) return;

        try {
            const res = await fetch(`/api/templates/${templateId}`, {
                method: 'DELETE',
            });
            const data = await res.json();

            if (res.ok) {
                // Refresh list
                await fetchTemplates();
            } else {
                alert('Errore cancellazione: ' + data.detail);
            }
        } catch (err) {
            console.error(err);
            alert('Errore di connessione durante cancellazione.');
        }
    };

    // Auto-scroll logs
    useEffect(() => {
        if (logsEndRef.current) {
            logsEndRef.current.scrollIntoView({ behavior: 'smooth' });
        }
    }, [logs]);

    const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (!file) return;

        setUploading(true);
        setLogs([]);
        setProgress(0);

        const formData = new FormData();
        formData.append("file", file);

        // SSE connection via fetch is tricky, but we can use basic fetch and read the stream
        try {
            const response = await fetch('/api/templates/upload', {
                method: 'POST',
                body: formData,
            });

            if (!response.ok) throw new Error("Upload failed");
            if (!response.body) throw new Error("No response body");

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { value, done } = await reader.read();
                if (done) break;

                const chunk = decoder.decode(value, { stream: true });
                buffer += chunk;

                // Process lines (SSE format: "data: ...\n\n")
                const lines = buffer.split('\n\n');
                buffer = lines.pop() || ''; // Keep incomplete part

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        const jsonStr = line.slice(6);
                        try {
                            const event: LogEvent = JSON.parse(jsonStr);
                            setLogs(prev => [...prev, event]);

                            if (event.status === 'indexing' && event.total) {
                                setProgress(Math.round((event.current! / event.total) * 100));
                            }

                            if (event.status === 'complete') {
                                setProgress(100);
                                fetchTemplates(); // Refresh list
                            }
                        } catch (e) {
                            console.error("Parse error", e);
                        }
                    }
                }
            }

        } catch (error) {
            setLogs(prev => [...prev, { status: 'error', message: String(error) }]);
        } finally {
            setUploading(false);
        }
    };

    return (
        <div className="absolute inset-x-0 bottom-0 top-16 z-20 bg-white/95 dark:bg-[#0d1117]/95 backdrop-blur-xl border-t border-gray-100 dark:border-white/5 overflow-hidden flex flex-col animate-in slide-in-from-bottom-4 fade-in duration-300">

            {/* Header */}
            <div className="flex items-center justify-between px-8 py-6 border-b border-gray-100 dark:border-white/5 bg-white/50 dark:bg-[#0d1117]/50">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
                        <LayoutTemplate className="w-6 h-6 text-purple-600 dark:text-purple-400" />
                    </div>
                    <div>
                        <h2 className="text-xl font-bold text-crick-text-primary">Templates Library</h2>
                        <p className="text-sm text-crick-text-secondary">Manage your graphic templates and knowledge base</p>
                    </div>
                </div>

                <button
                    onClick={onClose}
                    className="p-2 hover:bg-gray-100 dark:hover:bg-white/5 rounded-full transition-colors text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                >
                    <X size={24} />
                </button>
            </div>

            <div className="flex-1 overflow-y-auto p-8">
                <div className="max-w-6xl mx-auto">

                    {/* Upload Section */}
                    <div className="mb-10 bg-crick-surface border-2 border-dashed border-gray-200 dark:border-white/10 rounded-2xl p-8 text-center hover:border-purple-300 dark:hover:border-purple-500/50 hover:bg-purple-50/30 dark:hover:bg-purple-900/10 transition-all group relative overflow-hidden">
                        <input
                            type="file"
                            accept=".zip"
                            onChange={handleFileUpload}
                            disabled={uploading}
                            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                        />

                        <div className="relative z-0 pointer-events-none">
                            <div className="w-16 h-16 bg-purple-100 dark:bg-purple-900/30 rounded-full flex items-center justify-center mx-auto mb-4 group-hover:scale-110 transition-transform shadow-sm">
                                <Upload className="w-8 h-8 text-purple-600 dark:text-purple-400" />
                            </div>
                            <h3 className="text-lg font-medium text-crick-text-primary mb-1">Upload Template ZIP</h3>
                            <p className="text-sm text-crick-text-secondary">Drag & drop or click to upload a new template package</p>
                        </div>
                    </div>

                    {/* Progress & Logs */}
                    {(uploading || logs.length > 0) && (
                        <div className="mb-10 bg-crick-surface border border-gray-200 dark:border-white/10 rounded-xl p-4 font-mono text-xs shadow-inner">
                            <div className="flex items-center justify-between mb-2">
                                <span className="text-gray-500 font-bold uppercase tracking-wider">Installation Log</span>
                                <span className="text-purple-600 dark:text-purple-400">{progress}%</span>
                            </div>

                            {/* Progress Bar */}
                            <div className="h-1.5 w-full bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden mb-4">
                                <div
                                    className="h-full bg-purple-500 transition-all duration-300 ease-out"
                                    style={{ width: `${progress}%` }}
                                />
                            </div>

                            {/* Log Stream */}
                            <div className="h-32 overflow-y-auto space-y-1 scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600">
                                {logs.map((log, i) => (
                                    <div key={i} className={`flex items-start gap-2 ${log.status === 'error' ? 'text-red-500 dark:text-red-400' :
                                        log.status === 'complete' ? 'text-green-600 dark:text-green-400' : 'text-gray-600 dark:text-gray-400'
                                        }`}>
                                        <span className="opacity-50">[{new Date().toLocaleTimeString()}]</span>
                                        <span>
                                            {log.message || log.filename}
                                        </span>
                                    </div>
                                ))}
                                <div ref={logsEndRef} />
                            </div>
                        </div>
                    )}

                    {/* Gallery Grid */}
                    <h3 className="text-lg font-bold text-crick-text-primary mb-4 flex items-center gap-2">
                        Installed Templates
                        <span className="text-xs font-normal text-gray-500 dark:text-gray-400 bg-gray-100 dark:bg-gray-800 px-2 py-0.5 rounded-full border border-gray-200 dark:border-white/10">{templates.length}</span>
                    </h3>

                    {loading ? (
                        <div className="flex justify-center py-12">
                            <Loader2 className="w-8 h-8 text-purple-500 animate-spin" />
                        </div>
                    ) : templates.length === 0 ? (
                        <div className="text-center py-12 text-gray-400 italic">
                            No templates installed yet. Upload one to get started.
                        </div>
                    ) : (
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {templates.map(tpl => (
                                <div key={tpl.id} className="bg-white dark:bg-[#161b22] border border-gray-100 dark:border-white/10 rounded-xl overflow-hidden group hover:border-purple-200 dark:hover:border-purple-500/30 transition-all shadow-sm hover:shadow-lg hover:-translate-y-1">
                                    {/* Preview Image */}
                                    <div className="aspect-video bg-gray-50 dark:bg-gray-900 relative overflow-hidden border-b border-gray-100 dark:border-white/5 group-hover:opacity-100 transition-opacity">
                                        {tpl.preview_url ? (
                                            <img
                                                src={tpl.preview_url}
                                                alt={tpl.name}
                                                className="w-full h-full object-cover"
                                                onError={(e) => {
                                                    (e.target as HTMLImageElement).src = 'https://placehold.co/600x400?text=No+Preview';
                                                }}
                                            />
                                        ) : (
                                            <div className="w-full h-full flex items-center justify-center text-gray-400">
                                                <LayoutTemplate className="w-12 h-12 opacity-20" />
                                            </div>
                                        )}

                                        {/* Delete Button Overlay */}
                                        <button
                                            onClick={(e) => handleDelete(tpl.id, e)}
                                            className="absolute top-2 right-2 p-1.5 bg-red-500/90 text-white rounded-md opacity-0 group-hover:opacity-100 transition-opacity hover:bg-red-600 shadow-md z-10"
                                            title="Elimina Template"
                                        >
                                            <Trash2 className="w-4 h-4" />
                                        </button>
                                    </div>

                                    <div className="p-4">
                                        <div className="flex justify-between items-start mb-1">
                                            <h4 className="font-bold text-crick-text-primary truncate pr-2" title={tpl.name}>{tpl.name}</h4>
                                            {tpl.version && (
                                                <span className="text-[10px] bg-gray-100 dark:bg-white/5 text-gray-500 dark:text-gray-400 px-1.5 py-0.5 rounded border border-gray-200 dark:border-white/10">
                                                    v{tpl.version}
                                                </span>
                                            )}
                                        </div>

                                        {tpl.author && (
                                            <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">by <span className="text-gray-700 dark:text-gray-300 font-medium">{tpl.author}</span></p>
                                        )}

                                        {tpl.description && (
                                            <p className="text-xs text-gray-500 dark:text-gray-400 line-clamp-2 mb-3 h-8 leading-relaxed">
                                                {tpl.description}
                                            </p>
                                        )}

                                        <div className="flex items-center gap-2 mt-2 text-xs text-green-600 dark:text-green-400 border-t border-gray-100 dark:border-white/5 pt-3 font-medium">
                                            <CheckCircle size={12} />
                                            <span>Ready for Architect Agent</span>
                                        </div>
                                    </div>
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
