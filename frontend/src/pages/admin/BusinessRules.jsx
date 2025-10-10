import { useState, useEffect } from 'react';
import api from '@/lib/axios';
import { Shield, Plus, Edit, Trash2, Power, PowerOff } from 'lucide-react';

export default function AdminBusinessRules() {
  const [rules, setRules] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingRule, setEditingRule] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);

  useEffect(() => {
    fetchRules();
  }, []);

  const fetchRules = async () => {
    try {
      setLoading(true);
      const response = await api.get('/business-rules/');
      setRules(response.data);
    } catch (err) {
      console.error('Error fetching rules:', err);
      setError('Failed to load business rules');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRule = () => {
    setShowCreateForm(true);
    setEditingRule({
      rule_name: '',
      service_type: '',
      region: '',
      rule_config: {},
      is_active: true,
      priority: 100,
      source_reference: '',
      description: ''
    });
  };

  const handleSaveRule = async () => {
    try {
      if (editingRule.id) {
        // Update existing
        await api.put(`/business-rules/${editingRule.id}`, editingRule);
      } else {
        // Create new
        await api.post('/business-rules/', editingRule);
      }
      setShowCreateForm(false);
      setEditingRule(null);
      await fetchRules();
      alert('Business rule saved successfully!');
    } catch (err) {
      console.error('Error saving rule:', err);
      alert(err.response?.data?.detail || 'Failed to save business rule');
    }
  };

  const handleToggleRule = async (ruleId) => {
    try {
      await api.patch(`/business-rules/${ruleId}/toggle`);
      await fetchRules();
    } catch (err) {
      console.error('Error toggling rule:', err);
      alert('Failed to toggle rule');
    }
  };

  const handleDeleteRule = async (ruleId) => {
    if (!confirm('Delete this business rule? This cannot be undone.')) return;
    
    try {
      await api.delete(`/business-rules/${ruleId}`);
      await fetchRules();
    } catch (err) {
      console.error('Error deleting rule:', err);
      alert('Failed to delete rule');
    }
  };

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3">
              <Shield className="h-8 w-8" />
              Business Rules
            </h1>
            <p className="text-gray-600 mt-2">
              Manage regulatory requirements and business logic
            </p>
          </div>
          <button
            onClick={handleCreateRule}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors flex items-center gap-2"
          >
            <Plus className="h-5 w-5" />
            Create New Rule
          </button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Rule Editor Modal */}
        {(showCreateForm || editingRule) && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4 overflow-y-auto">
            <div className="bg-white rounded-lg p-6 max-w-4xl w-full max-h-[90vh] overflow-y-auto my-4">
              <h2 className="text-2xl font-bold mb-4">
                {editingRule?.id ? 'Edit Business Rule' : 'Create Business Rule'}
              </h2>

              {/* Basic Info */}
              <div className="space-y-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Rule Name
                  </label>
                  <input
                    type="text"
                    value={editingRule?.rule_name || ''}
                    onChange={(e) => setEditingRule({...editingRule, rule_name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    placeholder="Singapore Ladder Safety Standards"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Service Type
                    </label>
                    <input
                      type="text"
                      value={editingRule?.service_type || ''}
                      onChange={(e) => setEditingRule({...editingRule, service_type: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                      placeholder="cat_ladder_installation (optional)"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Region
                    </label>
                    <input
                      type="text"
                      value={editingRule?.region || ''}
                      onChange={(e) => setEditingRule({...editingRule, region: e.target.value})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                      placeholder="SGP (optional)"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description
                  </label>
                  <textarea
                    value={editingRule?.description || ''}
                    onChange={(e) => setEditingRule({...editingRule, description: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    rows="2"
                    placeholder="Rule description..."
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Source Reference
                  </label>
                  <input
                    type="text"
                    value={editingRule?.source_reference || ''}
                    onChange={(e) => setEditingRule({...editingRule, source_reference: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    placeholder="WSH Regulations, ISO 14122-4:2016"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Priority (lower = higher priority)
                    </label>
                    <input
                      type="number"
                      value={editingRule?.priority || 100}
                      onChange={(e) => setEditingRule({...editingRule, priority: parseInt(e.target.value)})}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    />
                  </div>

                  <div className="flex items-end">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={editingRule?.is_active || false}
                        onChange={(e) => setEditingRule({...editingRule, is_active: e.target.checked})}
                        className="rounded border-gray-300"
                      />
                      <span className="text-sm font-medium text-gray-700">Active</span>
                    </label>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Rule Configuration (JSON)
                  </label>
                  <textarea
                    value={JSON.stringify(editingRule?.rule_config || {}, null, 2)}
                    onChange={(e) => {
                      try {
                        const parsed = JSON.parse(e.target.value);
                        setEditingRule({...editingRule, rule_config: parsed});
                      } catch (err) {
                        // Invalid JSON, let user continue typing
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm"
                    rows="12"
                    placeholder='{"rule_type": "ladder_safety_singapore", ...}'
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    JSON configuration defining rule logic and parameters
                  </p>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-3 justify-end pt-4 border-t">
                <button
                  onClick={() => {
                    setShowCreateForm(false);
                    setEditingRule(null);
                  }}
                  className="px-6 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded-lg font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveRule}
                  className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium"
                >
                  Save Rule
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Rules List */}
        {loading ? (
          <p className="text-gray-500">Loading business rules...</p>
        ) : rules.length === 0 ? (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-12 text-center">
            <Shield className="h-16 w-16 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600 mb-4">No business rules yet</p>
            <p className="text-sm text-gray-500">
              Business rules automatically enforce regulatory requirements and standards
            </p>
          </div>
        ) : (
          <div className="grid gap-4">
            {rules.map((rule) => (
              <div key={rule.id} className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
                <div className="flex justify-between items-start mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-xl font-bold">{rule.rule_name}</h3>
                      <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                        rule.is_active
                          ? 'bg-green-100 text-green-800'
                          : 'bg-gray-100 text-gray-800'
                      }`}>
                        {rule.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                    <p className="text-sm text-gray-600 mb-2">{rule.description}</p>
                    <div className="flex gap-4 text-xs text-gray-500">
                      {rule.service_type && <span>Service: {rule.service_type}</span>}
                      {rule.region && <span>Region: {rule.region}</span>}
                      <span>Priority: {rule.priority}</span>
                    </div>
                  </div>
                </div>

                {/* Rule Config Preview */}
                <div className="mb-4 bg-gray-50 rounded-lg p-3">
                  <p className="text-xs font-medium text-gray-700 mb-2">Configuration:</p>
                  <pre className="text-xs text-gray-600 overflow-x-auto">
                    {JSON.stringify(rule.rule_config, null, 2)}
                  </pre>
                </div>

                {/* Source Reference */}
                {rule.source_reference && (
                  <div className="mb-4 text-sm">
                    <span className="font-medium text-gray-700">Source: </span>
                    <span className="text-gray-600">{rule.source_reference}</span>
                  </div>
                )}

                {/* Actions */}
                <div className="flex gap-3 pt-4 border-t">
                  <button
                    onClick={() => handleToggleRule(rule.id)}
                    className={`px-4 py-2 rounded-lg font-medium flex items-center gap-2 ${
                      rule.is_active
                        ? 'bg-yellow-100 hover:bg-yellow-200 text-yellow-800'
                        : 'bg-green-100 hover:bg-green-200 text-green-800'
                    }`}
                  >
                    {rule.is_active ? (
                      <>
                        <PowerOff className="h-4 w-4" />
                        Deactivate
                      </>
                    ) : (
                      <>
                        <Power className="h-4 w-4" />
                        Activate
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => {
                      setEditingRule(rule);
                      setShowCreateForm(true);
                    }}
                    className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded-lg font-medium flex items-center gap-2"
                  >
                    <Edit className="h-4 w-4" />
                    Edit
                  </button>
                  <button
                    onClick={() => handleDeleteRule(rule.id)}
                    className="px-4 py-2 bg-red-100 hover:bg-red-200 text-red-800 rounded-lg font-medium flex items-center gap-2"
                  >
                    <Trash2 className="h-4 w-4" />
                    Delete
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

