import {
  ChatInput,
  ChatInputSubmit,
  ChatInputTextArea,
} from "@/components/ui/chat-input";
import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import api from "@/lib/axios";
import { useAuth } from "@/hooks/useAuth";

export default function Enquiries() {
  const [value, setValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [hasMessages, setHasMessages] = useState(false);
  const [messages, setMessages] = useState([]);
  const [enquiryId, setEnquiryId] = useState(null);
  const [conversationTitle, setConversationTitle] = useState("");
  const [error, setError] = useState(null);
  const [streamingMessage, setStreamingMessage] = useState(null);
  const messagesEndRef = useRef(null);
  const { token } = useAuth();

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, streamingMessage]);

  // Real streaming from backend
  const handleStreamingResponse = async (enquiryId, userMessage) => {
    try {
      const response = await fetch(`/api/enquiries/${enquiryId}/message/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ content: userMessage })
      });

      if (!response.ok) {
        throw new Error('Failed to get streaming response');
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      let fullContent = '';

      // Initialize streaming message
      setStreamingMessage({
        role: 'assistant',
        content: '',
        draft_quote: null
      });

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop(); // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              
              if (data.type === 'content') {
                fullContent += data.content;
                setStreamingMessage(prev => ({
                  ...prev,
                  content: fullContent
                }));
              } else if (data.type === 'question') {
                // Handle question - for now just show as regular message
                fullContent = data.question;
                setStreamingMessage(prev => ({
                  ...prev,
                  content: fullContent
                }));
              } else if (data.type === 'draft_ready') {
                // Handle draft quote
                setStreamingMessage(prev => ({
                  ...prev,
                  content: data.message,
                  draft_quote: data.draft_quote
                }));
              } else if (data.type === 'error') {
                setStreamingMessage(prev => ({
                  ...prev,
                  content: data.message
                }));
              } else if (data.type === 'done') {
                // Move streaming message to regular messages
                setStreamingMessage(currentMsg => {
                  if (currentMsg) {
                    setMessages(prev => [...prev, currentMsg]);
                  }
                  return null;
                });
                return;
              }
            } catch (e) {
              console.error('Error parsing streaming data:', e);
            }
          }
        }
      }

      // Finalize the message (in case 'done' wasn't received)
      setStreamingMessage(currentMsg => {
        if (currentMsg && currentMsg.content) {
          setMessages(prev => [...prev, currentMsg]);
        }
        return null;
      });

    } catch (error) {
      console.error('Streaming error:', error);
      setError('Failed to get AI response');
      setStreamingMessage(null);
    }
  };

  // Format message content with markdown support
  const formatMessage = (text) => {
    // Replace **text** with bold
    const parts = [];
    let lastIndex = 0;
    const boldRegex = /\*\*(.+?)\*\*/g;
    let match;

    while ((match = boldRegex.exec(text)) !== null) {
      // Add text before the match
      if (match.index > lastIndex) {
        parts.push(text.substring(lastIndex, match.index));
      }
      // Add bold text
      parts.push(<strong key={match.index} className="font-bold">{match[1]}</strong>);
      lastIndex = match.index + match[0].length;
    }
    
    // Add remaining text
    if (lastIndex < text.length) {
      parts.push(text.substring(lastIndex));
    }
    
    return parts.length > 0 ? parts : text;
  };

  const generateConversationTitle = async (firstMessage) => {
    try {
      // Use AI to generate a creative conversation title
      const response = await api.post('/enquiries/generate-title', {
        message: firstMessage
      });
      setConversationTitle(response.data.title || firstMessage.substring(0, 30));
    } catch (err) {
      console.error('Error generating title:', err);
      // Fallback to first few words if AI fails
      const fallback = firstMessage.trim().split(' ').slice(0, 4).join(' ');
      setConversationTitle(fallback.length > 30 ? fallback.substring(0, 30) + '...' : fallback);
    }
  };

  const saveTranscript = () => {
    // Format the conversation transcript
    const timestamp = new Date().toLocaleString();
    let transcript = `CONVERSATION TRANSCRIPT\n`;
    transcript += `Title: ${conversationTitle || 'Conversation'}\n`;
    transcript += `Generated: ${timestamp}\n`;
    transcript += `Enquiry ID: ${enquiryId || 'N/A'}\n`;
    transcript += `${'='.repeat(60)}\n\n`;
    
    messages.forEach((msg, idx) => {
      const speaker = msg.role === 'user' ? 'CUSTOMER' : 'ASSISTANT';
      transcript += `[${speaker}]\n`;
      transcript += `${msg.content}\n`;
      
      // Add draft quote details if present
      if (msg.draft_quote) {
        transcript += `\n--- DRAFT QUOTATION ---\n`;
        transcript += `Item: ${msg.draft_quote.item_name}\n`;
        if (msg.draft_quote.quantity) {
          transcript += `Quantity: ${msg.draft_quote.quantity} ${msg.draft_quote.unit}\n`;
        }
        transcript += `Base Price: $${msg.draft_quote.base_price.toFixed(2)} per ${msg.draft_quote.unit}\n`;
        
        if (msg.draft_quote.adjustments?.length > 0) {
          transcript += `\nAdjustments:\n`;
          msg.draft_quote.adjustments.forEach(adj => {
            transcript += `  - ${adj.description}: $${adj.amount.toFixed(2)}\n`;
          });
        }
        
        transcript += `\nTOTAL: $${msg.draft_quote.total_price.toFixed(2)}\n`;
        
        if (msg.draft_quote.conditions?.length > 0) {
          transcript += `\nConditions:\n`;
          msg.draft_quote.conditions.forEach(cond => {
            transcript += `  - ${cond}\n`;
          });
        }
        transcript += `${'-'.repeat(40)}\n`;
      }
      
      transcript += `\n`;
    });
    
    transcript += `\n${'='.repeat(60)}\n`;
    transcript += `End of transcript\n`;
    
    // Create and download file
    const blob = new Blob([transcript], { type: 'text/plain' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transcript_${enquiryId || 'chat'}_${Date.now()}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  const handleSubmit = async () => {
    if (!value.trim()) return;
    
    setIsLoading(true);
    setError(null);
    const userMessage = value;
    
    // Add user message immediately
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setValue("");
    setHasMessages(true);
    
    try {
      let currentEnquiryId = enquiryId;
      
      let response;
      
      // Create enquiry if first message
      if (!currentEnquiryId) {
        // Generate conversation title from first message
        generateConversationTitle(userMessage);
        
        const createResponse = await api.post(`/enquiries/`, {
          initial_message: userMessage
        });
        currentEnquiryId = createResponse.data.id;
        setEnquiryId(currentEnquiryId);
        console.log('Created enquiry:', currentEnquiryId);
        
        // Validate enquiry ID before proceeding
        if (!currentEnquiryId) {
          throw new Error('Failed to create enquiry - no ID returned');
        }
      }
      
      // Use real streaming for AI response
      await handleStreamingResponse(currentEnquiryId, userMessage);
      
    } catch (err) {
      console.error('Error sending message:', err);
      setError(err.response?.data?.detail || 'Failed to send message');
      
      // Add error message
      setMessages(prev => [...prev, { 
        role: 'assistant', 
        content: 'Sorry, there was an error processing your request. Please try again.'
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="flex h-screen w-full flex-col overflow-hidden">
      {/* Header with Save Transcript - Only shows when there are messages */}
      {hasMessages && (
        <div className="w-full bg-white sticky top-0 z-10">
          <div className="w-full max-w-2xl mx-auto px-4 py-3 flex justify-between items-center">
            <h2 className="text-base font-medium text-gray-800">
              {conversationTitle || 'New Conversation'}
            </h2>
            <button
              onClick={saveTranscript}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 hover:bg-gray-200 rounded-lg transition-colors flex items-center gap-2"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
              </svg>
              Save Transcript
            </button>
          </div>
        </div>
      )}
      
      {/* Messages Area - Scrollable */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {hasMessages ? (
          <div className="px-4 py-4 md:p-4 min-h-full">
            <div className="w-full max-w-2xl mx-auto space-y-4">
              {messages.map((message, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                  className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {message.role === 'assistant' && (
                    <img 
                      src="/pengu.jpg" 
                      alt="AI Assistant" 
                      className="w-8 h-8 rounded-full mr-2 mt-1 flex-shrink-0"
                    />
                  )}
                  <div className="flex flex-col gap-2 max-w-[85%] md:max-w-[80%]">
                    <div className={`rounded-2xl px-3 py-2 md:px-4 md:py-2 text-sm md:text-base whitespace-pre-wrap ${
                      message.role === 'user'
                        ? 'bg-black text-white'
                        : 'bg-neutral-100 text-black'
                    }`}>
                      {formatMessage(message.content)}
                    </div>
                    
                    {/* Draft Quote Display */}
                    {message.draft_quote && (
                      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm">
                        <h4 className="font-bold text-blue-900 mb-3">Draft Quotation</h4>
                        
                        <div className="space-y-2 text-gray-700">
                          <div className="flex justify-between">
                            <span className="font-semibold">Item:</span>
                            <span>{message.draft_quote.item_name}</span>
                          </div>
                          
                          {message.draft_quote.quantity && (
                            <div className="flex justify-between">
                              <span className="font-semibold">Quantity:</span>
                              <span>{message.draft_quote.quantity} {message.draft_quote.unit}</span>
                            </div>
                          )}
                          
                          <div className="flex justify-between">
                            <span className="font-semibold">Base Price:</span>
                            <span>${message.draft_quote.base_price.toFixed(2)} per {message.draft_quote.unit}</span>
                          </div>
                          
                          {message.draft_quote.adjustments && message.draft_quote.adjustments.length > 0 && (
                            <div className="mt-3 pt-2 border-t border-blue-200">
                              <p className="font-semibold mb-1">Adjustments:</p>
                              {message.draft_quote.adjustments.map((adj, idx) => (
                                <div key={idx} className="flex justify-between text-xs ml-2">
                                  <span>• {adj.description}</span>
                                  <span>${adj.amount.toFixed(2)}</span>
                                </div>
                              ))}
                            </div>
                          )}
                          
                          <div className="flex justify-between font-bold text-lg mt-3 pt-2 border-t border-blue-300">
                            <span>Total:</span>
                            <span className="text-blue-700">${message.draft_quote.total_price.toFixed(2)}</span>
                          </div>
                          
                          {message.draft_quote.conditions && message.draft_quote.conditions.length > 0 && (
                            <div className="mt-3 pt-2 border-t border-blue-200">
                              <p className="font-semibold mb-1">Conditions:</p>
                              <ul className="text-xs space-y-1">
                                {message.draft_quote.conditions.map((cond, idx) => (
                                  <li key={idx}>• {cond}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          
                          <div className="mt-4 pt-3 border-t border-blue-200 text-xs text-blue-800 bg-blue-100 rounded p-2">
                            ✓ This quote has been submitted to our team for review. We'll get back to you shortly!
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </motion.div>
              ))}

              {/* Ghost streaming message */}
              {streamingMessage && (
                <motion.div
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                  className="flex justify-start"
                >
                  <img 
                    src="/pengu.jpg" 
                    alt="AI Assistant" 
                    className="w-8 h-8 rounded-full mr-2 mt-1 flex-shrink-0"
                  />
                  <div className="flex flex-col gap-2 max-w-[85%] md:max-w-[80%]">
                    <div className="bg-neutral-100 text-black rounded-2xl px-3 py-2 md:px-4 md:py-2 text-sm md:text-base whitespace-pre-wrap">
                      {formatMessage(streamingMessage.content)}
                    </div>
                    
                    {/* Draft Quote Display for streaming */}
                    {streamingMessage.draft_quote && (
                      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm">
                        <h4 className="font-bold text-blue-900 mb-3">Draft Quotation</h4>
                        
                        <div className="space-y-2 text-gray-700">
                          <div className="flex justify-between">
                            <span className="font-semibold">Item:</span>
                            <span>{streamingMessage.draft_quote.item_name}</span>
                          </div>
                          
                          {streamingMessage.draft_quote.quantity && (
                            <div className="flex justify-between">
                              <span className="font-semibold">Quantity:</span>
                              <span>{streamingMessage.draft_quote.quantity} {streamingMessage.draft_quote.unit}</span>
                            </div>
                          )}
                          
                          <div className="flex justify-between">
                            <span className="font-semibold">Base Price:</span>
                            <span>${streamingMessage.draft_quote.base_price.toFixed(2)} per {streamingMessage.draft_quote.unit}</span>
                          </div>
                          
                          {streamingMessage.draft_quote.adjustments && streamingMessage.draft_quote.adjustments.length > 0 && (
                            <div className="mt-3 pt-2 border-t border-blue-200">
                              <p className="font-semibold mb-1">Adjustments:</p>
                              {streamingMessage.draft_quote.adjustments.map((adj, idx) => (
                                <div key={idx} className="flex justify-between text-xs ml-2">
                                  <span>• {adj.description}</span>
                                  <span>${adj.amount.toFixed(2)}</span>
                                </div>
                              ))}
                            </div>
                          )}
                          
                          <div className="flex justify-between font-bold text-lg mt-3 pt-2 border-t border-blue-300">
                            <span>Total:</span>
                            <span className="text-blue-700">${streamingMessage.draft_quote.total_price.toFixed(2)}</span>
                          </div>
                          
                          {streamingMessage.draft_quote.conditions && streamingMessage.draft_quote.conditions.length > 0 && (
                            <div className="mt-3 pt-2 border-t border-blue-200">
                              <p className="font-semibold mb-1">Conditions:</p>
                              <ul className="text-xs space-y-1">
                                {streamingMessage.draft_quote.conditions.map((cond, idx) => (
                                  <li key={idx}>• {cond}</li>
                                ))}
                              </ul>
                            </div>
                          )}
                          
                          <div className="mt-4 pt-3 border-t border-blue-200 text-xs text-blue-800 bg-blue-100 rounded p-2">
                            ✓ This quote has been submitted to our team for review. We'll get back to you shortly!
                          </div>
                        </div>
                      </div>
                    )}
                  </div>
                </motion.div>
              )}

              {/* Loading indicator */}
              {isLoading && !streamingMessage && (
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex justify-start items-center"
                >
                  <img 
                    src="/pengu.jpg" 
                    alt="AI Assistant" 
                    className="w-8 h-8 rounded-full mr-2 flex-shrink-0"
                  />
                  <div className="bg-neutral-100 rounded-2xl px-4 py-3 flex items-center">
                    <div className="flex gap-1 items-center">
                      <span className="w-2 h-2 bg-neutral-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                      <span className="w-2 h-2 bg-neutral-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                      <span className="w-2 h-2 bg-neutral-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                    </div>
                  </div>
                </motion.div>
              )}
              
              {/* Scroll anchor */}
              <div ref={messagesEndRef} />
            </div>
          </div>
        ) : (
          /* Centered Title - Only shows when no messages */
          <div className="flex items-center justify-center min-h-full px-4">
            <div className="flex flex-col items-center justify-center text-center space-y-4 w-full max-w-md">
              <AnimatePresence>
                <motion.div
                  initial={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <p className="text-2xl md:text-3xl text-foreground">
                    how can i help you today?
                  </p>
                  {error && (
                    <p className="text-sm text-red-500 mt-2">
                      {error}
                    </p>
                  )}
                </motion.div>
              </AnimatePresence>
            </div>
          </div>
        )}
      </div>

      {/* Input Box - Fixed at bottom */}
      <div className="w-full bg-white flex-shrink-0">
        <div className="w-full max-w-2xl mx-auto px-4 py-3 md:p-4">
          <ChatInput
            variant="default"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onSubmit={handleSubmit}
            loading={isLoading}
            onStop={() => setIsLoading(false)}
          >
            <ChatInputTextArea placeholder="Ask about a quote" className="text-base md:text-lg w-full min-h-[48px]" />
            <ChatInputSubmit />
          </ChatInput>
        </div>
      </div>
    </div>
  );
}
