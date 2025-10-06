import { useState, useEffect } from 'react';
import api from '@/lib/axios';

export default function AdminPending() {
  const [quotes, setQuotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
    if (!confirm('Approve this quote?')) return;
    
    try {
      await api.post(`/admin/quotes/${quoteId}/approve`, {
        admin_notes: 'Approved'
      });
      await fetchPendingQuotes();
      alert('Quote approved successfully!');
    } catch (err) {
      console.error('Error approving quote:', err);
      alert('Failed to approve quote');
    }
  };

  const handleReject = async (quoteId) => {
    const reason = prompt('Enter rejection reason:');
    if (!reason) return;
    
    try {
      await api.post(`/admin/quotes/${quoteId}/reject`, {
        reason: reason,
        admin_notes: reason
      });
      await fetchPendingQuotes();
      alert('Quote rejected');
    } catch (err) {
      console.error('Error rejecting quote:', err);
      alert('Failed to reject quote');
    }
  };

  return (
    <div className="p-8">
      <h1 className="text-3xl font-bold mb-4">Pending Quotes</h1>
      <p className="text-gray-600 mb-6">Review and approve customer quotes</p>

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
                <button
                  onClick={() => handleApprove(quote.id)}
                  className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium transition-colors"
                >
                  Approve
                </button>
                <button
                  onClick={() => handleReject(quote.id)}
                  className="px-6 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium transition-colors"
                >
                  Reject
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
