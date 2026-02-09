"use client";

import { useState, useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from "react";
import type { ChatMessage, ChatStreamDoneEvent } from "@/types";
import { getChatSuggestions, sendChatMessage } from "@/lib/chat";

interface ChatWidgetProps {
  jobId: string;
}

export interface ChatWidgetRef {
  open: () => void;
}

const ChatWidget = forwardRef<ChatWidgetRef, ChatWidgetProps>(function ChatWidget({ jobId }, ref) {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [currentStreamedResponse, setCurrentStreamedResponse] = useState("");
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [messagesRemaining, setMessagesRemaining] = useState(20);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortControllerRef = useRef<AbortController | null>(null);
  const streamedResponseRef = useRef("");

  // Expose open method to parent components
  useImperativeHandle(ref, () => ({
    open: () => setIsOpen(true),
  }));

  // Scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentStreamedResponse]);

  // Focus input when panel opens
  useEffect(() => {
    if (isOpen && inputRef.current) {
      inputRef.current.focus();
    }
  }, [isOpen]);

  // Load initial suggestions when panel opens
  useEffect(() => {
    if (isOpen && suggestions.length === 0 && messages.length === 0) {
      loadInitialSuggestions();
    }
  }, [isOpen]);

  const loadInitialSuggestions = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await getChatSuggestions(jobId);
      setSuggestions(data.suggestions);
      setMessagesRemaining(data.messages_remaining);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load chat.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = useCallback(
    (message: string) => {
      if (!message.trim() || isStreaming || messagesRemaining <= 0) return;

      setError(null);
      setIsStreaming(true);
      setCurrentStreamedResponse("");
      streamedResponseRef.current = "";

      // Add user message immediately
      const userMessage: ChatMessage = { role: "user", content: message.trim() };
      setMessages((prev) => [...prev, userMessage]);
      setInputValue("");

      // Clear suggestions while streaming
      setSuggestions([]);

      const controller = sendChatMessage(
        jobId,
        message.trim(),
        messages, // Pass current history (before adding new message)
        {
          onToken: (token) => {
            streamedResponseRef.current += token;
            setCurrentStreamedResponse(streamedResponseRef.current);
          },
          onDone: (event: ChatStreamDoneEvent) => {
            // Finalize assistant message using ref (has latest value)
            const finalResponse = streamedResponseRef.current;
            if (finalResponse) {
              setMessages((prev) => [
                ...prev,
                { role: "assistant", content: finalResponse },
              ]);
            }
            setCurrentStreamedResponse("");
            streamedResponseRef.current = "";
            setIsStreaming(false);
            setSuggestions(event.suggestions);
            setMessagesRemaining(event.messages_remaining);
          },
          onError: (errorMsg) => {
            setError(errorMsg);
            setIsStreaming(false);
            setCurrentStreamedResponse("");
            streamedResponseRef.current = "";
          },
        }
      );

      abortControllerRef.current = controller;
    },
    [jobId, messages, isStreaming, messagesRemaining]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage(inputValue);
    }
  };

  const handleSuggestionClick = (suggestion: string) => {
    handleSendMessage(suggestion);
  };

  const handleClose = () => {
    // Cancel any ongoing stream
    abortControllerRef.current?.abort();
    setIsOpen(false);
  };

  return (
    <>
      {/* Floating Chat Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-blue-600 text-white shadow-lg transition-all hover:bg-blue-700 hover:scale-105 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2"
          aria-label="Open chat to ask questions about your results"
        >
          <svg
            className="h-6 w-6"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden="true"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
        </button>
      )}

      {/* Chat Panel */}
      {isOpen && (
        <div
          className="fixed inset-2 z-50 flex flex-col bg-white shadow-2xl rounded-xl border sm:inset-auto sm:bottom-6 sm:right-6 sm:h-[650px] sm:w-[550px]"
          role="dialog"
          aria-label="Chat about your lab results"
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b bg-blue-600 px-4 py-3 text-white rounded-t-xl">
            <div className="flex items-center space-x-2">
              <svg
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
                />
              </svg>
              <span className="font-semibold">Ask About Your Results</span>
            </div>
            <button
              onClick={handleClose}
              className="rounded p-1 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-white"
              aria-label="Close chat"
            >
              <svg
                className="h-5 w-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {/* Messages Area */}
          <div className="flex-1 overflow-y-auto p-4 space-y-4">
            {/* Loading state */}
            {isLoading && (
              <div className="flex justify-center py-8">
                <div className="h-6 w-6 animate-spin rounded-full border-2 border-blue-200 border-t-blue-600" />
              </div>
            )}

            {/* Error state */}
            {error && (
              <div className="rounded-lg bg-red-50 p-3 text-sm text-red-700">
                {error}
              </div>
            )}

            {/* Welcome message */}
            {!isLoading && messages.length === 0 && !error && (
              <div className="text-center text-sm text-gray-500 py-4">
                <p className="mb-2">
                  I can help you understand your lab results.
                </p>
                <p>Ask me anything or try one of the suggestions below!</p>
              </div>
            )}

            {/* Messages */}
            {messages.map((msg, index) => (
              <div
                key={index}
                className={`flex ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[85%] rounded-lg px-4 py-2 ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white"
                      : "bg-gray-100 text-gray-800"
                  }`}
                >
                  <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                </div>
              </div>
            ))}

            {/* Streaming response */}
            {isStreaming && currentStreamedResponse && (
              <div className="flex justify-start">
                <div className="max-w-[85%] rounded-lg bg-gray-100 px-4 py-2 text-gray-800">
                  <p className="text-sm whitespace-pre-wrap">
                    {currentStreamedResponse}
                    <span className="inline-block w-1 h-4 ml-1 bg-gray-400 animate-pulse" />
                  </p>
                </div>
              </div>
            )}

            {/* Typing indicator */}
            {isStreaming && !currentStreamedResponse && (
              <div className="flex justify-start">
                <div className="rounded-lg bg-gray-100 px-4 py-3">
                  <div className="flex space-x-1">
                    <div className="h-2 w-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "0ms" }} />
                    <div className="h-2 w-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "150ms" }} />
                    <div className="h-2 w-2 rounded-full bg-gray-400 animate-bounce" style={{ animationDelay: "300ms" }} />
                  </div>
                </div>
              </div>
            )}

            {/* Suggestions */}
            {!isStreaming && suggestions.length > 0 && messagesRemaining > 0 && (
              <div className="flex flex-wrap gap-2 pt-2">
                {suggestions.map((suggestion, index) => (
                  <button
                    key={index}
                    onClick={() => handleSuggestionClick(suggestion)}
                    className="rounded-full border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs text-blue-700 transition-colors hover:bg-blue-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          {/* Input Area */}
          <div className="border-t bg-gray-50 p-4 rounded-b-xl">
            {messagesRemaining > 0 ? (
              <>
                <div className="flex space-x-2">
                  <textarea
                    ref={inputRef}
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder="Ask about your results..."
                    disabled={isStreaming}
                    rows={1}
                    className="flex-1 resize-none rounded-lg border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
                    aria-label="Type your question"
                  />
                  <button
                    onClick={() => handleSendMessage(inputValue)}
                    disabled={!inputValue.trim() || isStreaming}
                    className="rounded-lg bg-blue-600 px-4 py-2 text-white transition-colors hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:bg-gray-300 disabled:cursor-not-allowed"
                    aria-label="Send message"
                  >
                    <svg
                      className="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                      viewBox="0 0 24 24"
                      aria-hidden="true"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                      />
                    </svg>
                  </button>
                </div>
                <div
                  className={`mt-2 text-center text-xs ${
                    messagesRemaining <= 5 ? "text-orange-600" : "text-gray-400"
                  }`}
                >
                  {messagesRemaining} message{messagesRemaining !== 1 ? "s" : ""} remaining
                </div>
              </>
            ) : (
              <div className="text-center text-sm text-gray-500">
                <p className="mb-2">You&apos;ve used all 20 messages for this report.</p>
                <p className="text-xs text-gray-400">
                  Download the PDF for a complete summary.
                </p>
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
});

export default ChatWidget;
