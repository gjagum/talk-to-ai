import React, { useEffect, useRef } from 'react';
import { User, Bot } from 'lucide-react';

function ConversationLog({ conversation }) {
  const logEndRef = useRef(null);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [conversation]);

  return (
    <div className="flex flex-col h-full max-h-[400px]">
      <h3 className="text-lg font-semibold text-slate-200 mb-4 px-2 flex items-center gap-2">
        <Bot className="w-5 h-5 text-purple-400" />
        Conversation History
      </h3>
      
      <div className="flex-1 overflow-y-auto pr-2 space-y-4 scrollbar-thin scrollbar-thumb-slate-700 scrollbar-track-transparent">
        {conversation.length === 0 ? (
          <div className="h-full min-h-[200px] flex flex-col items-center justify-center text-slate-500 space-y-3">
            <div className="p-4 rounded-full bg-slate-800/50 border border-slate-700/50">
              <Bot className="w-8 h-8 text-slate-600" />
            </div>
            <p>Your conversation will appear here</p>
          </div>
        ) : (
          conversation.map((msg, idx) => (
            <div 
              key={idx} 
              className={`flex w-full ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div 
                className={`
                  max-w-[85%] rounded-2xl p-4 flex gap-3 shadow-md
                  ${msg.role === 'user' 
                    ? 'bg-blue-600/20 border border-blue-500/20 text-blue-50 rounded-tr-sm' 
                    : 'bg-slate-800/80 border border-slate-700 text-slate-100 rounded-tl-sm'}
                `}
              >
                <div className="flex-shrink-0 mt-1">
                  {msg.role === 'user' ? (
                    <div className="w-6 h-6 rounded-full bg-blue-500/20 flex items-center justify-center text-blue-400">
                      <User className="w-4 h-4" />
                    </div>
                  ) : (
                    <div className="w-6 h-6 rounded-full bg-purple-500/20 flex items-center justify-center text-purple-400">
                      <Bot className="w-4 h-4" />
                    </div>
                  )}
                </div>
                <div className="flex flex-col">
                  <span className="text-xs font-semibold mb-1 opacity-60">
                    {msg.role === 'user' ? 'You' : 'Assistant'}
                  </span>
                  <p className="leading-relaxed text-sm">{msg.text}</p>
                </div>
              </div>
            </div>
          ))
        )}
        <div ref={logEndRef} />
      </div>
    </div>
  );
}

export default ConversationLog;
