import { useState, useEffect } from 'react';
import { X, Check, FileCode, ArrowLeftRight, AlertTriangle, RotateCcw } from 'lucide-react';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { chatService } from '@/services/chatService';

interface ReviewModalProps {
    runId: string;
    sessionId: string;
    projectPath: string;
    onClose: () => void;
    onReject: (files: string[]) => void;
}

export default function ReviewModal({
    runId,
    sessionId,
    projectPath,
    onClose,
    onReject
}: ReviewModalProps) {
    const [files, setFiles] = useState<string[]>([]);
    const [selectedFile, setSelectedFile] = useState<string | null>(null);
    const [diffs, setDiffs] = useState<Record<string, string>>({});
    const [loading, setLoading] = useState(true);
    const [checkedFiles, setCheckedFiles] = useState<Set<string>>(new Set());
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        loadData();
    }, [runId]);

    const loadData = async () => {
        try {
            setLoading(true);
            // 1. Get List of files
            const fileList = await chatService.getRunFiles(runId, sessionId, projectPath);
            setFiles(fileList);

            // Select first file by default
            if (fileList.length > 0) {
                setSelectedFile(fileList[0]);
                // Default: Checked means "Marked for Rejection" (Rollback)
                // Adjust logic: Maybe easier if user selects what to KEEP? 
                // User asked: "Accept Single / Reject Single".
                // Let's assume selection = Action Default. 
                // Let's select ALL for rejection by default? Or NONE?
                // Usually "Undo" implies undoing everything. So default select all.
                setCheckedFiles(new Set(fileList));
            }

            // 2. Get Diffs (Batch for all)
            const diffData = await chatService.getDiffs(fileList, runId, sessionId, projectPath);
            setDiffs(diffData);

        } catch (err) {
            setError(String(err));
        } finally {
            setLoading(false);
        }
    };

    const toggleFile = (file: string) => {
        const next = new Set(checkedFiles);
        if (next.has(file)) {
            next.delete(file);
        } else {
            next.add(file);
        }
        setCheckedFiles(next);
    };

    const handleRejectSelected = () => {
        const list = Array.from(checkedFiles);
        if (list.length === 0) {
            // Nothing to reject = Keep everything (Accept All)
            onClose();
            return;
        }
        onReject(list);
    };

    const handleAcceptAll = () => {
        onClose(); // Just close, do nothing updates
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
            <div className="bg-white dark:bg-[#1e1e1e] w-[90vw] h-[85vh] rounded-xl shadow-2xl flex flex-col border border-gray-200 dark:border-[#3e3e42] overflow-hidden">

                {/* HEADER */}
                <div className="h-14 border-b border-gray-200 dark:border-[#3e3e42] flex items-center justify-between px-6 bg-gray-50 dark:bg-[#252526]">
                    <div className="flex items-center gap-3">
                        <ArrowLeftRight className="text-blue-500" size={20} />
                        <h2 className="font-semibold text-lg text-gray-800 dark:text-gray-100">Review Changes</h2>
                        <span className="text-xs bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 px-2 py-0.5 rounded-full font-mono">
                            Run: {runId.slice(0, 8)}
                        </span>
                    </div>
                    <button onClick={onClose} className="p-2 hover:bg-gray-200 dark:hover:bg-white/5 rounded-full text-gray-500 transition-colors">
                        <X size={20} />
                    </button>
                </div>

                {error && (
                    <div className="bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 px-4 py-2 text-sm border-b border-red-200 dark:border-red-800/50 flex items-center gap-2">
                        <AlertTriangle size={14} />
                        Failed to load changes: {error}
                    </div>
                )}

                {/* CONTENT */}
                <div className="flex-1 flex overflow-hidden">

                    {/* SIDEBAR: File List */}
                    <div className="w-1/4 min-w-[250px] border-r border-gray-200 dark:border-[#3e3e42] bg-gray-50/50 dark:bg-[#1e1e1e] flex flex-col">
                        <div className="p-4 border-b border-gray-200 dark:border-[#3e3e42] bg-white dark:bg-[#202020]">
                            <h3 className="text-xs font-bold uppercase text-gray-500 tracking-wider mb-2">Modified Files ({files.length})</h3>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => setCheckedFiles(new Set(files))}
                                    className="text-xs text-blue-500 hover:underline"
                                >
                                    Select All
                                </button>
                                <span className="text-gray-300">|</span>
                                <button
                                    onClick={() => setCheckedFiles(new Set())}
                                    className="text-xs text-blue-500 hover:underline"
                                >
                                    Select None
                                </button>
                            </div>
                        </div>

                        <div className="overflow-y-auto flex-1 p-2 space-y-1">
                            {loading ? (
                                <div className="p-4 text-center text-gray-400 animate-pulse">Loading diffs...</div>
                            ) : (
                                files.map(file => (
                                    <div
                                        key={file}
                                        onClick={() => setSelectedFile(file)}
                                        className={`flex items-center gap-3 p-2.5 rounded-lg cursor-pointer transition-all border ${selectedFile === file
                                            ? 'bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800'
                                            : 'border-transparent hover:bg-gray-100 dark:hover:bg-white/5'
                                            }`}
                                    >
                                        <input
                                            type="checkbox"
                                            checked={checkedFiles.has(file)}
                                            onChange={(e) => {
                                                e.stopPropagation();
                                                toggleFile(file);
                                            }}
                                            className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                                        />
                                        <FileCode size={16} className="text-gray-400 shrink-0" />
                                        <span className="text-sm font-mono truncate text-gray-700 dark:text-gray-300" title={file}>
                                            {file}
                                        </span>
                                    </div>
                                ))
                            )}
                        </div>
                    </div>

                    {/* MAIN: Diff Viewer */}
                    <div className="flex-1 bg-[#1e1e1e] overflow-hidden flex flex-col">
                        {selectedFile ? (
                            <div className="flex-1 overflow-auto custom-scrollbar">
                                {diffs[selectedFile] ? (
                                    <SyntaxHighlighter
                                        language="diff"
                                        style={vscDarkPlus}
                                        showLineNumbers={true}
                                        wrapLines={true}
                                        customStyle={{ margin: 0, padding: '1.5rem', fontSize: '13px', lineHeight: '1.5', background: 'transparent' }}
                                        lineProps={(lineNumber) => {
                                            const code = diffs[selectedFile] || "";
                                            const lines = code.split('\n');
                                            const line = lines[lineNumber - 1]; // lineNumber is 1-indexed
                                            const style: React.CSSProperties = { display: 'block' };

                                            if (line?.startsWith('+')) {
                                                style.backgroundColor = 'rgba(16, 185, 129, 0.2)'; // Green-500 @ 20%
                                            } else if (line?.startsWith('-')) {
                                                style.backgroundColor = 'rgba(239, 68, 68, 0.2)'; // Red-500 @ 20%
                                            }

                                            return { style };
                                        }}
                                    >
                                        {diffs[selectedFile]}
                                    </SyntaxHighlighter>
                                ) : (
                                    <div className="flex items-center justify-center h-full text-gray-500">
                                        {loading ? 'Loading diff...' : 'No diff available (New file?)'}
                                    </div>
                                )}
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center h-full text-gray-500 gap-4">
                                <ArrowLeftRight size={48} className="opacity-20" />
                                <p>Select a file to view changes</p>
                            </div>
                        )}

                        {/* Diff Legend / Info */}
                        <div className="h-8 bg-[#252526] border-t border-[#3e3e42] flex items-center px-4 text-xs text-gray-400 gap-4 font-mono">
                            <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-500/50 rounded-full"></span> Removed</span>
                            <span className="flex items-center gap-1"><span className="w-2 h-2 bg-green-500/50 rounded-full"></span> Added</span>
                        </div>
                    </div>
                </div>

                {/* FOOTER */}
                <div className="h-16 border-t border-gray-200 dark:border-[#3e3e42] bg-gray-50 dark:bg-[#252526] px-6 flex items-center justify-between">
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                        {checkedFiles.size > 0 ? (
                            <span className="flex items-center gap-2 text-amber-600 dark:text-amber-500 font-medium">
                                <AlertTriangle size={16} />
                                {checkedFiles.size} file(s) marked for rejection/rollback
                            </span>
                        ) : (
                            <span className="flex items-center gap-2 text-emerald-600 dark:text-emerald-500 font-medium">
                                <Check size={16} />
                                All changes will be kept (Accepted)
                            </span>
                        )}
                    </div>

                    <div className="flex gap-3">
                        <button
                            onClick={handleAcceptAll}
                            className="px-5 py-2 rounded-lg font-medium text-gray-600 hover:bg-gray-200 dark:text-gray-300 dark:hover:bg-white/10 transition-colors"
                        >
                            Cancel / Keep All
                        </button>
                        <button
                            onClick={handleRejectSelected}
                            disabled={checkedFiles.size === 0}
                            className={`px-5 py-2 rounded-lg font-medium flex items-center gap-2 transition-all shadow-lg ${checkedFiles.size === 0
                                ? 'bg-gray-200 text-gray-400 cursor-not-allowed dark:bg-white/5 dark:text-gray-600'
                                : 'bg-red-600 hover:bg-red-700 text-white hover:scale-105'
                                }`}
                        >
                            <RotateCcw size={16} />
                            {checkedFiles.size === files.length ? 'Reject All Changes' : `Reject ${checkedFiles.size} Files`}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
