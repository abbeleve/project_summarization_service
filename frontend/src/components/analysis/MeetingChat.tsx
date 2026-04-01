import { useState, useRef, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ragApi } from '@/api/rag';
import { type ChatMessage } from '@/types/transcript';
import { LoadingSpinner } from '@/components/ui/LoadingSpinner';
import { ErrorMessage } from '@/components/ui/ErrorMessage';

interface MeetingChatProps {
  transcriptId: string;
  transcriptText?: string;
}

export const MeetingChat = ({ transcriptId }: MeetingChatProps) => {
  const [input, setInput] = useState('');
  const [localMessages] = useState<ChatMessage[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const queryClient = useQueryClient();

  const {  data: messages = [], isLoading, error } = useQuery<ChatMessage[]>({
    queryKey: ['chat', transcriptId],
    queryFn: () => ragApi.getChatHistory(transcriptId),
    enabled: !!transcriptId
  });

  const { mutate: sendMessage, isPending } = useMutation({
    mutationFn: (question: string) =>
      ragApi.askQuestion(transcriptId, question),
    onSuccess: (data) => {
      queryClient.setQueryData(['chat', transcriptId], (old: ChatMessage[] = []) => [
        ...old,
        { role: 'user', content: input },
        { role: 'assistant', content: data.answer }
      ]);
      setInput('');
    },
    onError: (err) => {
      console.error('Chat error:', err);
    }
  });

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, localMessages, isPending]);

  const handleSubmit = (e: React.SyntheticEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (input.trim() && !isPending) {
      sendMessage(input.trim());
    }
  };

  const allMessages = [...(messages || []), ...localMessages];

  return (
    <div className="flex flex-col h-[600px] bg-white dark:bg-gray-800 rounded-2xl shadow-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Header с градиентом */}
      <div className="bg-gradient-to-r from-violet-500 to-purple-600 p-5">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-white/20 flex items-center justify-center backdrop-blur-sm">
            <span className="text-xl">🤖</span>
          </div>
          <div>
            <h3 className="font-semibold text-white text-lg">AI Ассистент</h3>
            <p className="text-sm text-white/80">Задавайте вопросы о встрече</p>
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-gradient-to-b from-gray-50 to-white dark:from-gray-900 dark:to-gray-800">
        {isLoading && messages.length === 0 ? (
          <div className="flex justify-center py-12">
            <LoadingSpinner text="Загрузка истории..." size={'sm'} />
          </div>
        ) : error ? (
          <ErrorMessage message="Не удалось загрузить чат" />
        ) : allMessages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center px-4">
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-violet-100 to-purple-100 dark:from-violet-900/30 dark:to-purple-900/30 flex items-center justify-center mb-4">
              <span className="text-3xl">💬</span>
            </div>
            <p className="text-gray-600 dark:text-gray-400 font-medium mb-1">Начните диалог</p>
            <p className="text-sm text-gray-400 dark:text-gray-500">Задайте вопрос о содержании встречи</p>
          </div>
        ) : (
          allMessages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] px-4 py-3 rounded-2xl shadow-sm ${
                  msg.role === 'user'
                    ? 'bg-gradient-to-r from-violet-600 to-purple-600 text-white rounded-br-md'
                    : 'bg-white dark:bg-gray-700 text-gray-800 dark:text-gray-200 rounded-bl-md border border-gray-200 dark:border-gray-600'
                }`}
              >
                <p className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</p>
              </div>
            </div>
          ))
        )}

        {isPending && (
          <div className="flex justify-start">
            <div className="bg-white dark:bg-gray-700 border border-gray-200 dark:border-gray-600 px-4 py-3 rounded-2xl rounded-bl-md shadow-sm">
              <div className="flex gap-1.5">
                <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce" />
                <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce animation-delay-100" />
                <span className="w-2 h-2 bg-violet-400 rounded-full animate-bounce animation-delay-200" />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input form */}
      <form onSubmit={handleSubmit} className="p-4 bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Спросите о встрече..."
            className="flex-1 border border-gray-300 dark:border-gray-600 rounded-xl px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent transition-all placeholder:text-gray-400 dark:placeholder:text-gray-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            disabled={isPending}
          />
          <button
            type="submit"
            disabled={!input.trim() || isPending}
            className="px-5 py-2.5 bg-gradient-to-r from-violet-600 to-purple-600 text-white rounded-xl hover:from-violet-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-all shadow-md hover:shadow-lg"
          >
            <span className="text-lg">➤</span>
          </button>
        </div>
      </form>
    </div>
  );
};