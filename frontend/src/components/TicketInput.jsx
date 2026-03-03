import React from "react";

const TicketInput = ({ ticketNumber, onTicketChange, onSubmit, isLoading }) => {
  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <section className="space-y-3">
      <label className="block text-sm font-medium text-gray-700">
        Enter the ticket number
      </label>
      <form
        onSubmit={handleSubmit}
        className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center"
      >
        <input
          type="text"
          value={ticketNumber}
          onChange={(e) => onTicketChange(e.target.value)}
          placeholder="TKT-2025001"
          className="flex-1 rounded-lg border border-gray-300 px-4 py-2 focus:outline-none focus:ring-2 focus:ring-green-400"
        />
        <button
          type="submit"
          disabled={isLoading}
          className="whitespace-nowrap rounded-lg bg-green-600 px-5 py-2 text-white font-medium shadow-sm hover:bg-green-700 disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {isLoading ? "Fetching..." : "Get Resolution"}
        </button>
      </form>
    </section>
  );
};

export default TicketInput;

