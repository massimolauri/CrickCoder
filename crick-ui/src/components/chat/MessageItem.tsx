import React from 'react';
import { Zap } from 'lucide-react';
import type { ChatMessage, TimelineItem } from '@/types/api.types';
import { THEME } from '@/constants/theme';

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
  return (
    <div className={`flex gap-4 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
      {/* Avatar (solo per AI) */}
      {msg.role !== 'user' && (
        <div className="w-8 h-8 rounded-lg bg-[#161b22] border border-[#30363d] flex items-center justify-center shrink-0 mt-1 shadow-sm">
          <Zap
            size={14}
            className={streaming && isLast ? 'text-emerald-400 animate-pulse' : 'text-slate-600'}
          />
        </div>
      )}

      {/* Contenuto Messaggio */}
      <div className={`flex flex-col max-w-[90%] sm:max-w-[85%] ${msg.role === 'user' ? 'items-end' : 'items-start min-w-[60%]'}`}>
        {msg.role === 'user' ? (
          <div className={`px-4 py-3 rounded-2xl text-sm ${THEME.userBubble} shadow-sm`}>
            {msg.content}
          </div>
        ) : (
          <div className="w-full">
            {msg.timeline && msg.timeline.map((item, idx) => renderTimelineItem(item, idx))}
            {streaming && isLast && (
              <span className="inline-block w-1.5 h-4 bg-emerald-500/50 ml-1 animate-pulse align-middle rounded-full" />
            )}
          </div>
        )}
      </div>
    </div>
  );
});

export default MessageItem;