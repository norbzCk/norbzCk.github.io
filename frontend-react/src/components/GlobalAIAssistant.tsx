import { AIAssistant } from "./AIAssistant";

export function GlobalAIAssistant() {
  const { isOpen, isReplying, toggleAssistant, messages, sendMessage } = useAIAssistant();

  return (
    <AIAssistant
      isOpen={isOpen}
      isReplying={isReplying}
      onToggle={toggleAssistant}
      messages={messages}
      onSendMessage={sendMessage}
    />
  );
}
