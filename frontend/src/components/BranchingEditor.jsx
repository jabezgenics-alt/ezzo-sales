import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

export default function BranchingEditor({ treeConfig, onChange }) {
  const [questions, setQuestions] = useState(treeConfig?.questions || []);
  const [selectedQuestion, setSelectedQuestion] = useState(null);
  const [connectingFrom, setConnectingFrom] = useState(null);
  const [startQuestion, setStartQuestion] = useState(treeConfig?.start_question || null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [choicesInput, setChoicesInput] = useState('');

  useEffect(() => {
    // Update parent when questions change
    onChange({
      ...treeConfig,
      questions,
      start_question: startQuestion || (questions.length > 0 ? questions[0].id : null)
    });
  }, [questions, startQuestion]);

  useEffect(() => {
    if (!selectedQuestion || selectedQuestion.type !== 'choice') {
      setChoicesInput('');
      return;
    }

    setChoicesInput((selectedQuestion.choices || []).join(', '));
  }, [selectedQuestion?.id, selectedQuestion?.type]);

  const addQuestion = () => {
    const newQuestion = {
      id: `q_${Date.now()}`,
      question: 'New Question',
      type: 'text',
      required: true,
      choices: [],
      next: {}
    };
    setQuestions([...questions, newQuestion]);
    setSelectedQuestion(newQuestion);
  };

  const updateQuestion = (questionId, updates) => {
    setQuestions(questions.map(q => 
      q.id === questionId ? { ...q, ...updates } : q
    ));
    if (selectedQuestion?.id === questionId) {
      setSelectedQuestion({ ...selectedQuestion, ...updates });
    }
  };

  const deleteQuestion = (questionId) => {
    // Remove question and clean up references
    setQuestions(questions.filter(q => q.id !== questionId).map(q => {
      if (q.next) {
        const newNext = { ...q.next };
        Object.keys(newNext).forEach(key => {
          if (newNext[key] === questionId) {
            delete newNext[key];
          }
        });
        return { ...q, next: newNext };
      }
      return q;
    }));
    if (selectedQuestion?.id === questionId) {
      setSelectedQuestion(null);
    }
    if (startQuestion === questionId) {
      setStartQuestion(questions[0]?.id || null);
    }
  };

  const connectQuestions = (fromQuestionId, answer, toQuestionId) => {
    setQuestions(questions.map(q => {
      if (q.id === fromQuestionId) {
        return {
          ...q,
          next: {
            ...q.next,
            [answer]: toQuestionId
          }
        };
      }
      return q;
    }));
  };

  const disconnectAnswer = (fromQuestionId, answer) => {
    setQuestions(questions.map(q => {
      if (q.id === fromQuestionId) {
        const newNext = { ...q.next };
        delete newNext[answer];
        return { ...q, next: newNext };
      }
      return q;
    }));
  };

  const getQuestionById = (id) => questions.find(q => q.id === id);

  const getAnswerOptions = (question) => {
    if (question.type === 'choice') {
      return question.choices || [];
    }
    if (question.type === 'boolean') {
      return ['true', 'false'];
    }
    return ['default'];
  };

  return (
    <div className={`${isFullscreen ? 'fixed inset-0 z-50 bg-white p-4' : ''}`}>
      {/* Fullscreen Toggle */}
      <button
        onClick={() => setIsFullscreen(!isFullscreen)}
        className="absolute top-2 right-2 z-50 px-3 py-1 bg-gray-800 hover:bg-gray-700 text-white rounded-lg text-sm font-medium transition-colors"
      >
        {isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
      </button>

      <div className="flex flex-col lg:flex-row h-auto lg:h-[calc(100vh-200px)] gap-4">
      {/* Left Sidebar - Question List */}
      <div className="w-full lg:w-64 bg-white border border-gray-200 rounded-lg p-4 overflow-y-auto max-h-64 lg:max-h-none">
        <div className="flex justify-between items-center mb-4">
          <h3 className="font-semibold text-gray-900">Questions</h3>
          <button
            onClick={addQuestion}
            className="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded-lg transition-colors"
          >
            Add
          </button>
        </div>

        <div className="space-y-2">
          {questions.map((q) => (
            <motion.div
              key={q.id}
              layoutId={q.id}
              onClick={() => setSelectedQuestion(q)}
              className={`p-3 rounded-lg border-2 cursor-pointer transition-all ${
                selectedQuestion?.id === q.id
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 bg-white hover:border-gray-300'
              } ${startQuestion === q.id ? 'ring-2 ring-green-400' : ''}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-gray-900 truncate">
                    {q.question || 'Untitled'}
                  </p>
                  <p className="text-xs text-gray-500 mt-1">
                    {q.type} {q.required && '(required)'}
                  </p>
                </div>
                {startQuestion === q.id && (
                  <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded">
                    Start
                  </span>
                )}
              </div>
            </motion.div>
          ))}
        </div>

        {questions.length === 0 && (
          <div className="text-center py-8 text-gray-400 text-sm">
            No questions yet. Click Add to start.
          </div>
        )}
      </div>

      {/* Center - Visual Flow */}
      <div className="flex-1 bg-gray-50 border border-gray-200 rounded-lg p-4 lg:p-6 overflow-auto min-h-[500px] lg:min-h-0">
        {questions.length === 0 ? (
          <div className="flex items-center justify-center h-full text-gray-400">
            <div className="text-center">
              <p className="text-lg font-medium mb-2">No Questions Yet</p>
              <p className="text-sm">Add questions to start building your decision tree</p>
            </div>
          </div>
        ) : (
          <div className="relative min-h-full">
            <FlowCanvas
              questions={questions}
              startQuestion={startQuestion}
              selectedQuestion={selectedQuestion}
              onSelectQuestion={setSelectedQuestion}
              onConnect={connectQuestions}
              onDisconnect={disconnectAnswer}
              getQuestionById={getQuestionById}
            />
          </div>
        )}
      </div>

      {/* Right Sidebar - Question Properties */}
      <AnimatePresence mode="wait">
        {selectedQuestion && (
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 20 }}
            className="w-full lg:w-80 bg-white border border-gray-200 rounded-lg p-4 overflow-y-auto max-h-[600px] lg:max-h-none"
          >
            <div className="flex justify-between items-center mb-4">
              <h3 className="font-semibold text-gray-900">Properties</h3>
              <button
                onClick={() => setSelectedQuestion(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                ×
              </button>
            </div>

            <div className="space-y-4">
              {/* Question ID */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Question ID
                </label>
                <input
                  type="text"
                  value={selectedQuestion.id}
                  onChange={(e) => updateQuestion(selectedQuestion.id, { id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  placeholder="unique_id"
                />
              </div>

              {/* Question Text */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Question Text
                </label>
                <textarea
                  value={selectedQuestion.question}
                  onChange={(e) => updateQuestion(selectedQuestion.id, { question: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                  rows="3"
                  placeholder="What would you like to ask?"
                />
              </div>

              {/* Question Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Answer Type
                </label>
                <select
                  value={selectedQuestion.type}
                  onChange={(e) => updateQuestion(selectedQuestion.id, { type: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm"
                >
                  <option value="text">Text</option>
                  <option value="number">Number</option>
                  <option value="choice">Multiple Choice</option>
                  <option value="boolean">Yes/No</option>
                </select>
              </div>

              {/* Choices (for choice type) */}
              {selectedQuestion.type === 'choice' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Choices (comma separated)
                  </label>
                  <textarea
                    value={choicesInput}
                    onChange={(e) => {
                      const value = e.target.value;
                      setChoicesInput(value);
                      const parsedChoices = value
                        .split(',')
                        .map((choice) => choice.trim())
                        .filter(Boolean);

                      updateQuestion(selectedQuestion.id, {
                        choices: parsedChoices
                      });
                    }}
                    onKeyDown={(e) => {
                      // Explicitly allow space key
                      if (e.key === ' ' || e.code === 'Space') {
                        e.stopPropagation(); // Prevent any parent handlers
                      }
                    }}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm font-mono"
                    rows="3"
                    placeholder="Stainless Steel (SS304), Galvanized Mild Steel (HDG), Aluminum"
                    spellCheck={false}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    ✓ Separate each choice with a comma. Spaces within choices are fully supported.
                  </p>
                  <p className="text-xs text-blue-600 mt-1">
                    Example: "Stainless Steel (SS304), Galvanized Mild Steel (HDG), Aluminum"
                  </p>
                </div>
              )}

              {/* Required */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="required"
                  checked={selectedQuestion.required}
                  onChange={(e) => updateQuestion(selectedQuestion.id, { required: e.target.checked })}
                  className="rounded border-gray-300"
                />
                <label htmlFor="required" className="text-sm text-gray-700">
                  Required question
                </label>
              </div>

              {/* Set as Start */}
              <div>
                <button
                  onClick={() => setStartQuestion(selectedQuestion.id)}
                  className={`w-full px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    startQuestion === selectedQuestion.id
                      ? 'bg-green-100 text-green-800'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {startQuestion === selectedQuestion.id ? 'Start Question' : 'Set as Start'}
                </button>
              </div>

              {/* Delete */}
              <div className="pt-4 border-t">
                <button
                  onClick={() => {
                    if (confirm('Delete this question?')) {
                      deleteQuestion(selectedQuestion.id);
                    }
                  }}
                  className="w-full px-4 py-2 bg-red-50 hover:bg-red-100 text-red-700 rounded-lg text-sm font-medium transition-colors"
                >
                  Delete Question
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
      </div>
    </div>
  );
}

// Flow Canvas Component
function FlowCanvas({ questions, startQuestion, selectedQuestion, onSelectQuestion, onConnect, onDisconnect, getQuestionById }) {
  const [positions, setPositions] = useState({});
  const [connectMode, setConnectMode] = useState(null); // {questionId, answer}

  useEffect(() => {
    // Auto-layout questions in a tree structure
    if (questions.length > 0 && Object.keys(positions).length === 0) {
      const newPositions = {};
      const start = questions.find(q => q.id === startQuestion) || questions[0];
      
      // Improved layout - spread questions out more
      questions.forEach((q, i) => {
        newPositions[q.id] = {
          x: 100 + (i % 4) * 350,  // 4 columns, more spacing
          y: 100 + Math.floor(i / 4) * 250  // More vertical spacing
        };
      });
      
      setPositions(newPositions);
    }
  }, [questions, startQuestion]);

  const handleQuestionClick = (question, e) => {
    e.stopPropagation();
    if (connectMode) {
      // Connect mode active
      onConnect(connectMode.questionId, connectMode.answer, question.id);
      setConnectMode(null);
    } else {
      onSelectQuestion(question);
    }
  };

  const handleAnswerClick = (questionId, answer, e) => {
    e.stopPropagation();
    const question = getQuestionById(questionId);
    const currentTarget = question?.next?.[answer];
    
    if (currentTarget) {
      // Already connected - disconnect
      if (confirm(`Disconnect "${answer}" → "${getQuestionById(currentTarget)?.question}"?`)) {
        onDisconnect(questionId, answer);
      }
    } else {
      // Start connection
      setConnectMode({ questionId, answer });
    }
  };

  return (
    <div className="relative w-full min-h-full">
      {/* Connection Lines SVG */}
      <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 1 }}>
        {questions.map(q => {
          const fromPos = positions[q.id];
          if (!fromPos || !q.next) return null;

          return Object.entries(q.next).map(([answer, toId]) => {
            const toPos = positions[toId];
            if (!toPos) return null;

            const fromX = fromPos.x + 140;
            const fromY = fromPos.y + 60;
            const toX = toPos.x + 10;
            const toY = toPos.y + 60;

            return (
              <g key={`${q.id}-${answer}-${toId}`}>
                <line
                  x1={fromX}
                  y1={fromY}
                  x2={toX}
                  y2={toY}
                  stroke="#3b82f6"
                  strokeWidth="2"
                  markerEnd="url(#arrowhead)"
                />
                <text
                  x={(fromX + toX) / 2}
                  y={(fromY + toY) / 2 - 5}
                  fill="#6b7280"
                  fontSize="11"
                  fontWeight="500"
                  className="select-none"
                >
                  {answer}
                </text>
              </g>
            );
          });
        })}
        <defs>
          <marker
            id="arrowhead"
            markerWidth="10"
            markerHeight="10"
            refX="9"
            refY="3"
            orient="auto"
          >
            <polygon points="0 0, 10 3, 0 6" fill="#3b82f6" />
          </marker>
        </defs>
      </svg>

      {/* Question Nodes */}
      {questions.map(q => {
        const pos = positions[q.id];
        if (!pos) return null;

        return (
          <QuestionNode
            key={q.id}
            question={q}
            position={pos}
            isStart={startQuestion === q.id}
            isSelected={selectedQuestion?.id === q.id}
            onClick={(e) => handleQuestionClick(q, e)}
            onAnswerClick={handleAnswerClick}
            getQuestionById={getQuestionById}
          />
        );
      })}

      {/* Connect Mode Overlay */}
      {connectMode && (
        <div className="absolute top-4 left-1/2 transform -translate-x-1/2 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg z-50">
          <p className="text-sm font-medium">
            Click a question to connect "{connectMode.answer}"
          </p>
          <button
            onClick={() => setConnectMode(null)}
            className="ml-3 text-blue-200 hover:text-white"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  );
}

// Question Node Component
function QuestionNode({ question, position, isStart, isSelected, onClick, onAnswerClick, getQuestionById }) {
  const answerOptions = question.type === 'choice'
    ? question.choices || []
    : question.type === 'boolean'
    ? ['true', 'false']
    : ['default'];

  return (
    <motion.div
      drag
      dragMomentum={false}
      style={{ x: position.x, y: position.y }}
      className={`absolute w-64 lg:w-72 bg-white rounded-lg shadow-lg border-2 cursor-move ${
        isSelected ? 'border-blue-500 ring-2 ring-blue-200' : 'border-gray-200'
      } ${isStart ? 'ring-2 ring-green-400' : ''}`}
      style={{ zIndex: isSelected ? 10 : 5 }}
      onClick={onClick}
    >
      {/* Header */}
      <div className={`px-4 py-3 border-b ${isStart ? 'bg-green-50' : 'bg-gray-50'}`}>
        <div className="flex items-start justify-between gap-2">
          <div className="flex-1 min-w-0">
            <p className="text-sm font-semibold text-gray-900 break-words">
              {question.question || 'Untitled Question'}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {question.type} • {question.id}
            </p>
          </div>
          {isStart && (
            <span className="text-xs bg-green-500 text-white px-2 py-1 rounded font-medium">
              START
            </span>
          )}
        </div>
      </div>

      {/* Answers/Connections */}
      <div className="p-3 space-y-2">
        {answerOptions.map(answer => {
          const connectedTo = question.next?.[answer];
          const targetQuestion = connectedTo ? getQuestionById(connectedTo) : null;

          return (
            <button
              key={answer}
              onClick={(e) => {
                e.stopPropagation();
                onAnswerClick(question.id, answer, e);
              }}
              className={`w-full px-3 py-2 text-left rounded text-sm transition-colors ${
                connectedTo
                  ? 'bg-blue-50 border-2 border-blue-300 hover:border-blue-400'
                  : 'bg-gray-50 border-2 border-dashed border-gray-300 hover:border-gray-400'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="font-medium text-gray-700">{answer}</span>
                {connectedTo ? (
                  <span className="text-xs text-blue-600 truncate max-w-[120px]">
                    → {targetQuestion?.question || connectedTo}
                  </span>
                ) : (
                  <span className="text-xs text-gray-400">Click to connect</span>
                )}
              </div>
            </button>
          );
        })}
      </div>
    </motion.div>
  );
}
