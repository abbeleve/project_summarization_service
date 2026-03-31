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
    <div className="flex flex-col h-[600px] border rounded-xl bg-white">
      {/* Header */}
      <div className="p-4 border-b bg-gray-50">
        <h3 className="font-semibold text-gray-900">💬 Чат</h3>
        <p className="text-sm text-gray-500">Задавайте вопросы о содержании встречи</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {isLoading && messages.length === 0 ? (
          <div className="flex justify-center py-8">
            <LoadingSpinner text="Загрузка истории..." size={'sm'} />
          </div>
        ) : error ? (
          <ErrorMessage message="Не удалось загрузить чат" />
        ) : allMessages.length === 0 ? (
          <div className="text-center text-gray-400 py-8">
            Начните диалог, задав вопрос о встрече
          </div>
        ) : (
          allMessages.map((msg, idx) => (
            <div
              key={idx}
              className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[85%] p-3 rounded-2xl ${
                  msg.role === 'user'
                    ? 'bg-primary-600 text-white rounded-br-md'
                    : 'bg-gray-100 text-gray-800 rounded-bl-md'
                }`}
              >
                <p className="whitespace-pre-wrap">{msg.content}</p>
              </div>
            </div>
          ))
        )}
        
        {isPending && (
          <div className="flex justify-start">
            <div className="bg-gray-100 p-3 rounded-2xl rounded-bl-md">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce animation-delay-100" />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce animation-delay-200" />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input form */}
      <form onSubmit={handleSubmit} className="p-4 border-t">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Спросите о встрече..."
            className="flex-1 border border-gray-300 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            disabled={isPending}
          />
          <button
            type="submit"
            disabled={!input.trim() || isPending}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            ➤
          </button>
        </div>
      </form>
    </div>
  );
};