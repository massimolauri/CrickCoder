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
          <div className="text-sm text-slate-300 leading-7 font-sans mb-2 pl-1 markdown-body">
            <ReactMarkdown
              remarkPlugins={[]}
              components={{
                code({node, inline, className, children, ...props}: any) {
                  const match = /language-(\w+)/.exec(className || '')
                  return !inline && match ? (
                    <div className="my-3 rounded-md overflow-hidden border border-[#30363d] bg-[#0d1117] shadow-md">
                        <div className="flex items-center justify-between px-3 py-1.5 bg-[#161b22] border-b border-[#30363d]">
                            <div className="flex items-center gap-2"><FileText size={12} className="text-blue-400"/><span className="text-xs text-slate-400 font-mono">{match[1]}</span></div>
                        </div>
                        <SyntaxHighlighter style={vscDarkPlus} language={match[1]} PreTag="div" customStyle={{ margin: 0, padding: '16px', background: 'transparent', fontSize: '12px', lineHeight: '1.5' }} wrapLines={true} {...props}>
                          {String(children).replace(/\n$/, '')}
                        </SyntaxHighlighter>
                    </div>
                  ) : (
                    <code className="bg-[#1f6feb]/20 text-[#58a6ff] px-1.5 py-0.5 rounded text-xs font-mono border border-[#1f6feb]/30" {...props}>{children}</code>
                  )
                },
                ul: ({children}: any) => <ul className="list-disc pl-5 my-2 space-y-1 text-slate-400">{children}</ul>,
                ol: ({children}: any) => <ol className="list-decimal pl-5 my-2 space-y-1 text-slate-400">{children}</ol>,
                a: ({href, children}: any) => <a href={href} target="_blank" rel="noreferrer" className="text-emerald-400 hover:underline">{children}</a>,
                p: ({children}: any) => <p className="mb-2 last:mb-0">{children}</p>,
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