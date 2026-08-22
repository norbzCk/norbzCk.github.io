import { FormEvent, useState } from "react";

type AssistantMessage = {
  id: string;
  role: "assistant" | "user";
  text: string;
};

interface AIAssistantProps {
  isOpen: boolean;
  isReplying?: boolean;
  onToggle: () => void;
  messages: AssistantMessage[];
  onSendMessage: (message: string) => void | Promise<void>;
}

export function AIAssistant({ isOpen, isReplying = false, onToggle, messages, onSendMessage }: AIAssistantProps) {
  const [input, setInput] = useState("");

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (input.trim()) {
      void onSendMessage(input.trim());
      setInput("");
    }
  };

  return (
    <>
      {isOpen && (
        <div
          className="fixed bottom-24 right-4 left-4 sm:left-auto z-50 flex justify-end sm:right-6"
          role="dialog"
          aria-label="AI Assistant"
        >
          <div className="bg-white dark:bg-slate-800 w-full sm:w-[420px] rounded-2xl shadow-2xl border border-slate-200 dark:border-slate-700 flex flex-col max-h-[70vh] sm:max-h-[600px] overflow-hidden">
            <div className="p-4 border-b border-slate-200 dark:border-slate-700 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-brand/10 flex items-center justify-center text-xl">🤖</div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-slate-900 dark:text-white">AI Command Desk</h3>
                    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${isReplying ? "bg-yellow-100 text-yellow-800" : "bg-green-100 text-green-800"}`}>
                      {isReplying ? "Thinking" : "Live"}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 dark:text-slate-400">Products, sellers, orders, and the next best move.</p>
                </div>
              </div>
              <button className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors text-slate-400 hover:text-slate-600 dark:hover:text-slate-300" onClick={onToggle} aria-label="Close assistant">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M6.28 5.22a.75.75 0 00-1.06 1.06L8.94 10l-3.72 3.72a.75.75 0 101.06 1.06L10 11.06l3.72 3.72a.75.75 0 101.06-1.06L11.06 10l3.72-3.72a.75.75 0 00-1.06-1.06L10 8.94 6.28 5.22z" />
                </svg>
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4 space-y-3" aria-live="polite">
              {messages.map((message) => (
                <div key={message.id} className={`flex gap-3 ${message.role === "user" ? "flex-row-reverse" : ""}`}>
                  <div className="w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-700 flex items-center justify-center text-xs flex-shrink-0">
                    {message.role === "assistant" ? "🤖" : "You"}
                  </div>
                  <div className={`flex-1 rounded-2xl px-4 py-3 ${
                    message.role === "assistant"
                      ? "bg-slate-100 dark:bg-slate-700 text-slate-900 dark:text-white"
                      : "bg-brand text-white"
                  }`}>
                    {message.text}
                  </div>
                </div>
              ))}
              {isReplying ? (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-lg bg-slate-100 dark:bg-slate-700 flex items-center justify-center text-xs">🤖</div>
                  <div className="flex-1 rounded-2xl px-4 py-3 bg-slate-100 dark:bg-slate-700 text-slate-900 dark:text-white">
                    Thinking through the best reply for you...
                  </div>
                </div>
              ) : null}
            </div>

            <form className="p-4 border-t border-slate-200 dark:border-slate-700" onSubmit={handleSubmit}>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask for help, a reply draft, or the next step..."
                  disabled={isReplying}
                  className="flex-1 px-4 py-3 bg-slate-50 dark:bg-slate-700 border-2 border-transparent focus:border-brand/20 rounded-xl outline-none transition-all text-sm text-slate-900 dark:text-white placeholder:text-slate-400"
                />
                <button type="submit" disabled={isReplying} className="px-6 py-3 bg-brand text-white rounded-xl hover:bg-brand/90 transition-colors font-medium text-sm disabled:opacity-50">
                  {isReplying ? "..." : "Send"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      <button
        className="fixed bottom-6 right-6 w-14 h-14 bg-brand text-white rounded-full shadow-2xl hover:bg-brand/90 transition-all hover:scale-110 flex items-center justify-center text-2xl z-40"
        onClick={onToggle}
        aria-label="Toggle AI Assistant"
      >
        {isOpen ? "×" : "🤖"}
      </button>
    </>
  );
}
