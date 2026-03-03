import React, { useState } from "react";

const FeedbackSection = ({ title, sectionKey, onFeedback }) => {
  const [showCommentBox, setShowCommentBox] = useState(false);
  const [comment, setComment] = useState("");

  const handleClick = (verdict) => {
    onFeedback(sectionKey, verdict, null);
  };

  const handleCommentSubmit = () => {
    if (!comment.trim()) return;
    onFeedback(sectionKey, "comment", comment.trim());
    setComment("");
    setShowCommentBox(false);
  };

  return (
    <section className="space-y-2">
      <h3 className="text-sm font-medium text-gray-700">{title}</h3>
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => handleClick("correct")}
          className="rounded-full border border-green-500 px-4 py-1.5 text-sm font-medium text-green-700 hover:bg-green-50"
        >
          Correct
        </button>
        <button
          type="button"
          onClick={() => handleClick("incorrect")}
          className="rounded-full border border-red-500 px-4 py-1.5 text-sm font-medium text-red-700 hover:bg-red-50"
        >
          Incorrect
        </button>
        <button
          type="button"
          onClick={() => setShowCommentBox((v) => !v)}
          className="rounded-full border border-gray-400 px-4 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
        >
          Add your comment
        </button>
      </div>

      {showCommentBox && (
        <div className="mt-2 flex flex-col gap-2 max-w-xl">
          <textarea
            rows={2}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Share more details about your feedback..."
            className="rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-green-400"
          />
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleCommentSubmit}
              className="rounded-lg bg-green-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-green-700"
            >
              Submit comment
            </button>
            <button
              type="button"
              onClick={() => {
                setShowCommentBox(false);
                setComment("");
              }}
              className="rounded-lg border border-gray-300 px-3 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </section>
  );
};

export default FeedbackSection;

