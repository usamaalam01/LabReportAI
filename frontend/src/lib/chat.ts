import type {
  ChatMessage,
  ChatSuggestionsResponse,
  ChatStreamDoneEvent,
  ChatStreamTokenEvent,
} from "@/types";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

/**
 * Get starter question suggestions for a completed report.
 */
export async function getChatSuggestions(
  jobId: string
): Promise<ChatSuggestionsResponse> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/v1/chat/${jobId}/suggestions`);
  } catch {
    throw new Error("Network error. Please check your connection.");
  }

  if (!res.ok) {
    let errorMessage = "Failed to load chat suggestions.";
    try {
      const error = await res.json();
      errorMessage = error.message || errorMessage;
    } catch {
      if (res.status === 503) {
        errorMessage = "Chat feature is currently unavailable.";
      }
    }
    throw new Error(errorMessage);
  }

  return await res.json();
}

/**
 * Callbacks for streaming chat response.
 */
export interface ChatStreamCallbacks {
  onToken: (token: string) => void;
  onDone: (event: ChatStreamDoneEvent) => void;
  onError: (error: string) => void;
}

/**
 * Send a chat message and stream the response.
 * Returns an AbortController to allow cancellation.
 */
export function sendChatMessage(
  jobId: string,
  message: string,
  conversationHistory: ChatMessage[],
  callbacks: ChatStreamCallbacks
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_URL}/v1/chat/${jobId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message,
          conversation_history: conversationHistory,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        let errorMessage = "Failed to send message.";
        try {
          const error = await res.json();
          errorMessage = error.message || errorMessage;
        } catch {
          if (res.status === 429) {
            errorMessage = "Message limit reached for this report.";
          } else if (res.status === 503) {
            errorMessage = "Chat feature is currently unavailable.";
          }
        }
        callbacks.onError(errorMessage);
        return;
      }

      const reader = res.body?.getReader();
      if (!reader) {
        callbacks.onError("Failed to read response stream.");
        return;
      }

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || ""; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith("event: ")) {
            // Skip event type lines, we parse from data
            continue;
          }
          if (line.startsWith("data: ")) {
            try {
              const data = JSON.parse(line.slice(6));

              if (data.content !== undefined) {
                // Token event
                callbacks.onToken(data.content);
              } else if (data.suggestions !== undefined) {
                // Done event
                callbacks.onDone({
                  suggestions: data.suggestions,
                  messages_remaining: data.messages_remaining,
                });
              } else if (data.message !== undefined) {
                // Error event
                callbacks.onError(data.message);
              }
            } catch {
              // Ignore malformed JSON
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === "AbortError") {
        // Request was cancelled, ignore
        return;
      }
      callbacks.onError(
        err instanceof Error ? err.message : "Network error occurred."
      );
    }
  })();

  return controller;
}
