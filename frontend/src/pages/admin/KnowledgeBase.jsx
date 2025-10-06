import { useState, useEffect } from 'react'
import { Button } from '../../components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../../components/ui/dialog'
import { Textarea } from '../../components/ui/textarea'
import { Badge } from '../../components/ui/badge'
import { ScrollArea } from '../../components/ui/scroll-area'
import { ConfirmDialog } from '../../components/ui/confirm-dialog'
import { useToast } from '../../components/ui/toast'
import { Loader2, Trash2 } from 'lucide-react'
import axios from '../../lib/axios'

export default function AdminKnowledgeBase() {
  const { toast } = useToast()
  const [documents, setDocuments] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedDocument, setSelectedDocument] = useState(null)
  const [documentContent, setDocumentContent] = useState('')
  const [loadingContent, setLoadingContent] = useState(false)
  const [editing, setEditing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [reprocessing, setReprocessing] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [currentPage, setCurrentPage] = useState(1)
  const [totalDocuments, setTotalDocuments] = useState(0)
  const [selectedDocs, setSelectedDocs] = useState([])
  const [confirmDialog, setConfirmDialog] = useState({ open: false, title: '', description: '', onConfirm: () => {} })
  const itemsPerPage = 20

  useEffect(() => {
    fetchDocuments(currentPage)
  }, [currentPage])

  const fetchDocuments = async (page = 1) => {
    try {
      setLoading(true)
      const skip = (page - 1) * itemsPerPage
      // Request one extra item to check if there's a next page
      const response = await axios.get(`/admin/documents?skip=${skip}&limit=${itemsPerPage + 1}`)
      const hasMore = response.data.length > itemsPerPage
      const docs = hasMore ? response.data.slice(0, itemsPerPage) : response.data
      setDocuments(docs)
      // Estimate total based on whether we have more
      if (hasMore || page > 1) {
        setTotalDocuments((page * itemsPerPage) + (hasMore ? 1 : 0))
      } else {
        setTotalDocuments(docs.length)
      }
    } catch (error) {
      console.error('Error fetching documents:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchDocumentContent = async (documentId) => {
    try {
      setLoadingContent(true)
      setDocumentContent('')
      const response = await axios.get(`/admin/documents/${documentId}/content`)
      setDocumentContent(response.data.content)
    } catch (error) {
      console.error('Error fetching document content:', error)
      setDocumentContent('Error loading content')
    } finally {
      setLoadingContent(false)
    }
  }

  const saveDocumentContent = async () => {
    try {
      setSaving(true)
      await axios.put(`/admin/documents/${selectedDocument.id}/content`, {
        content: documentContent
      })
      setEditing(false)
      toast({ title: 'Success', description: 'Document content updated successfully', variant: 'success' })
    } catch (error) {
      console.error('Error saving document content:', error)
      toast({ title: 'Error', description: 'Failed to save document content', variant: 'error' })
    } finally {
      setSaving(false)
    }
  }

  const deleteDocument = async (documentId) => {
    try {
      await axios.delete(`/admin/documents/${documentId}`)
      setDocuments(documents.filter(doc => doc.id !== documentId))
      toast({ title: 'Success', description: 'Document deleted successfully', variant: 'success' })
    } catch (error) {
      console.error('Error deleting document:', error)
      toast({ title: 'Error', description: 'Failed to delete document', variant: 'error' })
    }
  }

  const batchDeleteDocuments = async () => {
    try {
      await Promise.all(selectedDocs.map(id => axios.delete(`/admin/documents/${id}`)))
      setDocuments(documents.filter(doc => !selectedDocs.includes(doc.id)))
      setSelectedDocs([])
      toast({ title: 'Success', description: `${selectedDocs.length} documents deleted successfully`, variant: 'success' })
    } catch (error) {
      console.error('Error deleting documents:', error)
      toast({ title: 'Error', description: 'Failed to delete some documents', variant: 'error' })
    }
  }

  const reprocessDocument = async (documentId) => {
    try {
      setReprocessing(documentId)
      await axios.post(`/admin/documents/${documentId}/reprocess`)
      toast({ title: 'Success', description: 'Document reprocessing started', variant: 'success' })
      fetchDocuments(currentPage)
    } catch (error) {
      console.error('Error reprocessing document:', error)
      toast({ title: 'Error', description: 'Failed to reprocess document', variant: 'error' })
    } finally {
      setReprocessing(null)
    }
  }

  const toggleSelectDoc = (docId) => {
    setSelectedDocs(prev => 
      prev.includes(docId) ? prev.filter(id => id !== docId) : [...prev, docId]
    )
  }

  const toggleSelectAll = () => {
    if (selectedDocs.length === filteredDocuments.length) {
      setSelectedDocs([])
    } else {
      setSelectedDocs(filteredDocuments.map(doc => doc.id))
    }
  }

  const filteredDocuments = documents.filter(doc => {
    const matchesSearch = doc.original_filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         (doc.summary && doc.summary.toLowerCase().includes(searchTerm.toLowerCase()))
    const matchesStatus = statusFilter === 'all' || doc.status === statusFilter
    return matchesSearch && matchesStatus
  })

  const getStatusBadge = (status) => {
    const variants = {
      'processed': 'default',
      'uploaded': 'secondary',
      'processing': 'outline',
      'failed': 'destructive'
    }
    return <Badge variant={variants[status] || 'secondary'}>{status}</Badge>
  }

  if (loading) {
    return (
      <div className="p-8">
        <h1 className="text-3xl font-bold mb-4">Knowledge Base</h1>
        <p className="text-gray-600">Loading documents...</p>
      </div>
    )
  }

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold mb-2">Knowledge Base</h1>
          <p className="text-gray-600">Manage uploaded documents and their content</p>
        </div>
        <div className="flex items-center gap-3">
          {selectedDocs.length > 0 && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setConfirmDialog({
                open: true,
                title: 'Delete Documents',
                description: `Are you sure you want to delete ${selectedDocs.length} document(s)? This action cannot be undone.`,
                onConfirm: batchDeleteDocuments
              })}
            >
              <Trash2 className="h-4 w-4 mr-2" />
              Delete {selectedDocs.length} Selected
            </Button>
          )}
          <div className="text-sm text-gray-500">
            Total: {documents.length} documents
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-4 mb-6">
        <input
          type="text"
          placeholder="Search documents..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
        >
          <option value="all">All Status</option>
          <option value="processed">Processed</option>
          <option value="uploaded">Uploaded</option>
          <option value="processing">Processing</option>
          <option value="failed">Failed</option>
        </select>
      </div>

      {/* Documents List */}
      <div className="bg-white rounded-lg shadow">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left">
                  <input
                    type="checkbox"
                    checked={selectedDocs.length === filteredDocuments.length && filteredDocuments.length > 0}
                    onChange={toggleSelectAll}
                    className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                  />
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Document
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Type
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Size
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Uploaded
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {filteredDocuments.map((doc) => (
                <tr key={doc.id} className="hover:bg-gray-50">
                  <td className="px-4 py-4">
                    <input
                      type="checkbox"
                      checked={selectedDocs.includes(doc.id)}
                      onChange={() => toggleSelectDoc(doc.id)}
                      className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                    />
                  </td>
                  <td className="px-6 py-4">
                    <div>
                      <div className="text-sm font-medium text-gray-900">
                        {doc.original_filename}
                      </div>
                      {doc.summary && (
                        <div className="text-sm text-gray-500 mt-1 max-w-md truncate">
                          {doc.summary}
                        </div>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {getStatusBadge(doc.status)}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {doc.file_type?.toUpperCase()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {doc.file_size ? `${(doc.file_size / 1024).toFixed(1)} KB` : 'N/A'}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    {new Date(doc.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                    <div className="flex gap-2">
                      <Dialog>
                        <DialogTrigger asChild>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => {
                              setSelectedDocument(doc)
                              fetchDocumentContent(doc.id)
                            }}
                          >
                            View
                          </Button>
                        </DialogTrigger>
                        <DialogContent className="max-w-5xl max-h-[85vh]">
                          <div className="bg-white rounded-3xl p-6 flex flex-col" style={{height: 'calc(85vh - 60px)', maxHeight: '700px'}}>
                            <DialogHeader className="pb-4 border-b border-gray-200 flex-shrink-0">
                              <div className="flex items-start justify-between">
                                <div className="flex-1 pr-8">
                                  <DialogTitle className="text-xl font-semibold text-gray-900 mb-3">{doc.original_filename}</DialogTitle>
                                  <div className="flex gap-2 mb-2">
                                    {getStatusBadge(doc.status)}
                                    <Badge variant="outline">{doc.file_type?.toUpperCase()}</Badge>
                                  </div>
                                  <div className="flex gap-4 text-xs text-gray-500">
                                    <span>Uploaded: {new Date(doc.created_at).toLocaleString()}</span>
                                    {doc.processed_at && (
                                      <span>Processed: {new Date(doc.processed_at).toLocaleString()}</span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            </DialogHeader>
                            
                            <div className="flex-1 overflow-auto mt-4 mb-4 min-h-0">
                              {loadingContent ? (
                                <div className="flex items-center justify-center h-full">
                                  <div className="text-center">
                                    <Loader2 className="h-8 w-8 animate-spin text-blue-600 mx-auto mb-2" />
                                    <p className="text-sm text-gray-600">Loading document content...</p>
                                  </div>
                                </div>
                              ) : editing ? (
                                <Textarea
                                  value={documentContent}
                                  onChange={(e) => setDocumentContent(e.target.value)}
                                  className="w-full h-full min-h-[400px] resize-none font-mono text-sm bg-white border-gray-300"
                                  placeholder="Document content..."
                                />
                              ) : (
                                <div className="whitespace-pre-wrap text-sm leading-relaxed font-mono bg-gray-50 text-gray-800 p-4 rounded-lg border border-gray-200">
                                  {documentContent || 'No content available'}
                                </div>
                              )}
                            </div>
                            
                            <div className="flex gap-2 pt-4 border-t border-gray-200 flex-shrink-0">
                              {doc.status === 'processed' && (
                                <>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setEditing(!editing)}
                                    className="min-w-[80px]"
                                  >
                                    {editing ? 'Cancel' : 'Edit'}
                                  </Button>
                                  {editing && (
                                    <Button
                                      size="sm"
                                      onClick={saveDocumentContent}
                                      disabled={saving}
                                      className="min-w-[80px]"
                                    >
                                      {saving ? (
                                        <>
                                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                          Saving...
                                        </>
                                      ) : (
                                        'Save'
                                      )}
                                    </Button>
                                  )}
                                </>
                              )}
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => reprocessDocument(doc.id)}
                                disabled={reprocessing === doc.id}
                                className="min-w-[100px]"
                              >
                                {reprocessing === doc.id ? (
                                  <>
                                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                                    Processing...
                                  </>
                                ) : (
                                  'Reprocess'
                                )}
                              </Button>
                              <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => setConfirmDialog({
                                  open: true,
                                  title: 'Delete Document',
                                  description: `Are you sure you want to delete "${doc.original_filename}"? This action cannot be undone.`,
                                  onConfirm: () => deleteDocument(doc.id)
                                })}
                                className="min-w-[80px] ml-auto"
                              >
                                Delete
                              </Button>
                            </div>
                          </div>
                        </DialogContent>
                      </Dialog>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {filteredDocuments.length === 0 && (
        <div className="text-center py-8 text-gray-500">
          No documents found matching your criteria.
        </div>
      )}

      {/* Pagination */}
      {filteredDocuments.length > 0 && (
        <div className="mt-6 flex items-center justify-between">
          <div className="text-sm text-gray-500">
            Showing {((currentPage - 1) * itemsPerPage) + 1} to {Math.min(currentPage * itemsPerPage, totalDocuments)} of {totalDocuments} documents
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(prev => Math.max(1, prev - 1))}
              disabled={currentPage === 1}
            >
              Previous
            </Button>
            <div className="flex items-center gap-2 px-4">
              <span className="text-sm text-gray-600">Page {currentPage} of {Math.ceil(totalDocuments / itemsPerPage)}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setCurrentPage(prev => prev + 1)}
              disabled={currentPage >= Math.ceil(totalDocuments / itemsPerPage)}
            >
              Next
            </Button>
          </div>
        </div>
      )}

      <ConfirmDialog
        open={confirmDialog.open}
        onOpenChange={(open) => setConfirmDialog({ ...confirmDialog, open })}
        title={confirmDialog.title}
        description={confirmDialog.description}
        onConfirm={confirmDialog.onConfirm}
      />
    </div>
  )
}
