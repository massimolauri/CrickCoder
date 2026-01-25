import React, { useMemo, useEffect } from 'react';
import { X, CheckCircle2, Circle, Clock, Layers } from 'lucide-react';
import ReactMarkdown from 'react-markdown';

interface Task {
    id: string;
    text: string;
    status: 'todo' | 'in-progress' | 'done';
}

interface KanbanBoardProps {
    tasks: Task[];
    onClose: () => void;
    projectPath: string;
}

const KanbanBoard: React.FC<KanbanBoardProps> = ({ tasks, onClose, projectPath }) => {
    // Prevent body scroll when open
    useEffect(() => {
        document.body.style.overflow = 'hidden';
        return () => {
            document.body.style.overflow = 'unset';
        };
    }, []);

    const columns = useMemo(() => {
        return {
            todo: tasks.filter(t => t.status === 'todo'),
            inProgress: tasks.filter(t => t.status === 'in-progress'),
            done: tasks.filter(t => t.status === 'done')
        };
    }, [tasks]);

    return (
        <div className="fixed inset-0 z-50 bg-white/80 dark:bg-black/80 backdrop-blur-xl animate-in fade-in duration-300 flex flex-col font-sans">
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200 dark:border-white/10 bg-white/50 dark:bg-black/50 shadow-sm shrink-0">
                <div className="flex items-center gap-4">
                    <div className="p-2 bg-blue-500/10 rounded-lg glass-pill">
                        <Layers className="text-blue-600 dark:text-blue-400" size={24} />
                    </div>
                    <div>
                        <h1 className="text-2xl font-bold text-gray-900 dark:text-white tracking-tight">Project Board</h1>
                        <p className="text-xs text-gray-500 dark:text-gray-400 font-mono">{projectPath}</p>
                    </div>
                </div>
                <button
                    onClick={onClose}
                    className="p-2 rounded-full hover:bg-gray-100 dark:hover:bg-white/10 transition-colors text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white"
                >
                    <X size={28} />
                </button>
            </div>

            {/* Board Grid */}
            <div className="flex-1 overflow-x-auto overflow-y-auto p-4 md:p-8 scrollbar-thin">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-6 h-auto md:h-full max-w-[1800px] mx-auto">

                    {/* TO DO Column */}
                    <Column
                        title="To Do"
                        count={columns.todo.length}
                        color="border-slate-500"
                        icon={<Circle className="text-slate-500" size={20} />}
                    >
                        {columns.todo.map(task => <TaskCard key={task.id} task={task} />)}
                    </Column>

                    {/* IN PROGRESS Column */}
                    <Column
                        title="In Progress"
                        count={columns.inProgress.length}
                        color="border-blue-500"
                        icon={<Clock className="text-blue-500 animate-pulse" size={20} />}
                    >
                        {columns.inProgress.map(task => <TaskCard key={task.id} task={task} />)}
                    </Column>

                    {/* DONE Column */}
                    <Column
                        title="Done"
                        count={columns.done.length}
                        color="border-emerald-500"
                        icon={<CheckCircle2 className="text-emerald-500" size={20} />}
                    >
                        {columns.done.map(task => <TaskCard key={task.id} task={task} />)}
                    </Column>

                </div>
            </div>
        </div>
    );
};

const Column: React.FC<{ title: string; count: number; children: React.ReactNode; color: string; icon: React.ReactNode }> = ({ title, count, children, color, icon }) => (
    <div className="glass-panel rounded-2xl p-4 flex flex-col h-[500px] md:h-full shadow-lg">
        <div className={`flex items-center justify-between mb-4 pb-4 border-b-2 ${color}`}>
            <div className="flex items-center gap-2">
                {icon}
                <h2 className="font-bold text-lg text-gray-700 dark:text-gray-200">{title}</h2>
            </div>
            <span className="glass-pill px-3 py-1 rounded-full text-xs font-bold text-gray-600 dark:text-gray-300 shadow-sm">{count}</span>
        </div>
        <div className="flex-1 overflow-y-auto space-y-3 pr-2 scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-white/10">
            {children}
        </div>
    </div>
);

const TaskCard: React.FC<{ task: Task }> = ({ task }) => (
    <div className="group relative bg-white dark:bg-[#1e1e1e] p-4 rounded-xl shadow-sm hover:shadow-lg border border-gray-100 dark:border-white/5 transition-all hover:-translate-y-1 hover:border-blue-500/30 cursor-default">
        <div className="flex justify-between items-start gap-3">
            <div className="prose dark:prose-invert prose-sm max-w-none text-gray-700 dark:text-gray-300 leading-snug line-clamp-3 group-hover:line-clamp-none transition-all">
                <ReactMarkdown>{task.text}</ReactMarkdown>
            </div>
        </div>

        <div className="mt-3 flex items-center justify-between">
            {/* ID Chip: Hidden by default, visible on hover with glow */}
            <span className="text-[10px] font-mono text-gray-400 dark:text-gray-500 bg-gray-100 dark:bg-white/5 px-1.5 py-0.5 rounded opacity-0 group-hover:opacity-100 transition-opacity duration-300 shadow-sm border border-transparent group-hover:border-blue-500/20 group-hover:text-blue-500 group-hover:shadow-[0_0_10px_rgba(59,130,246,0.2)]">
                #{task.id}
            </span>

            {task.status === 'in-progress' && (
                <div className="h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse shadow-[0_0_8px_rgba(59,130,246,0.6)]" />
            )}
        </div>

        {/* Floating "Exploded Info" Tooltip on deep hover (optional approach if simple expand isn't enough) */}
        {/* We rely on line-clamp removal for "exploded" text view above. */}
    </div>
);

export default KanbanBoard;
