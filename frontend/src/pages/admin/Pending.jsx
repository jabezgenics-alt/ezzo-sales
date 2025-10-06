import { useState, useEffect } from 'react';
import { Button } from '../../components/ui/button';
import { ConfirmDialog } from '../../components/ui/confirm-dialog';
import { useToast } from '../../components/ui/toast';
import { Trash2, Loader2 } from 'lucide-react';
import api from '@/lib/axios';

export default function AdminPending() {
  const { toast } = useToast();
  const [quotes, setQuotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedQuotes, setSelectedQuotes] = useState([]);
  const [deletingQuotes, setDeletingQuotes] = useState([]);
  const [batchDeleting, setBatchDeleting] = useState(false);
  const [confirmDialog, setConfirmDialog] = useState({ open: false, title: '', description: '', onConfirm: () => {} });

  useEffect(() => {
    fetchPendingQuotes();
  }, []);

  const fetchPendingQuotes = async () => {
    try {
      setLoading(true);
      const response = await api.get('/admin/quotes/pending');
      setQuotes(response.data);
    } catch (err) {
      console.error('Error fetching pending quotes:', err);
      setError('Failed to load pending quotes');
    } finally {
      setLoading(false);
    }
  };

  const handleApprove = async (quoteId) => {
    try {
      await api.post(`/admin/quotes/${quoteId}/approve`, {
        admin_notes: 'Approved'
      });
      await fetchPendingQuotes();
      toast({ title: 'Success', description: 'Quote approved successfully', variant: 'success' });
    } catch (err) {
      console.error('Error approving quote:', err);
      toast({ title: 'Error', description: 'Failed to approve quote', variant: 'error' });
    }
  };

  const handleReject = async (quoteId, reason) => {
    try {
      await api.post(`/admin/quotes/${quoteId}/reject`, {
        reason: reason,
        admin_notes: reason
      });
      await fetchPendingQuotes();
      toast({ title: 'Success', description: 'Quote rejected', variant: 'success' });
    } catch (err) {
      console.error('Error rejecting quote:', err);
      toast({ title: 'Error', description: 'Failed to reject quote', variant: 'error' });
    }
  };

  const deleteQuote = async (quoteId) => {
    try {
      setDeletingQuotes(prev => [...prev, quoteId]);
      await api.delete(`/admin/quotes/${quoteId}`);
      setQuotes(quotes.filter(q => q.id !== quoteId));
      toast({ title: 'Success', description: 'Quote deleted successfully', variant: 'success' });
    } catch (err) {
      console.error('Error deleting quote:', err);
      toast({ title: 'Error', description: 'Failed to delete quote', variant: 'error' });
    } finally {
      setDeletingQuotes(prev => prev.filter(id => id !== quoteId));
    }
  };

  const batchDeleteQuotes = async () => {
    try {
      setBatchDeleting(true);
      await Promise.all(selectedQuotes.map(id => api.delete(`/admin/quotes/${id}`)));
      setQuotes(quotes.filter(q => !selectedQuotes.includes(q.id)));
      setSelectedQuotes([]);
      toast({ title: 'Success', description: `${selectedQuotes.length} quotes deleted successfully`, variant: 'success' });
    } catch (err) {
      console.error('Error deleting quotes:', err);
      toast({ title: 'Error', description: 'Failed to delete some quotes', variant: 'error' });
    } finally {
      setBatchDeleting(false);
    }
  };

  const toggleSelectQuote = (quoteId) => {
    setSelectedQuotes(prev => 
      prev.includes(quoteId) ? prev.filter(id => id !== quoteId) : [...prev, quoteId]
    );
  };

  const toggleSelectAll = () => {
    if (selectedQuotes.length === quotes.length) {
      setSelectedQuotes([]);
    } else {
      setSelectedQuotes(quotes.map(q => q.id));
    }
  };

  return (
    <div className="p-8">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold mb-2">Pending Quotes</h1>
          <p className="text-gray-600">Review and approve customer quotes</p>
        </div>
        <div className="flex items-center gap-3">
          {selectedQuotes.length > 0 && (
            <>
              <Button
                variant="outline"
                size="sm"
                onClick={toggleSelectAll}
              >
                {selectedQuotes.length === quotes.length ? 'Deselect All' : 'Select All'}
              </Button>
              <Button
                variant="destructive"
                size="sm"
                disabled={batchDeleting}
                onClick={() => setConfirmDialog({
                  open: true,
                  title: 'Delete Quotes',
                  description: `Are you sure you want to delete ${selectedQuotes.length} quote(s)? This action cannot be undone.`,
                  onConfirm: batchDeleteQuotes
                })}
              >
                {batchDeleting ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  <>
                    <Trash2 className="h-4 w-4 mr-2" />
                    Delete {selectedQuotes.length} Selected
                  </>
                )}
              </Button>
            </>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <p className="text-red-700">{error}</p>
        </div>
      )}

      {loading ? (
        <p className="text-gray-500">Loading quotes...</p>
      ) : quotes.length === 0 ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-8 text-center">
          <p className="text-gray-600">No pending quotes to review</p>
        </div>
      ) : (
        <div className="space-y-4">
          {quotes.map((quote) => (
            <div key={quote.id} className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
              <div className="flex items-start gap-4">
                <input
                  type="checkbox"
                  checked={selectedQuotes.includes(quote.id)}
                  onChange={() => toggleSelectQuote(quote.id)}
                  className="mt-1 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <div className="flex-1">
                  <div className="flex justify-between items-start mb-4">
                    <div>
                      <h3 className="text-xl font-bold text-gray-900">Quote #{quote.id}</h3>
                      <p className="text-sm text-gray-500">
                        Created: {new Date(quote.created_at).toLocaleString()}
                      </p>
                    </div>
                    <span className="px-3 py-1 bg-yellow-100 text-yellow-800 rounded-full text-sm font-medium">
                      Pending Review
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-4 mb-4">
                    <div>
                      <p className="text-sm text-gray-600">Item</p>
                      <p className="font-semibold">{quote.item_name}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-600">Quantity</p>
                      <p className="font-semibold">{quote.quantity} {quote.unit}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-600">Base Price</p>
                      <p className="font-semibold">${quote.base_price.toFixed(2)} per {quote.unit}</p>
                    </div>
                    <div>
                      <p className="text-sm text-gray-600">Total Price</p>
                      <p className="font-semibold text-lg text-blue-700">${quote.total_price.toFixed(2)}</p>
                    </div>
                  </div>

                  {quote.conditions && quote.conditions.length > 0 && (
                    <div className="mb-4">
                      <p className="text-sm text-gray-600 mb-2">Conditions:</p>
                      <ul className="text-sm space-y-1 bg-gray-50 p-3 rounded">
                        {quote.conditions.map((cond, idx) => (
                          <li key={idx} className="text-gray-700">• {cond}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div className="flex gap-3 mt-4 pt-4 border-t">
                    <Button
                      onClick={() => setConfirmDialog({
                        open: true,
                        title: 'Approve Quote',
                        description: `Approve quote #${quote.id} for ${quote.item_name}?`,
                        onConfirm: () => handleApprove(quote.id),
                        variant: 'default',
                        confirmText: 'Approve'
                      })}
                      className="bg-green-600 hover:bg-green-700"
                    >
                      Approve
                    </Button>
                    <Button
                      variant="destructive"
                      onClick={() => {
                        const reason = prompt('Enter rejection reason:');
                        if (reason) {
                          handleReject(quote.id, reason);
                        }
                      }}
                    >
                      Reject
                    </Button>
                    <Button
                      variant="outline"
                      disabled={deletingQuotes.includes(quote.id)}
                      onClick={() => setConfirmDialog({
                        open: true,
                        title: 'Delete Quote',
                        description: `Are you sure you want to delete quote #${quote.id}? This action cannot be undone.`,
                        onConfirm: () => deleteQuote(quote.id)
                      })}
                      className="ml-auto"
                    >
                      {deletingQuotes.includes(quote.id) ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      <ConfirmDialog
        open={confirmDialog.open}
        onOpenChange={(open) => setConfirmDialog({ ...confirmDialog, open })}
        title={confirmDialog.title}
        description={confirmDialog.description}
        onConfirm={confirmDialog.onConfirm}
        confirmText={confirmDialog.confirmText}
        variant={confirmDialog.variant}
      />
    </div>
  );
}
