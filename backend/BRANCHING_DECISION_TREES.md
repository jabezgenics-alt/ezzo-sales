# Branching Decision Trees Guide

## ✅ System Upgraded!

Your decision tree system now supports **conditional branching** - where answers determine which questions come next!

---

## 📋 How It Works

### Linear Flow (Old Way - Still Supported)
Questions asked in order, one after another:
```
Q1 → Q2 → Q3 → Q4 → Done
```

### Branching Flow (New Way)
Different answers lead to different questions:
```
Q1: Court type?
├─ Basketball → Q2a: Full/Half? → Q3a: 3-point line?
├─ Pickleball → Q2b: Singles/Doubles? → Q3b: Indoor/Outdoor?
└─ Tennis → Q2c: Clay/Hard? → Done
```

---

## 🔧 JSON Structure

### Required Fields for Branching

```json
{
  "tree_config": {
    "start_question": "first_question_id",  // NEW: Which question to start with
    "questions": [
      {
        "id": "first_question_id",
        "question": "Your question text?",
        "type": "choice",
        "choices": ["Option A", "Option B"],
        "required": true,
        "next": {                          // NEW: Defines branching
          "Option A": "question_for_a",   // If answer is "Option A", go to question_for_a
          "Option B": "question_for_b"    // If answer is "Option B", go to question_for_b
        }
      },
      {
        "id": "question_for_a",
        "question": "Follow-up for Option A?",
        "type": "text",
        "required": true
        // No "next" field means this is the end of this branch
      },
      {
        "id": "question_for_b",
        "question": "Follow-up for Option B?",
        "type": "boolean",
        "required": true,
        "next": {
          "true": "if_yes_question",
          "false": "if_no_question"
        }
      }
    ]
  }
}
```

---

## 📝 Complete Example: Court Markings Service

See `example_branching_tree.json` for a full working example with:
- Basketball (full/half court branching)
- Pickleball (singles/doubles branching)
- Tennis (clay/hard court)

---

## 🎯 Key Rules

### 1. **Question IDs Must Be Unique**
```json
"id": "court_type"  // Each question needs a unique ID
```

### 2. **`next` Field Format**
```json
"next": {
  "answer_value": "next_question_id"
}
```

### 3. **Answer Matching**
- For **choice** questions: Use exact choice text
  ```json
  "choices": ["Basketball", "Tennis"],
  "next": {
    "Basketball": "basketball_questions",
    "Tennis": "tennis_questions"
  }
  ```

- For **boolean** questions: Use "true" or "false" as strings
  ```json
  "next": {
    "true": "if_yes_question",
    "false": "if_no_question"
  }
  ```

- For **text/number** questions: Use "default" for any answer
  ```json
  "next": {
    "default": "next_question_after_text"
  }
  ```

### 4. **End of Branch**
If a question has no `next` field, it's the end of that branch.

### 5. **Start Question**
Set `start_question` to the ID of your first question. If not set, uses the first question in the array.

---

## 🔄 Backward Compatibility

**Old linear trees still work!** If you don't add `next` fields, questions are asked in order just like before.

Linear tree (no changes needed):
```json
{
  "questions": [
    {"id": "q1", "question": "First?", "type": "text", "required": true},
    {"id": "q2", "question": "Second?", "type": "text", "required": true},
    {"id": "q3", "question": "Third?", "type": "text", "required": true}
  ]
}
```
This will ask Q1 → Q2 → Q3 in order.

---

## 🚨 Common Mistakes

### ❌ Wrong: Misspelled answer in `next`
```json
{
  "choices": ["Basketball", "Tennis"],
  "next": {
    "Basketbal": "basketball_q"  // Typo! Won't match
  }
}
```

### ✅ Right: Exact match
```json
{
  "choices": ["Basketball", "Tennis"],
  "next": {
    "Basketball": "basketball_q"  // Exact match
  }
}
```

### ❌ Wrong: Referencing non-existent question
```json
"next": {
  "Basketball": "basketball_size"  // This question ID doesn't exist!
}
```

### ✅ Right: Valid question ID
```json
"next": {
  "Basketball": "basketball_size"  // This question exists in the questions array
}
```

---

## 📤 Adding to System

1. Go to: `http://localhost:8000/admin/decision-trees`
2. Click "Create New Decision Tree"
3. Paste your JSON
4. Save

The AI will automatically follow the branching logic!

---

## 🧪 Testing Your Tree

1. Create the tree in the admin panel
2. Start a customer chat
3. Say something like "I need court markings"
4. The AI will ask questions following your branch logic

---

## 💡 Tips

- Draw your tree on paper first
- Keep branches simple (max 3-4 levels deep)
- Always have a final question that collects site address or contact info
- Test each branch path separately

---

## Example Flow in Action

Customer says: **"I need basketball court markings"**

```
AI: What type of court do you need markings for?
    [Basketball] [Pickleball] [Tennis]

Customer: Basketball

AI: Do you need a full court or half court?
    [Full] [Half]

Customer: Full

AI: Do you need a 3-point line?
    [Yes] [No]

Customer: Yes

AI: What is the site address for the work?

Customer: 123 Main St

✅ All questions answered → Generate quote
```

---

Need help? Check `example_branching_tree.json` for a complete working example!
