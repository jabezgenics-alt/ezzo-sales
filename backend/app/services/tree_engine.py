from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from app.models import DecisionTree, Enquiry
from app.schemas import AIResponse, AIQuestion


class DecisionTreeEngine:
    """Execute decision trees - follow the flow, no AI freestyle"""
    
    def __init__(self):
        pass
    
    def match_service(self, db: Session, customer_message: str) -> Optional[DecisionTree]:
        """Use AI to classify which service the customer wants"""
        from openai import OpenAI
        from app.config import settings
        import json
        
        # Get all active trees
        trees = db.query(DecisionTree).filter(DecisionTree.is_active == True).all()
        
        if not trees:
            return None
        
        # Build service options
        service_options = {tree.service_name: tree.display_name for tree in trees}
        
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are a service classifier. Match the customer's request to ONE of these services:

{json.dumps(service_options, indent=2)}

Return JSON with: {{"service": "service_name"}} using the EXACT service_name key from the list above.

Matching Rules:
- "cat ladder", "cat-ladder", "catladder", "ladder installation" → {{"service": "cat_ladder_installation"}}
- "parquet", "parquet floor", "parquet sanding", "parquet varnishing" → {{"service": "parquet_sanding_varnishing"}}
- "court", "basketball court", "tennis court", "pickleball court", "court marking" → {{"service": "court_markings"}}
- "hello", "hi", general questions → {{"service": null}}

