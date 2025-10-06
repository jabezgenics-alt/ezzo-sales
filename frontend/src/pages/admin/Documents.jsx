import { useState, useEffect, useRef } from 'react';
import FileUpload from '@/components/ui/file-upload';
import api from '@/lib/axios';

export default function AdminDocuments() {
  const fileUploadRef = useRef(null);
  const [documents, setDocuments] = useState([]);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(true);
  const [reprocessing, setReprocessing] = useState(false);
  const uploadedFileIdsRef = useRef(new Set()); // Track uploaded file IDs to prevent duplicates
  const [knowledgeSummary, setKnowledgeSummary] = useState(null); // Master knowledge base summary
  const [generatingSummary, setGeneratingSummary] = useState(false); // Track if generating summary
  const [processingUploaded, setProcessingUploaded] = useState(false); // Track processing uploaded docs

  // Fetch documents on component mount
  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      setLoading(true);
      const response = await api.get(`/documents/`);
      console.log('Documents:', response.data); // Debug log
      if (response.data.length > 0) {
        console.log('First document status:', response.data[0].status); // Debug log
      }
      setDocuments(response.data);
    } catch (err) {
      console.error('Error fetching documents:', err);
      setError('Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDocument = async (documentId) => {
    if (!confirm('Are you sure you want to delete this document?')) {
      return;
    }
    
    try {
      await api.delete(`/documents/${documentId}`);
      // Refresh the documents list
      await fetchDocuments();
    } catch (err) {
      console.error('Error deleting document:', err);
      setError('Failed to delete document');
    }
  };

  const handleReprocessAll = async () => {
    if (!confirm('Reprocess all documents to extract pricing data?\n\nThis will re-analyze all documents using AI. It may take a few minutes.')) {
      return;
    }
    
    try {
      setReprocessing(true);
      setError(null);
      const response = await api.post('/documents/reprocess-all');
      console.log('Reprocess response:', response.data);
      
      // Refresh the documents list
      await fetchDocuments();
      
      const message = `Reprocessed ${response.data.processed_count} of ${response.data.total_documents} documents!`;
      if (response.data.failed_count) {
        alert(`${message}\n\nFailed: ${response.data.failed_count} documents`);
      } else {
        alert(message);
      }
    } catch (err) {
      console.error('Error reprocessing documents:', err);
      setError(err.response?.data?.detail || 'Failed to reprocess documents');
    } finally {
      setReprocessing(false);
    }
  };

  const handleDeleteAllDocuments = async () => {
    const confirmText = 'DELETE ALL';
    const userInput = prompt(
      `WARNING: This will delete ALL documents, files, and vector store data!\n\n` +
      `This action CANNOT be undone.\n\n` +
      `Type "${confirmText}" to confirm:`
    );
    
    if (userInput !== confirmText) {
      return;
    }
    
    try {
      setLoading(true);
      const response = await api.delete('/documents/');
      console.log('Cleanup response:', response.data);
      
      // Clear knowledge summary
      setKnowledgeSummary(null);
      
      // Clear uploaded file IDs
      uploadedFileIdsRef.current.clear();
      
      // Clear file upload component
      if (fileUploadRef.current) {
        fileUploadRef.current.clearFiles();
      }
      
      // Refresh the documents list
      await fetchDocuments();
      
      alert(`Successfully deleted ${response.data.deleted_count} documents!`);
    } catch (err) {
      console.error('Error deleting all documents:', err);
      setError(err.response?.data?.detail || 'Failed to delete all documents');
    } finally {
      setLoading(false);
    }
  };

  const handleGenerateKnowledgeSummary = async () => {
    setGeneratingSummary(true);
    setError(null);
    try {
      const response = await api.post('/documents/generate-knowledge-summary');
      setKnowledgeSummary(response.data.summary);
    } catch (err) {
      console.error('Error generating knowledge summary:', err);
      setError(err.response?.data?.detail || 'Failed to generate knowledge base summary');
    } finally {
      setGeneratingSummary(false);
    }
  };

  const handleProcessAllUploaded = async () => {
    const uploadedDocs = documents.filter(d => d.status === 'uploaded');
    if (uploadedDocs.length === 0) {
      alert('No uploaded documents to process');
      return;
    }

    if (!confirm(`Process ${uploadedDocs.length} uploaded documents?\n\nThis will extract pricing data using AI.`)) {
      return;
    }

    setProcessingUploaded(true);
    setError(null);
    let successCount = 0;
    let failCount = 0;

    try {
      // Process in batches of 3 to avoid overwhelming
      const BATCH_SIZE = 3;
      for (let i = 0; i < uploadedDocs.length; i += BATCH_SIZE) {
        const batch = uploadedDocs.slice(i, i + BATCH_SIZE);
        console.log(`Processing batch ${Math.floor(i / BATCH_SIZE) + 1} of ${Math.ceil(uploadedDocs.length / BATCH_SIZE)}`);

        const processPromises = batch.map(async (doc) => {
          try {
            await api.post(`/documents/${doc.id}/process`);
            console.log('Processed document:', doc.id);
            successCount++;
          } catch (err) {
            console.error('Error processing document:', doc.id, err);
            failCount++;
          }
        });

        await Promise.all(processPromises);

        // Refresh documents list after each batch
        await fetchDocuments();

        // Small delay between batches
        if (i + BATCH_SIZE < uploadedDocs.length) {
          await new Promise(resolve => setTimeout(resolve, 1000));
        }
      }

      alert(`Processing complete!\n\nSucceeded: ${successCount}\nFailed: ${failCount}`);
    } catch (err) {
      console.error('Error processing uploaded documents:', err);
      setError(err.response?.data?.detail || 'Failed to process documents');
    } finally {
      setProcessingUploaded(false);
      await fetchDocuments();
    }
  };

  const handleFilesUploaded = async (files) => {
    setError(null);
    setUploading(true);

    const MAX_CONCURRENT_UPLOADS = 5; // Limit concurrent uploads
    let successCount = 0;
    let failCount = 0;

    try {
      // Filter files to upload
      const filesToUpload = files.filter(file => {
        if (uploadedFileIdsRef.current.has(file.id)) {
          console.log('Skipping already uploaded file:', file.id);
          return false;
        }
        return file.file && file.progress === 100;
      });

      console.log(`Uploading ${filesToUpload.length} files with max ${MAX_CONCURRENT_UPLOADS} concurrent uploads...`);

      // Process files in batches with concurrency limit
      for (let i = 0; i < filesToUpload.length; i += MAX_CONCURRENT_UPLOADS) {
        const batch = filesToUpload.slice(i, i + MAX_CONCURRENT_UPLOADS);
        
        console.log(`Processing batch ${Math.floor(i / MAX_CONCURRENT_UPLOADS) + 1} of ${Math.ceil(filesToUpload.length / MAX_CONCURRENT_UPLOADS)} (${batch.length} files)`);
        
        // Upload batch concurrently
        const uploadPromises = batch.map(async (file) => {
          try {
            // Mark as uploaded immediately to prevent duplicates
            uploadedFileIdsRef.current.add(file.id);

            const formData = new FormData();
            formData.append('file', file.file);
            
            const response = await api.post(`/documents/upload`, formData);
            console.log('File uploaded:', response.data.original_filename);
            
            // Process the document immediately
            if (response.data.id) {
              try {
                await api.post(`/documents/${response.data.id}/process`);
                console.log('Document processed:', response.data.id);
                successCount++;
              } catch (processError) {
                console.error('Error processing document:', processError);
                failCount++;
              }
            }
          } catch (uploadError) {
            console.error('Error uploading file:', uploadError);
            failCount++;
          }
        });

        // Wait for this batch to complete before starting next batch
        await Promise.all(uploadPromises);
        
        // Small delay between batches to avoid overwhelming the server
        if (i + MAX_CONCURRENT_UPLOADS < filesToUpload.length) {
          await new Promise(resolve => setTimeout(resolve, 500));
        }
      }
      
      console.log(`Upload complete: ${successCount} succeeded, ${failCount} failed`);
      
      // Fetch updated documents list
      await fetchDocuments();
      
      // Clear the upload component's state after successful upload
      if (fileUploadRef.current) {
        fileUploadRef.current.clearFiles();
        // Clear the uploaded IDs tracker
        uploadedFileIdsRef.current.clear();
      }

      // Show summary
      if (failCount > 0) {
        alert(`Upload complete!\n\nSucceeded: ${successCount}\nFailed: ${failCount}`);
      }
      
    } catch (err) {
      console.error('Upload error:', err);
      setError(err.response?.data?.detail || 'Failed to upload files');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen p-4">
      <div className="max-w-5xl mx-auto space-y-6">
        <div className="text-left">
          <h1 className="text-3xl md:text-4xl font-bold tracking-wide">
            Documents
          </h1>
          <p className="text-muted-foreground mt-2 text-sm md:text-base">
            Upload and manage documents for the knowledge base
          </p>
          {error && (
            <p className="text-sm text-red-500 mt-2">
              {error}
            </p>
          )}
          {uploading && (
            <p className="text-sm text-blue-500 mt-2">
              Uploading and processing documents...
            </p>
          )}
        </div>

        <FileUpload ref={fileUploadRef} onFilesUploaded={handleFilesUploaded} />

        {/* Process Uploaded Documents */}
        {documents.filter(d => d.status === 'uploaded').length > 0 && (
          <div className="mt-8 p-6 bg-gradient-to-r from-orange-50 to-amber-50 border border-orange-200 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-gray-800">Process Uploaded Documents</h2>
                <p className="text-sm text-gray-600 mt-1">
                  Extract pricing data from uploaded documents that haven't been processed yet
                </p>
              </div>
              <button
                onClick={handleProcessAllUploaded}
                disabled={processingUploaded}
                className={`px-6 py-3 rounded-lg font-semibold text-white transition-all ${
                  processingUploaded
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-orange-600 hover:bg-orange-700 hover:shadow-lg'
                }`}
              >
                {processingUploaded ? 'Processing...' : `Process All (${documents.filter(d => d.status === 'uploaded').length})`}
              </button>
            </div>
          </div>
        )}

        {/* Batch Reprocess */}
        {documents.filter(d => d.status === 'processed').length > 0 && (
          <div className="mt-8 p-6 bg-gradient-to-r from-green-50 to-emerald-50 border border-green-200 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-gray-800">Batch Reprocess</h2>
                <p className="text-sm text-gray-600 mt-1">
                  Re-extract pricing data from all processed documents using AI
                </p>
              </div>
              <button
                onClick={handleReprocessAll}
                disabled={reprocessing}
                className={`px-6 py-3 rounded-lg font-semibold text-white transition-all ${
                  reprocessing
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-green-600 hover:bg-green-700 hover:shadow-lg'
                }`}
              >
                {reprocessing ? 'Reprocessing...' : `Reprocess All (${documents.filter(d => d.status === 'processed').length})`}
              </button>
            </div>
          </div>
        )}

        {/* Knowledge Base Summary Section */}
        {documents.length > 0 && (
          <div className="mt-8 p-6 bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-2xl font-bold text-gray-800">Knowledge Base Summary</h2>
                <p className="text-sm text-gray-600 mt-1">
                  Generate a comprehensive structured summary of all uploaded documents
                </p>
              </div>
              <button
                onClick={handleGenerateKnowledgeSummary}
                disabled={generatingSummary || documents.filter(d => d.status === 'processed').length === 0}
                className={`px-6 py-3 rounded-lg font-semibold text-white transition-all ${
                  generatingSummary || documents.filter(d => d.status === 'processed').length === 0
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-blue-600 hover:bg-blue-700 hover:shadow-lg'
                }`}
              >
                {generatingSummary ? 'Generating...' : 'Generate Summary'}
              </button>
            </div>

            {knowledgeSummary && (
              <div className="mt-4 p-6 bg-white rounded-lg border border-gray-200 shadow-sm">
                <div className="space-y-3">
                  {knowledgeSummary.split('\n').map((line, idx) => {
                    if (line.startsWith('# ')) {
                      return <h2 key={idx} className="text-2xl font-bold text-gray-900 mt-6 mb-3">{line.substring(2)}</h2>;
                    } else if (line.startsWith('## ')) {
                      return <h3 key={idx} className="text-xl font-semibold text-gray-800 mt-4 mb-2">{line.substring(3)}</h3>;
                    } else if (line.startsWith('- ')) {
                      return <li key={idx} className="ml-6 text-gray-700">{line.substring(2)}</li>;
                    } else if (line.startsWith('**') && line.endsWith('**')) {
                      return <p key={idx} className="font-semibold text-gray-800">{line.replace(/\*\*/g, '')}</p>;
                    } else if (line.trim() === '') {
                      return <div key={idx} className="h-2"></div>;
                    } else {
                      return <p key={idx} className="text-gray-700">{line}</p>;
                    }
                  })}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Danger Zone - Delete All */}
        {documents.length > 0 && (
          <div className="mt-8 p-6 bg-red-50 border-2 border-red-300 rounded-lg">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-bold text-red-800">Danger Zone</h2>
                <p className="text-sm text-red-700 mt-1">
                  Delete all documents, files, and vector store data. This action cannot be undone.
                </p>
              </div>
              <button
                onClick={handleDeleteAllDocuments}
                disabled={loading}
                className={`px-6 py-3 rounded-lg font-semibold text-white transition-all ${
                  loading
                    ? 'bg-gray-400 cursor-not-allowed'
                    : 'bg-red-600 hover:bg-red-700 hover:shadow-lg'
                }`}
              >
                {loading ? 'Deleting...' : 'Delete All Documents'}
              </button>
            </div>
          </div>
        )}

        {/* Documents List */}
        <div className="mt-8">
          <h2 className="text-2xl font-bold mb-4">Uploaded Documents</h2>
          {loading ? (
            <p className="text-gray-500">Loading documents...</p>
          ) : documents.length === 0 ? (
            <p className="text-gray-500">No documents uploaded yet</p>
          ) : (
            <div className="space-y-4">
              {documents.map((doc) => (
                <div
                  key={doc.id}
                  className="border rounded-lg p-4 bg-white shadow-sm hover:shadow-md transition-shadow"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h3 className="font-semibold text-lg">{doc.original_filename}</h3>
                      <div className="mt-2 space-y-1 text-sm text-gray-600">
                        <p>Type: {doc.file_type.toUpperCase()}</p>
                        <p>Size: {(doc.file_size / 1024).toFixed(2)} KB</p>
                        <p>Uploaded: {new Date(doc.created_at).toLocaleString()}</p>
                        {doc.processed_at && (
                          <p>Processed: {new Date(doc.processed_at).toLocaleString()}</p>
                        )}
                      </div>
                    </div>
                    <div className="ml-4 flex items-center gap-3">
                      <span
                        className={`inline-block px-3 py-1 rounded-full text-sm font-medium ${
                          doc.status === 'processed'
                            ? 'bg-green-100 text-green-800'
                            : doc.status === 'processing'
                            ? 'bg-blue-100 text-blue-800'
                            : doc.status === 'failed'
                            ? 'bg-red-100 text-red-800'
                            : 'bg-gray-100 text-gray-800'
                        }`}
                      >
                        {doc.status}
                      </span>
                      <button
                        onClick={() => handleDeleteDocument(doc.id)}
                        className="text-red-600 hover:text-red-800 font-medium text-sm"
                      >
                        Delete
                      </button>
                    </div>
                  </div>
                  {doc.error_message && (
                    <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                      <strong>Error:</strong> {doc.error_message}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
