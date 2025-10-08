import { useState, useEffect } from 'react'
import axios from '../lib/axios'
import { CheckCircle2, Clock, XCircle, Send, FileText, DollarSign, Package } from 'lucide-react'

export default function Quotes() {
  const [quotes, setQuotes] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedQuote, setSelectedQuote] = useState(null)

  useEffect(() => {
    fetchQuotes()
  }, [])

  const fetchQuotes = async () => {
    try {
      setLoading(true)
      const response = await axios.get('/api/enquiries/quotes')
      setQuotes(response.data)
      setError(null)
    } catch (err) {
      console.error('Error fetching quotes:', err)
      setError('Failed to load quotes')
    } finally {
      setLoading(false)
    }
  }

  const getStatusBadge = (status) => {
    const statusConfig = {
      pending_admin: {
        label: 'Pending Review',
        icon: Clock,
        className: 'bg-yellow-100 text-yellow-800 border-yellow-200'
      },
      approved: {
        label: 'Approved',
        icon: CheckCircle2,
        className: 'bg-green-100 text-green-800 border-green-200'
      },
      rejected: {
        label: 'Rejected',
        icon: XCircle,
        className: 'bg-red-100 text-red-800 border-red-200'
      },
      sent_to_customer: {
        label: 'Sent to You',
        icon: Send,
        className: 'bg-blue-100 text-blue-800 border-blue-200'
      }
    }

    const config = statusConfig[status] || statusConfig.pending_admin
    const Icon = config.icon

    return (
      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium border ${config.className}`}>
        <Icon className="w-4 h-4" />
        {config.label}
      </span>
    )
  }

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('en-SG', {
      style: 'currency',
      currency: 'SGD'
    }).format(amount)
  }

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-SG', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading your quotes...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-8">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 text-red-800">
          {error}
        </div>
      </div>
    )
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">My Quotes</h1>
        <p className="text-gray-600">View all your quotations and their status</p>
      </div>

      {quotes.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <FileText className="w-16 h-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-gray-900 mb-2">No quotes yet</h3>
          <p className="text-gray-600 mb-6">Start a conversation to get your first quote</p>
          <a
            href="/enquiries"
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Start New Enquiry
          </a>
        </div>
      ) : (
        <div className="grid gap-6">
          {quotes.map((quote) => (
            <div
              key={quote.id}
              className="bg-white rounded-lg border border-gray-200 hover:border-blue-300 transition-all hover:shadow-md cursor-pointer"
              onClick={() => setSelectedQuote(selectedQuote?.id === quote.id ? null : quote)}
            >
              {/* Quote Header */}
              <div className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <Package className="w-5 h-5 text-gray-400" />
                      <h3 className="text-lg font-semibold text-gray-900">
                        {quote.item_name}
                      </h3>
                    </div>
                    <p className="text-sm text-gray-500">
                      Quote #{quote.id} • Created {formatDate(quote.created_at)}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    {getStatusBadge(quote.status)}
                    <div className="text-right">
                      <div className="text-2xl font-bold text-gray-900">
                        {formatCurrency(quote.total_price)}
                      </div>
                      <div className="text-xs text-gray-500">Total Price</div>
                    </div>
                  </div>
                </div>

                {/* Quick Info */}
                <div className="grid grid-cols-3 gap-4 pt-4 border-t border-gray-100">
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Quantity</div>
                    <div className="font-medium text-gray-900">
                      {quote.quantity} {quote.unit}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Base Price</div>
                    <div className="font-medium text-gray-900">
                      {formatCurrency(quote.base_price)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500 mb-1">Last Updated</div>
                    <div className="font-medium text-gray-900">
                      {formatDate(quote.updated_at)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Expanded Details */}
              {selectedQuote?.id === quote.id && (
                <div className="border-t border-gray-200 bg-gray-50 p-6">
                  {/* Adjustments */}
                  {quote.adjustments && quote.adjustments.length > 0 && (
                    <div className="mb-6">
                      <h4 className="font-semibold text-gray-900 mb-3">Price Adjustments</h4>
                      <div className="space-y-2">
                        {quote.adjustments.map((adj, idx) => (
                          <div key={idx} className="flex justify-between items-center bg-white rounded px-4 py-2">
                            <span className="text-gray-700">{adj.description}</span>
                            <span className="font-medium text-gray-900">
                              {adj.type === 'percentage' ? `${adj.amount}%` : formatCurrency(adj.amount)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}

                  {/* Conditions */}
                  {quote.conditions && quote.conditions.length > 0 && (
                    <div className="mb-6">
                      <h4 className="font-semibold text-gray-900 mb-3">Terms & Conditions</h4>
                      <ul className="space-y-2">
                        {quote.conditions.map((condition, idx) => (
                          <li key={idx} className="flex items-start gap-2 text-gray-700">
                            <span className="text-blue-600 mt-1">•</span>
                            <span>{condition}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Admin Notes */}
                  {quote.admin_notes && (
                    <div className="mb-6">
                      <h4 className="font-semibold text-gray-900 mb-3">Admin Notes</h4>
                      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
                        <p className="text-gray-700">{quote.admin_notes}</p>
                      </div>
                    </div>
                  )}

                  {/* Review Info */}
                  {quote.reviewed_at && (
                    <div className="text-sm text-gray-500">
                      Reviewed on {formatDate(quote.reviewed_at)}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