Be flexible with spelling, punctuation, and partial matches. Match based on INTENT, not exact words."""
                    },
                    {
                        "role": "user",
                        "content": customer_message
                    }
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            service_name = result.get('service')
            
            if service_name:
                return db.query(DecisionTree).filter(
                    DecisionTree.service_name == service_name,
                    DecisionTree.is_active == True
                ).first()
            
        except Exception as e:
            print(f"Error matching service: {str(e)}")
        
        return None
    
    def get_next_question(
        self,
        tree: DecisionTree,
        collected_data: Dict[str, Any]
    ) -> Optional[AIQuestion]:
        """Get the next unanswered question from the tree (supports branching)"""
        
        questions = tree.tree_config.get('questions', [])
        
        # Build question lookup dict
        question_dict = {q.get('id'): q for q in questions}
        
        # Determine which question to ask next
        next_question_id = self._find_next_question_id(questions, question_dict, collected_data, tree.tree_config)
        
        if next_question_id:
            q = question_dict.get(next_question_id)
            if q:
                return AIQuestion(
                    key=q.get('id'),
                    question=q.get('question'),
                    type=q.get('type'),
                    choices=q.get('choices'),
                    required=q.get('required', True)
                )
        
        return None
    
    def _find_next_question_id(
        self,
        questions: List[Dict],
        question_dict: Dict[str, Dict],
        collected_data: Dict[str, Any],
        tree_config: Dict[str, Any]
    ) -> Optional[str]:
        """Find the next question ID based on branching logic or linear flow"""
        
        # If no data collected yet, start with start_question or first question
        if not collected_data:
            start_id = tree_config.get('start_question')
            if start_id:
                return start_id
            return questions[0].get('id') if questions else None
        
        # Build the path of questions that should be asked based on branching logic
        question_path = self._build_question_path(questions, question_dict, collected_data, tree_config)
        
        # Find first unanswered question in the path
        for q_id in question_path:
            if q_id not in collected_data or collected_data[q_id] is None:
                return q_id
        
        return None
    
    def _build_question_path(
        self,
        questions: List[Dict],
        question_dict: Dict[str, Dict],
        collected_data: Dict[str, Any],
        tree_config: Dict[str, Any]
    ) -> List[str]:
        """Build the path of questions to ask based on answers given"""
        
        path = []
        
        # Start with start_question or first question
        start_id = tree_config.get('start_question')
        if not start_id and questions:
            start_id = questions[0].get('id')
        
        if not start_id:
            return path
        
        current_id = start_id
        path.append(current_id)
        
        # Check if this is a linear tree (all next fields are null)
        is_linear = all(q.get('next') is None for q in questions)
        
        if is_linear:
            # For linear trees, include all questions in sequence
            for question in questions:
                q_id = question.get('id')
                if q_id and q_id != start_id:
                    path.append(q_id)
            return path
        
        # Follow the branch based on answers (for branching trees)
        while current_id:
            current_q = question_dict.get(current_id)
            if not current_q:
                break
            
            # Check if this question has been answered
            answer = collected_data.get(current_id)
            if answer is None:
                # Not answered yet, stop here
                break
            
            # Check if there's a next question based on the answer
            next_mapping = current_q.get('next')
            if next_mapping and isinstance(next_mapping, dict):
                # Convert answer to string for lookup
                answer_str = str(answer)
                next_id = next_mapping.get(answer_str)
                
                # Also check for a 'default' path for text/number inputs
                if not next_id and 'default' in next_mapping:
                    next_id = next_mapping.get('default')
                
                if next_id and next_id in question_dict:
                    path.append(next_id)
                    current_id = next_id
                else:
                    # No valid next question
                    break
            else:
                # No branching, we're done
                break
        
        return path
    
    def is_complete(
        self,
        tree: DecisionTree,
        collected_data: Dict[str, Any]
    ) -> bool:
        """Check if all required questions in the current branch path are answered"""
        
        questions = tree.tree_config.get('questions', [])
        question_dict = {q.get('id'): q for q in questions}
        tree_config = tree.tree_config
        
        # Build the path of questions based on current answers
        question_path = self._build_question_path(questions, question_dict, collected_data, tree_config)
        
        # Check if all questions in the path are answered
        for q_id in question_path:
            if q_id not in collected_data or collected_data[q_id] is None:
                return False
        
        # Also check if there's a next question - if yes, we're not complete
        next_q = self.get_next_question(tree, collected_data)
        if next_q:
            return False
        
        return True
    
    def parse_answer(self, answer_text: str, question_type: str, choices: List[str] = None) -> Any:
        """Parse customer's natural language answer"""
        from openai import OpenAI
        from app.config import settings
        import json
        
        print(f"Parsing answer: '{answer_text}' | Type: {question_type} | Choices: {choices}")
        
        try:
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            if question_type == 'number':
                prompt = f"Extract the numeric value from: '{answer_text}'. Return JSON: {{\"value\": number}}"
            elif question_type == 'boolean':
                prompt = f"Is this a yes or no? '{answer_text}'. Return JSON: {{\"value\": true/false}}"
            elif question_type == 'choice' and choices:
                # For choice questions, match to one of the provided choices
                prompt = f"""The user said: '{answer_text}'
                
Which of these choices does it match: {json.dumps(choices)}

Be flexible with casual language, slang, and typos. For example:
- "basketbal mate" or "baskaball" → "Basketball"
- "ye full" or "full idol" or "full brotha" → "Full"
- "nah" or "nah man" → for yes/no, interpret as no

Return JSON: {{\"value\": "exact_choice"}} where exact_choice is one of the provided options.
If completely unclear, return {{\"value\": null}}"""
            elif question_type == 'text':
                # For text questions, just clean and return the text
                prompt = f"Clean up this text (fix obvious typos, trim whitespace): '{answer_text}'. Return JSON: {{\"value\": \"cleaned_text\"}}"
            else:
                prompt = f"Extract the answer from: '{answer_text}'. Return JSON: {{\"value\": \"text\"}}"
            
            response = client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a precise answer parser."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0,
                response_format={"type": "json_object"},
                max_tokens=100
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get('value')
            
        except Exception as e:
            print(f"Error parsing answer: {str(e)}")
            # Fallback to simple parsing
            if question_type == 'number':
                import re
                match = re.search(r'(\d+(?:\.\d+)?)', answer_text)
                return float(match.group(1)) if match else None
            elif question_type == 'boolean':
                return 'yes' in answer_text.lower() or 'y' == answer_text.lower().strip()
            elif question_type == 'choice' and choices:
                # Try simple case-insensitive matching
                answer_lower = answer_text.lower().strip()
                for choice in choices:
                    choice_lower = choice.lower()
                    # Check if choice word is in answer
                    if choice_lower in answer_lower or answer_lower in choice_lower:
                        print(f"Fallback matched: '{answer_text}' -> '{choice}'")
                        return choice
                print(f"No fallback match for: '{answer_text}' in {choices}")
                return None
            else:
                return answer_text


# Singleton instance
tree_engine = DecisionTreeEngine()

