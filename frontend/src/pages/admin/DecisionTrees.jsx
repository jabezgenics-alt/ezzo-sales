import { useState, useEffect } from 'react';
import api from '@/lib/axios';
import BranchingEditor from '@/components/BranchingEditor';

export default function AdminDecisionTrees() {
  const [trees, setTrees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [editingTree, setEditingTree] = useState(null);
  const [showCreateForm, setShowCreateForm] = useState(false);

  useEffect(() => {
    fetchTrees();
  }, []);

  const fetchTrees = async () => {
    try {
      setLoading(true);
      const response = await api.get('/decision-trees/');
      setTrees(response.data);
    } catch (err) {
      console.error('Error fetching trees:', err);
      setError('Failed to load decision trees');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTree = () => {
    setShowCreateForm(true);
    setEditingTree({
      service_name: '',
      display_name: '',
      description: '',
      tree_config: {
        questions: [],
        pricing_rules: {
          search_query: '',
          calculation_type: 'per_unit',
          components: []
        }
      }
    });
  };

  const handleSaveTree = async () => {
    try {
      if (editingTree.id) {
        // Update existing
        await api.put(`/decision-trees/${editingTree.id}`, {
          display_name: editingTree.display_name,
          description: editingTree.description,
          tree_config: editingTree.tree_config
        });
      } else {
        // Create new
        await api.post('/decision-trees/', editingTree);
      }
      setShowCreateForm(false);
      setEditingTree(null);
      await fetchTrees();
      alert('Decision tree saved successfully!');
    } catch (err) {
      console.error('Error saving tree:', err);
      alert(err.response?.data?.detail || 'Failed to save decision tree');
    }
  };

  const handleDeleteTree = async (treeId) => {
    if (!confirm('Delete this decision tree? This cannot be undone.')) return;
    
    try {
      await api.delete(`/decision-trees/${treeId}`);
      await fetchTrees();
    } catch (err) {
      console.error('Error deleting tree:', err);
      alert('Failed to delete tree');
    }
  };

  const addQuestion = () => {
    setEditingTree({
      ...editingTree,
      tree_config: {
        ...editingTree.tree_config,
        questions: [
          ...editingTree.tree_config.questions,
          { id: `q${Date.now()}`, question: '', type: 'text', required: true }
        ]
      }
    });
  };

  const updateQuestion = (index, field, value) => {
    const newQuestions = [...editingTree.tree_config.questions];
    newQuestions[index] = { ...newQuestions[index], [field]: value };
    setEditingTree({
      ...editingTree,
      tree_config: { ...editingTree.tree_config, questions: newQuestions }
    });
  };

  const removeQuestion = (index) => {
    const newQuestions = editingTree.tree_config.questions.filter((_, i) => i !== index);
    setEditingTree({
      ...editingTree,
      tree_config: { ...editingTree.tree_config, questions: newQuestions }
    });
  };

  return (
    <div className="min-h-screen p-8">
      <div className="max-w-6xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <div>
            <h1 className="text-3xl font-bold">Decision Trees</h1>
            <p className="text-gray-600 mt-2">
              Manage service flows - no coding required
            </p>
          </div>
          <button
            onClick={handleCreateTree}
            className="px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium transition-colors"
          >
            Create New Tree
          </button>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
            <p className="text-red-700">{error}</p>
          </div>
        )}

        {/* Tree Editor Modal */}
        {(showCreateForm || editingTree) && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-2 lg:p-4 overflow-y-auto">
            <div className="bg-white rounded-lg p-4 lg:p-6 max-w-7xl w-full max-h-[95vh] lg:max-h-[90vh] overflow-y-auto my-4">
              <h2 className="text-2xl font-bold mb-4">
                {editingTree?.id ? 'Edit Decision Tree' : 'Create Decision Tree'}
              </h2>

              {/* Basic Info */}
              <div className="space-y-4 mb-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Service Name (internal ID)
                  </label>
                  <input
                    type="text"
                    value={editingTree?.service_name || ''}
                    onChange={(e) => setEditingTree({...editingTree, service_name: e.target.value})}
                    disabled={editingTree?.id}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    placeholder="cat_ladder"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Display Name
                  </label>
                  <input
                    type="text"
                    value={editingTree?.display_name || ''}
                    onChange={(e) => setEditingTree({...editingTree, display_name: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    placeholder="Cat Ladder Installation"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Description
                  </label>
                  <textarea
                    value={editingTree?.description || ''}
                    onChange={(e) => setEditingTree({...editingTree, description: e.target.value})}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    rows="2"
                    placeholder="Service description..."
                  />
                </div>
              </div>

              {/* Visual Branching Editor */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-3">Decision Flow</h3>
                <BranchingEditor
                  treeConfig={editingTree?.tree_config || {}}
                  onChange={(newConfig) => {
                    setEditingTree({
                      ...editingTree,
                      tree_config: newConfig
                    });
                  }}
                />
              </div>

              {/* Pricing Rules */}
              <div className="mb-6">
                <h3 className="text-lg font-semibold mb-3">Pricing Rules</h3>
                <div className="space-y-3 border border-gray-300 rounded-lg p-4 bg-gray-50">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Search Query Template
                    </label>
                    <input
                      type="text"
                      value={editingTree?.tree_config?.pricing_rules?.search_query || ''}
                      onChange={(e) => setEditingTree({
                        ...editingTree,
                        tree_config: {
                          ...editingTree.tree_config,
                          pricing_rules: {
                            ...editingTree.tree_config.pricing_rules,
                            search_query: e.target.value
                          }
                        }
                      })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                      placeholder="cat ladder {material} {height}"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Use curly braces for variables: material, height, etc.
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Calculation Type
                    </label>
                    <select
                      value={editingTree?.tree_config?.pricing_rules?.calculation_type || 'per_unit'}
                      onChange={(e) => setEditingTree({
                        ...editingTree,
                        tree_config: {
                          ...editingTree.tree_config,
                          pricing_rules: {
                            ...editingTree.tree_config.pricing_rules,
                            calculation_type: e.target.value
                          }
                        }
                      })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg"
                    >
                      <option value="per_unit">Per Unit</option>
                      <option value="per_meter">Per Meter (height-based)</option>
                      <option value="per_sqft">Per Square Foot</option>
                      <option value="per_sqm">Per Square Meter</option>
                    </select>
                  </div>
                </div>
              </div>

              {/* Actions */}
              <div className="flex gap-3 justify-end pt-4 border-t">
                <button
                  onClick={() => {
                    setShowCreateForm(false);
                    setEditingTree(null);
                  }}
                  className="px-6 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded-lg font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveTree}
                  className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium"
                >
                  Save Tree
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Trees List */}
        {loading ? (
          <p className="text-gray-500">Loading decision trees...</p>
        ) : trees.length === 0 ? (
          <div className="bg-gray-50 border border-gray-200 rounded-lg p-12 text-center">
            <p className="text-gray-600 mb-4">No decision trees yet</p>
            <p className="text-sm text-gray-500">
              Decision trees guide customers through questions to build accurate quotes
            </p>
          </div>
        ) : (
          <div className="grid gap-4">
            {trees.map((tree) => (
              <div key={tree.id} className="bg-white border border-gray-200 rounded-lg p-6 shadow-sm">
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h3 className="text-xl font-bold">{tree.display_name}</h3>
                    <p className="text-sm text-gray-500 mt-1">{tree.description}</p>
                    <p className="text-xs text-gray-400 mt-1">Service ID: {tree.service_name}</p>
                  </div>
                  <div className="flex gap-2">
                    <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                      tree.is_active
                        ? 'bg-green-100 text-green-800'
                        : 'bg-gray-100 text-gray-800'
                    }`}>
                      {tree.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>
                </div>

                {/* Questions Preview */}
                <div className="mb-4">
                  <p className="text-sm font-medium text-gray-700 mb-2">
                    Questions ({tree.tree_config?.questions?.length || 0}):
                  </p>
                  <div className="bg-gray-50 rounded-lg p-3 space-y-1">
                    {tree.tree_config?.questions?.slice(0, 3).map((q, idx) => (
                      <div key={idx} className="text-sm text-gray-700">
                        {idx + 1}. {q.question} <span className="text-gray-500">({q.type})</span>
                      </div>
                    ))}
                    {tree.tree_config?.questions?.length > 3 && (
                      <p className="text-xs text-gray-500 mt-2">
                        ...and {tree.tree_config.questions.length - 3} more
                      </p>
                    )}
                  </div>
                </div>

                {/* Pricing Info */}
                <div className="mb-4">
                  <p className="text-sm font-medium text-gray-700 mb-2">Pricing:</p>
                  <div className="bg-blue-50 rounded-lg p-3 text-sm">
                    <p><strong>Type:</strong> {tree.tree_config?.pricing_rules?.calculation_type || 'N/A'}</p>
                    <p className="text-xs text-gray-600 mt-1">
                      <strong>Search:</strong> {tree.tree_config?.pricing_rules?.search_query || 'N/A'}
                    </p>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex gap-3 pt-4 border-t">
                  <button
                    onClick={() => {
                      setEditingTree(tree);
                      setShowCreateForm(true);
                    }}
                    className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-800 rounded-lg font-medium"
                  >
                    Edit
                  </button>
                  <button
                    onClick={() => handleDeleteTree(tree.id)}
                    className="px-4 py-2 bg-red-100 hover:bg-red-200 text-red-800 rounded-lg font-medium"
                  >
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

