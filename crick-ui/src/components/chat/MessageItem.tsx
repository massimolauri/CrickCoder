import React from 'react';
import { Zap } from 'lucide-react';
import type { ChatMessage, TimelineItem } from '@/types/api.types';


interface MessageItemProps {
  msg: ChatMessage;
  isLast: boolean;
  streaming: boolean;
  renderTimelineItem: (item: TimelineItem, index: number) => React.ReactNode;
}

const MessageItem = React.memo(function MessageItem({
  msg,
  isLast,
  streaming,
  renderTimelineItem
}: MessageItemProps) {
  // Hide AI message if it has no content, no timeline, and is not currently streaming (e.g. stopped)
  const isEmpty = !msg.content && (!msg.timeline || msg.timeline.length === 0);
  if (msg.role !== 'user' && isEmpty && !streaming) {
    return null;
  }

  return (
    <div className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      {/* Avatar (solo per AI) */}
      {msg.role !== 'user' && (
        <div className="w-8 h-8 rounded-lg bg-white dark:bg-[#252526] border border-gray-200 dark:border-[#3e3e42] flex items-center justify-center shrink-0 mt-1 shadow-sm">
          <Zap
            size={14}
            className={streaming && isLast ? 'text-crick-accent animate-pulse' : 'text-gray-400 dark:text-slate-600'}
          />
        </div>
      )}

      {/* Contenuto Messaggio */}
      <div className={`flex flex-col max-w-[90%] sm:max-w-[85%] ${msg.role === 'user' ? 'items-end' : 'items-start min-w-[60%]'}`}>
        {msg.role === 'user' ? (
          <div className="px-5 py-3.5 rounded-3xl text-sm shadow-sm bg-gray-200 dark:bg-white/10 dark:text-white text-gray-900 border border-transparent dark:border-[#3e3e42] font-medium backdrop-blur-sm">
            {msg.content}
          </div>
        ) : (
          <div className="w-full text-crick-text-primary leading-relaxed">
            {msg.timeline && msg.timeline.map((item, idx) => renderTimelineItem(item, idx))}
            {streaming && isLast && (
              <span className="inline-flex items-center gap-1 ml-2 align-middle">
                <span className="w-1.5 h-1.5 bg-blue-600 dark:bg-blue-400 rounded-full animate-bounce-slow block" />
                <span className="w-1.5 h-1.5 bg-blue-600 dark:bg-blue-400 rounded-full animate-bounce-slow delay-100 block" />
                <span className="w-1.5 h-1.5 bg-blue-600 dark:bg-blue-400 rounded-full animate-bounce-slow delay-200 block" />
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
});

export default MessageItem;
