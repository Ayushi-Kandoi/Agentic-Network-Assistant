import React from "react";

const AssistantResponse = ({ response, isLoading, error }) => {
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-medium text-gray-700">Assistant Response</h2>
      <div className="min-h-[180px] md:min-h-[220px] rounded-3xl border border-gray-200 bg-slate-50 p-4 md:p-6">
        {isLoading && (
          <p className="text-gray-500 text-sm">Analyzing ticket...</p>
        )}
        {!isLoading && error && (
          <p className="text-red-600 text-sm">Error: {error}</p>
        )}
        {!isLoading && !error && !response && (
          <p className="text-gray-400 text-sm">
            Ticket analysis summary will appear here.
          </p>
        )}
        {!isLoading && !error && response && (
          <div className="space-y-3 text-sm md:text-base text-gray-800">
            <div>
              <h3 className="font-semibold mb-1">Summary</h3>
              <p className="whitespace-pre-wrap">{response.summary}</p>
            </div>
            {response.evidence && (
              <div>
                <h3 className="font-semibold mb-1">Evidence</h3>
                <p className="whitespace-pre-wrap">{response.evidence}</p>
              </div>
            )}
            {response.recommendation && (
              <div>
                <h3 className="font-semibold mb-1">Recommendation</h3>
                <p className="whitespace-pre-wrap">{response.recommendation}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </section>
  );
};

export default AssistantResponse;

