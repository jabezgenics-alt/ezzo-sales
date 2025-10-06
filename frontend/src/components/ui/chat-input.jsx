import { cn } from "@/lib/utils";
import { ArrowUp } from "lucide-react";
import { createContext, useContext } from "react";

const ChatInputContext = createContext({});

function ChatInput({
  children,
  className,
  variant = "default",
  value,
  onChange,
  onSubmit,
  loading,
  onStop,
  rows = 1,
}) {
  const contextValue = {
    value,
    onChange,
    onSubmit,
    loading,
    onStop,
    variant,
    rows,
  };

  const handleKeyDown = (e) => {
    if (!onSubmit) return;
    if (e.key === "Enter" && !e.shiftKey) {
      if (typeof value !== "string" || value.trim().length === 0) return;
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <ChatInputContext.Provider value={contextValue}>
      <div className={cn(
        "pl-5 pr-3 border border-gray-300 rounded-2xl bg-white shadow-lg flex items-center justify-between focus-within:border-black transition-all duration-200",
        className
      )}>
        {children}
      </div>
    </ChatInputContext.Provider>
  );
}

ChatInput.displayName = "ChatInput";

function ChatInputTextArea({
  onSubmit: onSubmitProp,
  value: valueProp,
  onChange: onChangeProp,
  className,
  variant: variantProp,
  ...props
}) {
  const context = useContext(ChatInputContext);
  const value = valueProp ?? context.value ?? "";
  const onChange = onChangeProp ?? context.onChange;
  const onSubmit = onSubmitProp ?? context.onSubmit;

  const handleKeyDown = (e) => {
    if (!onSubmit) return;
    if (e.key === "Enter" && !e.shiftKey) {
      if (typeof value !== "string" || value.trim().length === 0) return;
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <>
      <input
        type="text"
        placeholder="Ask a question..."
        aria-label="Ask a question..."
        className={cn(
          "py-3 flex-1 bg-transparent text-black placeholder-gray-400 outline-none text-base sm:text-sm w-full min-h-[48px]",
          className
        )}
        value={value}
        onChange={onChange}
        onKeyDown={handleKeyDown}
        {...props}
      />
      <span className="text-xs font-semibold mx-2 select-none pointer-events-none">⌘I</span>
    </>
  );
}

ChatInputTextArea.displayName = "ChatInputTextArea";

function ChatInputSubmit({
  onSubmit: onSubmitProp,
  loading: loadingProp,
  onStop: onStopProp,
  className,
  ...props
}) {
  const context = useContext(ChatInputContext);
  const loading = loadingProp ?? context.loading;
  const onStop = onStopProp ?? context.onStop;
  const onSubmit = onSubmitProp ?? context.onSubmit;

  if (loading && onStop) {
    return (
      <button
        onClick={onStop}
        className={cn(
          "chat-assistant-send-button flex justify-center items-center p-1 size-7 rounded-full bg-black",
          className
        )}
        aria-label="Stop"
        {...props}
      >
        <svg
          xmlns="http://www.w3.org/2000/svg"
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="currentColor"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="size-5 text-white"
        >
          <rect x="6" y="6" width="12" height="12" />
        </svg>
      </button>
    );
  }

  const isDisabled =
    typeof context.value !== "string" || context.value.trim().length === 0;

  return (
    <button
      className={cn(
        "chat-assistant-send-button flex justify-center items-center p-1 size-7 rounded-full bg-black disabled:bg-gray-200",
        className
      )}
      aria-label="Send message"
      disabled={isDisabled}
      onClick={(event) => {
        event.preventDefault();
        if (!isDisabled) {
          onSubmit?.();
        }
      }}
      {...props}
    >
      <svg
        xmlns="http://www.w3.org/2000/svg"
        width="24"
        height="24"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="lucide lucide-arrow-up size-5 text-white"
      >
        <path d="m5 12 7-7 7 7"></path>
        <path d="M12 19V5"></path>
      </svg>
    </button>
  );
}

ChatInputSubmit.displayName = "ChatInputSubmit";

export { ChatInput, ChatInputTextArea, ChatInputSubmit };

