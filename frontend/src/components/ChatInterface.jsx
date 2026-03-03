import React, { useState } from "react";

const ChatInterface = ({ messages, onSend }) => {
  const [input, setInput] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    onSend(input);
    setInput("");
  };

  return (
    <section className="space-y-3">
      <h3 className="text-sm font-medium text-gray-700">
        Chat interface for next user query
      </h3>

      <div className="h-40 md:h-52 rounded-2xl border border-gray-200 bg-slate-50 p-3 overflow-y-auto space-y-2 text-sm">
        {messages.length === 0 && (
          <p className="text-gray-400">
            Your ongoing conversation will appear here.
          </p>
        )}
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`max-w-[80%] rounded-2xl px-3 py-2 ${
              msg.role === "user"
                ? "ml-auto bg-green-600 text-white"
                : "mr-auto bg-white border border-gray-200 text-gray-800"
            }`}
          >
            {msg.content}
          </div>
        ))}
      </div>

      <form
        onSubmit={handleSubmit}
        className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your next question..."
          className="flex-1 rounded-lg border border-gray-300 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
        />
        <button
          type="submit"
          className="whitespace-nowrap rounded-lg bg-green-600 px-4 py-2 text-sm font-medium text-white shadow-sm hover:bg-green-700"
        >
          Send
        </button>
      </form>
    </section>
  );
};

export default ChatInterface;

