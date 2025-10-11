import {
  ChatInput,
  ChatInputSubmit,
  ChatInputTextArea,
} from "@/components/ui/chat-input";
import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import api from "@/lib/axios";
import { useAuth } from "@/hooks/useAuth";
import * as Dialog from "@radix-ui/react-dialog";
import { Worker, Viewer, SpecialZoomLevel } from "@react-pdf-viewer/core";
import "@react-pdf-viewer/core/lib/styles/index.css";
import { zoomPlugin } from "@react-pdf-viewer/zoom";
import "@react-pdf-viewer/zoom/lib/styles/index.css";
import { ShimmerButton } from "@/components/ui/shimmer-button";
import workerUrl from "pdfjs-dist/build/pdf.worker.min.js?url";

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
  const [activeDrawing, setActiveDrawing] = useState(null);
  const { token, logout } = useAuth();
  const [selectedImage, setSelectedImage] = useState(null);
  const [uploadingImage, setUploadingImage] = useState(false);
  const fileInputRef = useRef(null);
  const pdfWorkerUrl = workerUrl;
  const zoomPluginInstance = zoomPlugin();
  const { ZoomIn, ZoomOut, CurrentScale } = zoomPluginInstance;

  const handleAuthExpired = () => {
    if (!logout) return;
    logout();
  };

  const handleDownloadDrawing = (url, filename) => {
    if (!url) return;
    const link = document.createElement("a");
    link.href = url;
    if (filename) {
      link.download = filename;
    }
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, streamingMessage]);

  // Cleanup image preview URL on unmount
  useEffect(() => {
    return () => {
      if (selectedImage?.preview) {
        URL.revokeObjectURL(selectedImage.preview);
      }
    };
  }, [selectedImage]);

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
              } else if (data.type === 'drawing') {
                // Handle product drawing
                setStreamingMessage(prev => ({
                  ...prev,
                  content: data.message,
                  drawing_url: data.drawing_url,
                  filename: data.filename
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

  const handleImageUpload = async (file, captionOverride = null, enquiryIdOverride = null) => {
    const id = enquiryIdOverride ?? enquiryId;
    if (!id) {
      setError('Please start a conversation first before uploading images');
      return;
    }

    const caption = (captionOverride ?? value.trim()) || 'Image for review';

      // Show the user's image message immediately with a local preview
      const tempId = `temp-${Date.now()}`;
      const localPreviewUrl = selectedImage?.preview || URL.createObjectURL(file);
      setMessages(prev => [
        ...prev,
        {
          id: tempId,
          role: 'user',
          content: caption,
          image_url: localPreviewUrl,
        },
      ]);

      // Clear the inline preview immediately from the input box
      const previewToRevoke = selectedImage?.preview || null;
      setSelectedImage(null);

      setUploadingImage(true);
      try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('caption', caption);

      const response = await api.post(`/enquiries/${id}/upload-image?caption=${encodeURIComponent(caption)}`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data'
        }
      });

      // Swap the local preview with the public URL returned from the server
      setMessages(prev => prev.map(m => m.id === tempId ? { ...m, image_url: response.data.image_url } : m));

      // Add AI analysis response
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.data.analysis
      }]);

      // Clear input and revoke the local preview URL
      if (previewToRevoke && localPreviewUrl === previewToRevoke) {
        URL.revokeObjectURL(previewToRevoke);
      }
      setValue('');
      
    } catch (err) {
      console.error('Error uploading image:', err);
      setError(err.response?.data?.detail || 'Failed to upload image');
      // Also surface an error in the chat so the user sees feedback
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Sorry, there was an error uploading or analyzing your image. Please try again.'
      }]);
    } finally {
      setUploadingImage(false);
    }
  };

  const handleImageSelect = (e) => {
    const file = e.target.files[0];
    if (file) {
      // Validate file type
      const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'];
      if (!validTypes.includes(file.type)) {
        setError('Please select a valid image file (JPG, PNG, GIF, or WebP)');
        return;
      }

      // Validate file size (max 5MB)
      if (file.size > 5242880) {
        setError('Image too large. Maximum size is 5MB');
        return;
      }

      setSelectedImage({
        file,
        preview: URL.createObjectURL(file)
      });
    }
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
                    {/* Image Display */}
                    {message.image_url && (
                      <div className={`rounded-xl overflow-hidden border border-gray-200 shadow-sm max-w-xs ${
                        message.role === 'user' ? 'ml-auto' : ''
                      }`}>
                        <img 
                          src={message.image_url} 
                          alt="Uploaded" 
                          className="w-full h-auto max-h-80 object-contain bg-white"
                        />
                      </div>
                    )}
                    
                    {message.content && message.content !== 'Image for review' && (
                      <div className={`rounded-2xl px-3 py-2 md:px-4 md:py-2 text-sm md:text-base whitespace-pre-wrap ${
                        message.role === 'user'
                          ? 'bg-black text-white'
                          : 'bg-neutral-100 text-black'
                      }`}>
                        {formatMessage(message.content)}
                      </div>
                    )}
                    
                    {/* Product Drawing Display */}
                    {message.drawing_url && (
                      <div 
                        className="cursor-pointer hover:opacity-95 transition-opacity mt-2"
                        onClick={() => setActiveDrawing({ url: message.drawing_url, filename: message.filename })}
                      >
                        <Worker workerUrl={pdfWorkerUrl}>
                          <div style={{ height: '300px', width: '100%' }} className="bg-gray-50 rounded-lg border border-gray-200 overflow-hidden">
                            <Viewer
                              fileUrl={message.drawing_url}
                              defaultScale={SpecialZoomLevel.PageWidth}
                              theme="light"
                            />
                          </div>
                        </Worker>
                      </div>
                    )}
      <Dialog.Root open={!!activeDrawing} onOpenChange={(open) => {
        if (!open) {
          setActiveDrawing(null);
        }
      }}>
        {activeDrawing && (
          <Dialog.Portal>
            <Dialog.Overlay className="fixed inset-0 bg-black/60 z-50" />
            <Dialog.Content className="fixed inset-0 z-50 flex items-center justify-center p-4">
              <div className="bg-white rounded-lg shadow-xl max-w-5xl w-full max-h-[90vh] flex flex-col">
                <div className="flex justify-between items-center px-4 py-3 border-b border-gray-200">
                  <div>
                    <Dialog.Title className="text-lg font-semibold text-gray-900">
                      {activeDrawing.filename || "Technical Drawing"}
                    </Dialog.Title>
                    <Dialog.Description className="text-sm text-gray-500">
                      Use the zoom controls below to view the drawing.
                    </Dialog.Description>
                  </div>
                  <div className="flex items-center gap-2">
                    <Dialog.Close className="inline-flex items-center justify-center w-9 h-9 rounded-md border border-gray-200 hover:bg-gray-100 text-gray-700" title="Close">
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </Dialog.Close>
                  </div>
                </div>
                <div className="flex-1 overflow-auto bg-gray-100">
                  <div className="flex flex-col items-center p-4 gap-4">
                    <div className="flex items-center gap-2 bg-white px-4 py-2 rounded-lg shadow-sm border border-gray-200">
                      {ZoomOut && <ZoomOut />}
                      {CurrentScale && (
                        <div className="px-2">
                          <CurrentScale>
                            {(props) => <span className="text-sm font-medium">{`${Math.round(props.scale * 100)}%`}</span>}
                          </CurrentScale>
                        </div>
                      )}
                      {ZoomIn && <ZoomIn />}
                    </div>
                    <Worker workerUrl={pdfWorkerUrl}>
                      <div className="w-full max-w-[900px] border border-gray-200 rounded overflow-hidden bg-white">
                        <Viewer
                          fileUrl={activeDrawing.url}
                          defaultScale={SpecialZoomLevel.PageWidth}
                          theme="light"
                          plugins={[zoomPluginInstance]}
                        />
                      </div>
                    </Worker>
                  </div>
                </div>
              </div>
            </Dialog.Content>
          </Dialog.Portal>
        )}
      </Dialog.Root>
                    
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
              {(isLoading || uploadingImage) && !streamingMessage && (
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
          {/* Image Upload Input (Hidden) */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleImageSelect}
            accept="image/jpeg,image/jpg,image/png,image/gif,image/webp"
            className="hidden"
          />
          
          {/* Chat Input with integrated plus button and file preview */}
          <div className="relative">
            {/* Selected Image Preview - Inside the input container */}
            {selectedImage && (
              <motion.div 
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                className="mb-2 relative inline-block"
              >
                <div className="relative group">
                  <img 
                    src={selectedImage.preview} 
                    alt="Preview" 
                    className="w-24 h-24 rounded-lg object-cover border border-gray-300 shadow-sm"
                  />
                  <button
                    onClick={() => {
                      URL.revokeObjectURL(selectedImage.preview);
                      setSelectedImage(null);
                    }}
                    className="absolute -top-2 -right-2 p-1 bg-black text-white rounded-full hover:bg-gray-800 transition-colors shadow-lg"
                    title="Remove image"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
              </motion.div>
            )}
            
            <ChatInput
              variant="default"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              onSubmit={async () => {
                if (selectedImage) {
                  const caption = (value || '').trim() || 'Image for review';
                  // If no enquiry exists yet, create it first using the typed message
                  if (!enquiryId) {
                    const userMessage = (value || '').trim();
                    if (!userMessage) {
                      setError('Please enter a message before sending an image');
                      return;
                    }

                    setIsLoading(true);
                    setError(null);
                    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
                    setValue(''); // clear input immediately
                    setHasMessages(true);
                    try {
                      const createResponse = await api.post(`/enquiries/`, { initial_message: userMessage });
                      const newId = createResponse.data.id;
                      if (!newId) throw new Error('Failed to create enquiry - no ID returned');
                      setEnquiryId(newId);

                      // Stream AI response to the initial text
                      await handleStreamingResponse(newId, userMessage);
                      // Then upload the image with the same caption
                      await handleImageUpload(selectedImage.file, caption, newId);
                      // Clear the text input after successful submission
                      setValue('');
                    } catch (err) {
                      console.error('Error creating enquiry or sending message:', err);
                      setError(err.response?.data?.detail || 'Failed to send message');
                    } finally {
                      setIsLoading(false);
                    }
                  } else {
                    setValue(''); // clear input immediately
                    await handleImageUpload(selectedImage.file, caption);
                  }
                } else {
                  await handleSubmit();
                }
              }}
              loading={isLoading || uploadingImage}
              onStop={() => setIsLoading(false)}
              hasAttachment={!!selectedImage}
            >
              {/* Plus Icon for Image Upload - Inside input */}
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={isLoading || uploadingImage || !enquiryId}
                type="button"
                className="flex-shrink-0 p-1.5 -ml-3 rounded-lg hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                title="Upload image"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
              </button>
              
              <ChatInputTextArea placeholder="Ask about a quote" className="text-base md:text-lg w-full min-h-[48px]" />
              <ChatInputSubmit />
            </ChatInput>
          </div>
        </div>
      </div>
    </div>
  );
}
