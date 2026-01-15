import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism';
import { FileText } from 'lucide-react';
import TerminalOutput from '@/components/common/TerminalOutput';
import ToolBadge from '@/components/common/ToolBadge';
import AgentHeader from '@/components/common/AgentHeader';
import type { TimelineItem } from '@/types/api.types';

export function renderTimelineItem(item: TimelineItem, index: number): React.ReactNode {
  switch (item.type) {
    case 'terminal':
      return <TerminalOutput key={index} command={item.command} output={item.output} agent={item.agent} />;
    case 'tool':
      return <ToolBadge key={index} tool={item.tool} args={item.args} status={item.status} agent={item.agent} />;
    case 'text':
      return (
        <div key={index} className="flex flex-col animate-in fade-in duration-300">
          <AgentHeader name={item.agent} />
          <div className="text-sm text-crick-text-primary leading-relaxed font-sans mb-2 pl-1 markdown-body">
            <ReactMarkdown
              remarkPlugins={[]}
              components={{
                code({ node, inline, className, children, ...props }: any) {
                  const match = /language-(\w+)/.exec(className || '')
                  return !inline && match ? (
                    <div className="my-3 rounded-lg overflow-hidden border border-gray-200 dark:border-[#30363d] bg-gray-50 dark:bg-[#0d1117] shadow-sm">
                      <div className="flex items-center justify-between px-3 py-1.5 bg-gray-100 dark:bg-[#161b22] border-b border-gray-200 dark:border-[#30363d]">
                        <div className="flex items-center gap-2">
                          <FileText size={12} className="text-blue-500 dark:text-blue-400" />
                          <span className="text-xs text-gray-500 dark:text-slate-400 font-mono font-medium">{match[1]}</span>
                        </div>
                      </div>
                      <SyntaxHighlighter style={vscDarkPlus} language={match[1]} PreTag="div" customStyle={{ margin: 0, padding: '16px', background: 'transparent', fontSize: '13px', lineHeight: '1.6' }} wrapLines={true} {...props}>
                        {String(children).replace(/\n$/, '')}
                      </SyntaxHighlighter>
                    </div>
                  ) : (
                    <code className="bg-gray-100 dark:bg-[#1f6feb]/20 text-pink-600 dark:text-[#58a6ff] px-1.5 py-0.5 rounded text-xs font-mono border border-gray-200 dark:border-[#1f6feb]/30 font-medium" {...props}>{children}</code>
                  )
                },
                ul: ({ children }: any) => <ul className="list-disc pl-5 my-2 space-y-1 text-crick-text-primary">{children}</ul>,
                ol: ({ children }: any) => <ol className="list-decimal pl-5 my-2 space-y-1 text-crick-text-primary">{children}</ol>,
                a: ({ href, children }: any) => <a href={href} target="_blank" rel="noreferrer" className="text-blue-600 dark:text-emerald-400 hover:underline font-medium">{children}</a>,
                p: ({ children }: any) => <p className="mb-2 last:mb-0 text-crick-text-primary">{children}</p>,
                strong: ({ children }: any) => <strong className="font-bold text-gray-900 dark:text-white">{children}</strong>
              }}
            >
              {item.content}
            </ReactMarkdown>
          </div>
        </div>
      );
    default: return null;
  }
}
