'use client';

import { useState, useRef, useEffect } from 'react';
import Sidebar from '@/components/Sidebar';
import Header from '@/components/Header';
import DataRain from '@/components/DataRain';
import { useWebSocket } from '@/lib/useWebSocket';
import { sendChat } from '@/lib/api';
import styles from './chat.module.css';

interface ChatMessage {
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
}

const BOOT_MESSAGES: ChatMessage[] = [
  { role: 'system', content: '═══════════════════════════════════════════', timestamp: '' },
  { role: 'system', content: '  BIGBROTHER v1.0 — AI Supervision Terminal', timestamp: '' },
  { role: 'system', content: '  Autonomous Trading Intelligence Online', timestamp: '' },
  { role: 'system', content: '═══════════════════════════════════════════', timestamp: '' },
  { role: 'system', content: '', timestamp: '' },
  { role: 'assistant', content: 'BigBrother online. I monitor all trading operations, risk levels, and agent behavior. Ask me about portfolio status, market conditions, or trading decisions.', timestamp: new Date().toISOString() },
];

export default function ChatPage() {
  const { isConnected } = useWebSocket();
  const [messages, setMessages] = useState<ChatMessage[]>(BOOT_MESSAGES);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSend = async () => {
    const msg = input.trim();
    if (!msg || loading) return;

    const userMsg: ChatMessage = {
      role: 'user',
      content: msg,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await sendChat(msg);
      const reply: ChatMessage = {
        role: 'assistant',
        content: res.data?.reply || 'Error: No response from BigBrother.',
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, reply]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'system', content: '[ERROR] Failed to reach BigBrother. Is the bot running?', timestamp: new Date().toISOString() },
      ]);
    }
    setLoading(false);
    inputRef.current?.focus();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="app-container">
      <DataRain />
      <Sidebar />
      <Header wsConnected={isConnected} />
      <main className="main-content" style={{ padding: 0, display: 'flex', flexDirection: 'column' }}>
        {/* Chat Messages */}
        <div className={styles.chatArea}>
          {messages.map((msg, i) => (
            <div key={i} className={`${styles.message} ${styles[msg.role]}`}>
              {msg.role === 'system' ? (
                <div className={styles.systemLine}>{msg.content}</div>
              ) : (
                <>
                  <div className={styles.messageHeader}>
                    <span className={styles.prompt}>
                      {msg.role === 'user' ? 'operator@moonshot ~$' : 'bigbrother >>'}
                    </span>
                    {msg.timestamp && (
                      <span className={styles.timestamp}>
                        {new Date(msg.timestamp).toLocaleTimeString('en-US', { hour12: false })}
                      </span>
                    )}
                  </div>
                  <div className={styles.messageBody}>{msg.content}</div>
                </>
              )}
            </div>
          ))}
          {loading && (
            <div className={`${styles.message} ${styles.assistant}`}>
              <div className={styles.messageHeader}>
                <span className={styles.prompt}>bigbrother &gt;&gt;</span>
              </div>
              <div className={styles.thinking}>
                <span className={styles.thinkingDots}>analyzing</span>
                <span className="cursor-blink" />
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Input */}
        <div className={styles.inputBar}>
          <span className={styles.inputPrompt}>$</span>
          <input
            ref={inputRef}
            type="text"
            className={styles.input}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask BigBrother anything..."
            disabled={loading}
            autoFocus
          />
          <button className={`btn btn-primary ${styles.sendBtn}`} onClick={handleSend} disabled={loading}>
            SEND
          </button>
        </div>
      </main>
    </div>
  );
}
