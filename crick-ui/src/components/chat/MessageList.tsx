import React from 'react';
import type { ChatMessage, TimelineItem } from '@/types/api.types';
import MessageItem from './MessageItem';

interface MessageListProps {
  messages: ChatMessage[];
  streaming: boolean;
  lastMessageId: number | undefined;
  renderTimelineItem: (item: TimelineItem, index: number) => React.ReactNode;
  onUndo?: (runId: string) => void;
}

const MessageList = React.memo(function MessageList({
  messages,
  streaming,
  lastMessageId,
  renderTimelineItem,
  onUndo
}: MessageListProps) {
  return (
    <div className="space-y-10">
      {messages.map((msg) => (
        <MessageItem
          key={msg.id}
          msg={msg}
          isLast={msg.id === lastMessageId}
          streaming={streaming}
          renderTimelineItem={renderTimelineItem}
          onUndo={onUndo}
        />
      ))}
    </div>
  );
});

export default MessageList;