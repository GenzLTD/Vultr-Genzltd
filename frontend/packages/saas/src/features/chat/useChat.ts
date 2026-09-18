/**
 * useChat hook - Streaming chat for SaaS RAG knowledge base.
 * Owner: szbenyx
 *
 * SSE-based streaming via fetch API.
 * No Supabase. No tdesign.
 * Auto-retry on connection drop (up to 3 retries).
 * 
 * DEPRECATED: Use useChatNonStreaming instead for contract consistency.
 */
import { useState, useCallback, useRef } from "react";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

let _uid = 0;
function uid(): string {
  return `msg_${Date.now()}_${++_uid}`;
}

export interface DocSource {
  filename: string;
  chunk_id?: string;
  score?: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
  sources?: DocSource[];
}

interface UseChatOptions {
  mode?: "chat" | "deepseek" | "fast";
  top_k?: number;
  /** Pre-check / retry when backend returns consent_required */
  ensureAskConsent?: () => Promise<boolean>;
}

const RETRY_DELAYS = [1000, 2000, 5000];
const MAX_RETRIES = 3;

export function useChat(options: UseChatOptions = {}) {
  console.warn('⚠️ useChat is deprecated. Use useChatNonStreaming for contract consistency.');
  
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const retryCountRef = useRef(0);

  const getToken = useCallback(() => {
    try {
      const stored = localStorage.getItem("saas-auth");
      if (stored) {
        const parsed = JSON.parse(stored);
        return parsed?.state?.token || null;
      }
    } catch { /* ignore */ }
    return null;
  }, []);

  /** SSE streaming request */
  const sendStream = useCallback(
    async (query: string) => {
      setError(null);
      setIsStreaming(true);
      retryCountRef.current = 0;

      const userMsg: ChatMessage = {
        id: uid(),
        role: "user",
        content: query,
        created_at: new Date().toISOString(),
      };
      const assistantId = uid();

      setMessages((prev) => [
        ...prev,
        userMsg,
        {
          id: assistantId,
          role: "assistant",
          content: "",
          created_at: new Date().toISOString(),
        },
      ]);

      const attemptStream = async (): Promise<void> => {
        const token = getToken();
        try {
          const response = await fetch(`${API_BASE}/v1/ask`, {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              ...(token ? { Authorization: `Bearer ${token}` } : {}),
            },
            body: JSON.stringify({
              query,
              history: messages.slice(-10).map((m) => ({ role: m.role, content: m.content })),
              mode: options.mode ?? "chat",
              top_k: options.top_k ?? 5,
            }),
          });

          if (!response.ok) {
            const err = await response.json().catch(() => ({})) as {
              error?: string;
              message?: string;
              detail?: string;
            };
            if (
              response.status === 403
              && err.error === "consent_required"
              && options.ensureAskConsent
            ) {
              const allowed = await options.ensureAskConsent();
              if (allowed) return attemptStream();
              throw new Error(err.message || "需要授权后才能使用 AI 问答");
            }
            throw new Error(err.detail || err.message || `HTTP ${response.status}`);
          }

          const reader = response.body?.getReader();
          if (!reader) {
            throw new Error("Response body is not readable");
          }

          const decoder = new TextDecoder();
          let buffer = "";

          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
              if (line.startsWith("data: ")) {
                const data = line.slice(6).trim();
                if (data === "[DONE]") continue;

                try {
                  const parsed = JSON.parse(data);
                  if (parsed.token) {
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantId
                          ? { ...m, content: m.content + parsed.token }
                          : m
                      )
                    );
                  }
                  if (parsed.sources && parsed.sources.length > 0) {
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantId ? { ...m, sources: parsed.sources } : m
                      )
                    );
                  }
                } catch {
                  // Non-JSON chunk, treat as plain text token
                  if (data) {
                    setMessages((prev) =>
                      prev.map((m) =>
                        m.id === assistantId
                          ? { ...m, content: m.content + data }
                          : m
                      )
                    );
                  }
                }
              }
            }
          }

          setIsStreaming(false);
        } catch (err) {
          const errMsg = (err as Error).message;

          if (retryCountRef.current < MAX_RETRIES) {
            const delay = RETRY_DELAYS[retryCountRef.current] ?? 5000;
            retryCountRef.current++;
            setError(`连接中断，${delay / 1000}s 后重试 (${retryCountRef.current}/${MAX_RETRIES})...`);
            await new Promise((r) => setTimeout(r, delay));
            setError(null);
            return attemptStream();
          }

          setError(errMsg || "请求失败");
          setIsStreaming(false);
        }
      };

      await attemptStream();
    },
    [messages, options.mode, options.top_k, options.ensureAskConsent, getToken]
  );

  const clear = useCallback(() => {
    setMessages([]);
    setError(null);
    setIsStreaming(false);
  }, []);

  return { messages, isStreaming, error, sendStream, clear };
}
