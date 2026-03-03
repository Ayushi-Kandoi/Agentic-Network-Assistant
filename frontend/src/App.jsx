import React, { useState } from "react";
import TicketInput from "./components/TicketInput.jsx";
import AssistantResponse from "./components/AssistantResponse.jsx";
import FeedbackSection from "./components/FeedbackSection.jsx";
import ChatInterface from "./components/ChatInterface.jsx";

function App() {
  const [ticketNumber, setTicketNumber] = useState("");
  const [threadId, setThreadId] = useState("");
  const [assistantResponse, setAssistantResponse] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [chatMessages, setChatMessages] = useState([]);

  const handleFetchTicket = async () => {
    if (!ticketNumber.trim()) return;

    setIsLoading(true);
    setError("");
    try {
      const res = await fetch("http://127.0.0.1:8000/ticket/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ticket_number: ticketNumber.trim() })
      });

      if (!res.ok) {
        throw new Error(`Backend error: ${res.status}`);
      }

      const data = await res.json();
      setAssistantResponse(data);
      setThreadId(data.thread_id || "");
      setChatMessages([]);
    } catch (e) {
      console.error(e);
      setError(e.message || "Failed to fetch ticket resolution.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleFeedback = async (section, verdict, comment) => {
    try {
      await fetch("http://127.0.0.1:8000/feedback/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticket_number: ticketNumber,
          section,
          verdict,
          comment: comment || null
        })
      });
    } catch (e) {
      console.error("Error sending feedback", e);
    }
  };

  const handleSendChat = async (message) => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage) return;
    if (!ticketNumber.trim() || !threadId) {
      setError("Analyze a valid ticket first before sending chat messages.");
      return;
    }

    const userMsg = {
      id: Date.now(),
      role: "user",
      content: trimmedMessage
    };
    setChatMessages((prev) => [...prev, userMsg]);

    try {
      const res = await fetch("http://127.0.0.1:8000/chat/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ticket_number: ticketNumber.trim(),
          thread_id: threadId,
          message: trimmedMessage
        })
      });

      if (!res.ok) {
        throw new Error(`Chat backend error: ${res.status}`);
      }

      const data = await res.json();
      const assistantMsg = {
        id: Date.now() + 1,
        role: "assistant",
        content: data.response || JSON.stringify(data)
      };
      setChatMessages((prev) => [...prev, assistantMsg]);
    } catch (e) {
      console.error("Error sending chat message", e);
      setError(e.message || "Failed to send follow-up message.");
    }
  };

  return (
    <div className="min-h-screen bg-slate-100 flex items-center justify-center p-4">
      <div className="w-full max-w-5xl bg-white rounded-[32px] shadow-xl p-8 space-y-8">
        <header className="text-center">
          <h1 className="inline-block px-6 py-3 rounded-lg bg-green-100 text-green-900 font-semibold text-lg md:text-xl">
            Your Network Investigation Assistance
          </h1>
        </header>

        <TicketInput
          ticketNumber={ticketNumber}
          onTicketChange={setTicketNumber}
          onSubmit={handleFetchTicket}
          isLoading={isLoading}
        />

        <AssistantResponse
          response={assistantResponse}
          isLoading={isLoading}
          error={error}
        />

        <div className="space-y-4">
          <FeedbackSection
            title="Feedback on summary"
            sectionKey="summary"
            onFeedback={handleFeedback}
          />
          <FeedbackSection
            title="Feedback on recommendation"
            sectionKey="recommendation"
            onFeedback={handleFeedback}
          />
        </div>

        <ChatInterface messages={chatMessages} onSend={handleSendChat} />
      </div>
    </div>
  );
}

export default App;

