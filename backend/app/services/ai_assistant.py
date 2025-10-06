from typing import List, Dict, Any, Tuple, Optional
from openai import OpenAI
from sqlalchemy.orm import Session
import json
from app.config import settings
from app.models import Enquiry, EnquiryMessage, KnowledgeChunk, DecisionTree, EnquiryStatus
from app.services.vector_store import vector_store
from app.services.quote_engine import quote_engine
from app.schemas import AIQuestion, AIResponse


class AIAssistant:
    """AI Assistant for customer interaction using GPT-5"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.system_prompt = """You are a professional sales assistant for Ezzo Sales, a quotation system.

Your role:
1. Help customers with general questions about services and products using the knowledge base
2. Provide helpful information about Ezzo Sales offerings
3. Only start quote collection when the customer explicitly asks for pricing/quotes
4. Always be polite, professional, and helpful

IMPORTANT - Follow this order:
1. FIRST - Answer general questions using the knowledge base information
2. Provide helpful information about services, products, and capabilities
3. ONLY when customer explicitly asks for a quote/price, then start collecting quote information
4. Use the knowledge base to provide accurate information

CRITICAL GST INFORMATION:
- Singapore GST rate is 9% (NOT 8%)
- All prices are quoted before GST
- GST is calculated as 9% of the quoted price
- When providing pricing information, always mention "before GST" and that GST is 9%

IMPORTANT SERVICE CLARIFICATION:
- When customers ask about pricing for services that could have multiple types, ALWAYS clarify what specific service they need first
- Don't assume the service type - ask for clarification before providing pricing
- Use knowledge base information to provide accurate pricing for the correct service
- Even if customer asks "how much", first clarify the service type before providing pricing
- This applies to any service that has multiple variants (installation, repair, maintenance, etc.)

Guidelines:
- Be conversational and helpful
- Use knowledge base information to answer questions accurately
- Don't push for quotes unless customer asks
- If customer asks for a quote, then ask clarifying questions one at a time
- Never make up prices - always use information from the knowledge base
- Focus on being helpful and informative first
- ALWAYS use 9% GST rate for Singapore (never 8%)
- ALWAYS clarify service type before providing pricing

When customer explicitly wants a quote, ask for:
1. What specific service/product they need
2. Exact area/quantity needed
3. Location (affects delivery and pricing)
4. Any special requirements

Only indicate draft quote is ready when customer has explicitly requested pricing and you have collected the necessary information."""
    
    def process_enquiry(
        self,
        db: Session,
        enquiry: Enquiry,
        user_message: str = None
    ) -> AIResponse:
        """Process an enquiry and return AI response"""
        from app.services.tree_engine import tree_engine
        
        # First check if enquiry has a decision tree assigned
        tree = None
        if enquiry.service_tree_id:
            tree = db.query(DecisionTree).filter(DecisionTree.id == enquiry.service_tree_id).first()
        
        # If no tree assigned yet, check if user explicitly wants a quote
        if not tree:
            # Build message to match against
            message_to_match = enquiry.initial_message
            if user_message:
                message_to_match = message_to_match + " " + user_message
            
            # Only match tree if user explicitly wants a quote
            if self._user_wants_quote(message_to_match):
                tree = tree_engine.match_service(db, message_to_match)
                if tree:
                    # Assign the tree to the enquiry
                    enquiry.service_tree_id = tree.id
                    db.commit()
                    print(f"Matched service tree: {tree.service_name} (ID: {tree.id})")
        
        # If we have a decision tree, use tree-based questioning
        if tree:
            return self._process_with_tree(db, enquiry, tree, user_message)
        
        # Get conversation history
        messages = self._build_conversation_history(enquiry, db)
        
        # Add user message if provided
        if user_message:
            messages.append({
                "role": "user",
                "content": user_message
            })
        
        # Search knowledge base for relevant information
        kb_context = self._search_knowledge_base(enquiry.initial_message)
        
        # Add KB context to system message
        if kb_context:
            kb_text = "\n\nRelevant information from knowledge base:\n" + kb_context
            messages[0]["content"] += kb_text
        
        # Check if this is a general question or quote request
        message_to_check = enquiry.initial_message
        if user_message:
            message_to_check = message_to_check + " " + user_message
        is_quote_request = self._user_wants_quote(message_to_check)
        
        # Get AI response
        try:
            # Only use function calling for quote requests
            if is_quote_request:
                functions = [
                    {
                        "name": "ask_question",
                        "description": "Ask the customer a clarifying question",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "question_key": {
                                    "type": "string",
                                    "description": "Unique key for this question (e.g., 'area', 'location')"
                                },
                                "question": {
                                    "type": "string",
                                    "description": "The question to ask the customer"
                                },
                                "question_type": {
                                    "type": "string",
                                    "enum": ["text", "choice", "boolean", "number"],
                                    "description": "Type of answer expected"
                                },
                                "choices": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "For choice type questions, list of options"
                                }
                            },
                            "required": ["question_key", "question", "question_type"]
                        }
                    },
                    {
                        "name": "draft_ready",
                        "description": "Indicate that enough information has been collected to prepare a draft quote",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "summary": {
                                    "type": "string",
                                    "description": "Summary of collected information"
                                }
                            },
                            "required": ["summary"]
                        }
                    }
                ]
            else:
                functions = None
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=0.7,
                functions=functions
            )
            
            choice = response.choices[0]
            
            # Check if function was called
            if choice.finish_reason == "function_call" or (hasattr(choice.message, 'function_call') and choice.message.function_call):
                function_call = choice.message.function_call
                function_name = function_call.name
                function_args = json.loads(function_call.arguments)
                
                if function_name == "ask_question":
                    return AIResponse(
                        message=choice.message.content or function_args.get("question"),
                        questions=[AIQuestion(
                            key=function_args.get("question_key"),
                            question=function_args.get("question"),
                            type=function_args.get("question_type"),
                            choices=function_args.get("choices"),
                            required=True
                        )],
                        draft_available=False
                    )
                
                elif function_name == "draft_ready":
                    summary_msg = function_args.get("summary", "")
                    default_msg = "Alright, the draft quotation would be:"
                    return AIResponse(
                        message=summary_msg if summary_msg else default_msg,
                        questions=[],
                        draft_available=True
                    )
            
            # Regular response
            return AIResponse(
                message=choice.message.content,
                questions=[],
                draft_available=self._check_if_ready(enquiry)
            )
            
        except Exception as e:
            print(f"Error in AI processing: {str(e)}")
            return AIResponse(
                message="I apologize, but I'm having trouble processing your request. Please try again.",
                questions=[],
                draft_available=False
            )
    
    def process_enquiry_stream(
        self,
        db: Session,
        enquiry: Enquiry,
        user_message: str = None
    ):
        """Process enquiry with streaming response"""
        
        from app.services.tree_engine import tree_engine
        
        # First check if enquiry has a decision tree assigned
        tree = None
        if enquiry.service_tree_id:
            tree = db.query(DecisionTree).filter(DecisionTree.id == enquiry.service_tree_id).first()
        
        # If no tree assigned yet, check if user explicitly wants a quote
        if not tree:
            # Build message to match against
            message_to_match = enquiry.initial_message
            if user_message:
                message_to_match = message_to_match + " " + user_message
            
            # Only match tree if user explicitly wants a quote
            if self._user_wants_quote(message_to_match):
                tree = tree_engine.match_service(db, message_to_match)
                if tree:
                    # Assign the tree to the enquiry
                    enquiry.service_tree_id = tree.id
                    db.commit()
                    print(f"Matched service tree: {tree.service_name} (ID: {tree.id})")
        
        # If we have a decision tree, use tree-based questioning
        if tree:
            # Refresh the enquiry object to ensure it's bound to the session
            db.refresh(enquiry)
            yield from self._process_with_tree_stream(db, enquiry, tree, user_message)
            return
        
        # Refresh the enquiry object to ensure it's bound to the session
        db.refresh(enquiry)
        
        # Get conversation history
        messages = self._build_conversation_history(enquiry, db)
        
        # Add user message if provided
        if user_message:
            messages.append({
                "role": "user",
                "content": user_message
            })
        
        # Search knowledge base for relevant information
        kb_context = self._search_knowledge_base(enquiry.initial_message)
        
        # Add KB context to system message
        if kb_context:
            kb_text = "\n\nRelevant information from knowledge base:\n" + kb_context
            messages[0]["content"] += kb_text
        
        # Check if this is a general question or quote request
        message_to_check = enquiry.initial_message
        if user_message:
            message_to_check = message_to_check + " " + user_message
        is_quote_request = self._user_wants_quote(message_to_check)
        
        # Get streaming AI response
        try:
            # Only use function calling for quote requests
            if is_quote_request:
                functions = [
                    {
                        "name": "ask_question",
                        "description": "Ask the customer a clarifying question",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "question_key": {
                                    "type": "string",
                                    "description": "Unique key for this question (e.g., 'area', 'location')"
                                },
                                "question": {
                                    "type": "string",
                                    "description": "The question to ask the customer"
                                },
                                "question_type": {
                                    "type": "string",
                                    "enum": ["text", "choice", "boolean", "number"],
                                    "description": "Type of answer expected"
                                },
                                "choices": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "For choice type questions, list of options"
                                }
                            },
                            "required": ["question_key", "question", "question_type"]
                        }
                    },
                    {
                        "name": "draft_ready",
                        "description": "Indicate that enough information has been collected to prepare a draft quote",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "summary": {
                                    "type": "string",
                                    "description": "Summary of collected information"
                                }
                            },
                            "required": ["summary"]
                        }
                    }
                ]
            else:
                functions = None
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=messages,
                temperature=0.7,
                stream=True,
                functions=functions
            )
            
            full_content = ""
            function_call_data = None
            
            for chunk in response:
                if chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_content += content
                    yield {
                        'type': 'content',
                        'content': content
                    }
                
                # Check for function calls
                if chunk.choices[0].delta.function_call:
                    if not function_call_data:
                        function_call_data = {
                            'name': chunk.choices[0].delta.function_call.name or '',
                            'arguments': ''
                        }
                    if chunk.choices[0].delta.function_call.arguments:
                        function_call_data['arguments'] += chunk.choices[0].delta.function_call.arguments
            
            # Handle function calls
            if function_call_data and function_call_data['name']:
                try:
                    function_args = json.loads(function_call_data['arguments'])
                    
                    if function_call_data['name'] == "ask_question":
                        # Save AI response
                        assistant_message = EnquiryMessage(
                            enquiry_id=enquiry.id,
                            role="assistant",
                            content=full_content or function_args.get("question")
                        )
                        db.add(assistant_message)
                        db.commit()
                        
                        yield {
                            'type': 'question',
                            'question_key': function_args.get("question_key"),
                            'question': function_args.get("question"),
                            'question_type': function_args.get("question_type"),
                            'choices': function_args.get("choices"),
                            'required': True
                        }
                        return
                    
                    elif function_call_data['name'] == "draft_ready":
                        # Save AI response
                        assistant_message = EnquiryMessage(
                            enquiry_id=enquiry.id,
                            role="assistant",
                            content=full_content or function_args.get("summary", "Alright, the draft quotation would be:")
                        )
                        db.add(assistant_message)
                        
                        # Update status and generate draft quote
                        enquiry.status = EnquiryStatus.DRAFT_READY
                        
                        # Only extract data if NOT using a decision tree
                        if not enquiry.service_tree_id:
                            try:
                                # Build conversation text
                                conversation_text = f"Initial request: {enquiry.initial_message}\n\n"
                                for msg in enquiry.messages:
                                    conversation_text += f"{msg.role}: {msg.content}\n"
                                
                                # Use AI to extract structured requirements
                                extracted_data = self.extract_requirements(conversation_text)
                                print(f"Extracted data from conversation: {extracted_data}")
                                
                                # Store in collected_data
                                if extracted_data:
                                    enquiry.collected_data = extracted_data
                            except Exception as extract_err:
                                print(f"Error extracting data: {str(extract_err)}")
                        
                        db.commit()
                        
                        # Generate and show draft quote to user
                        try:
                            draft = quote_engine.calculate_draft_quote(db, enquiry)
                            
                            yield {
                                'type': 'draft_ready',
                                'message': full_content or function_args.get("summary", "Alright, the draft quotation would be:"),
                                'draft_quote': draft.dict() if draft else None
                            }
                            
                            # Auto-submit to admin if all info is available
                            if draft and draft.can_submit and draft.base_price > 0:
                                # Create quote (no KnowledgeChunk dependency)
                                quote = quote_engine.create_quote_from_draft(
                                    db, enquiry.id, draft, source_chunk_ids=[]
                                )
                                
                                # Update enquiry status
                                enquiry.status = EnquiryStatus.SENT_TO_ADMIN
                                db.commit()
                                
                        except Exception as e:
                            print(f"Error generating draft quote: {str(e)}")
                            import traceback
                            traceback.print_exc()
                        
                        return
                
                except json.JSONDecodeError:
                    pass
            
            # Regular response - save to database
            assistant_message = EnquiryMessage(
                enquiry_id=enquiry.id,
                role="assistant",
                content=full_content
            )
            db.add(assistant_message)
            db.commit()
            
            # Check if draft is ready
            if self._check_if_ready(enquiry):
                enquiry.status = EnquiryStatus.DRAFT_READY
                db.commit()
                
                try:
                    draft = quote_engine.calculate_draft_quote(db, enquiry)
                    yield {
                        'type': 'draft_ready',
                        'message': full_content,
                        'draft_quote': draft.dict() if draft else None
                    }
                except Exception as e:
                    print(f"Error generating draft quote: {str(e)}")
            
        except Exception as e:
            print(f"Error in AI streaming: {str(e)}")
            yield {
                'type': 'error',
                'message': "I apologize, but I'm having trouble processing your request. Please try again."
            }
    
    def _process_with_tree_stream(
        self,
        db: Session,
        enquiry: Enquiry,
        tree: DecisionTree,
        user_message: str = None
    ):
        """Process enquiry using a decision tree with streaming"""
        from app.services.tree_engine import tree_engine
        
        # Refresh the enquiry object to ensure it's bound to the session
        db.refresh(enquiry)
        
        collected_data = enquiry.collected_data or {}
        
        # Get the next unanswered question
        next_q = tree_engine.get_next_question(tree, collected_data)
        
        # Check if the tree has asked any questions yet (has assistant messages)
        assistant_messages = [msg for msg in enquiry.messages if msg.role == "assistant"]
        tree_has_asked_question = len(assistant_messages) > 0
        
        # If user provided a message AND tree has asked a question, process the answer
        if user_message and next_q and tree_has_asked_question:
            # Parse the answer based on question type
            parsed_answer = tree_engine.parse_answer(
                user_message, 
                next_q.type, 
                next_q.choices
            )
            
            if parsed_answer is not None:
                # Store the answer
                collected_data[next_q.key] = parsed_answer
                enquiry.collected_data = collected_data
                db.commit()
                
                # Get next question
                next_q = tree_engine.get_next_question(tree, collected_data)
        
        # If no more questions, prepare draft
        if not next_q:
            enquiry.status = EnquiryStatus.DRAFT_READY
            db.commit()
            
            try:
                draft = quote_engine.calculate_draft_quote(db, enquiry)
                
                # Save assistant message
                assistant_message = EnquiryMessage(
                    enquiry_id=enquiry.id,
                    role="assistant",
                    content="Alright, the draft quotation would be:"
                )
                db.add(assistant_message)
                db.commit()
                
                yield {
                    'type': 'draft_ready',
                    'message': "Alright, the draft quotation would be:",
                    'draft_quote': draft.dict() if draft else None
                }
                
                # Auto-submit to admin if all info is available
                if draft and draft.can_submit and draft.base_price > 0:
                    # Create quote (no KnowledgeChunk dependency)
                    quote = quote_engine.create_quote_from_draft(
                        db, enquiry.id, draft, source_chunk_ids=[]
                    )
                    
                    # Update enquiry status
                    enquiry.status = EnquiryStatus.SENT_TO_ADMIN
                    db.commit()
                    
            except Exception as e:
                print(f"Error generating draft quote: {str(e)}")
                import traceback
                traceback.print_exc()
                
                yield {
                    'type': 'error',
                    'message': "I apologize, but I'm having trouble processing your request. Please try again."
                }
            
            return
        
        # Ask the next question
        question_text = next_q.question
        if next_q.choices:
            question_text += f"\n\nOptions: {', '.join(next_q.choices)}"
        
        # Save assistant message
        assistant_message = EnquiryMessage(
            enquiry_id=enquiry.id,
            role="assistant",
            content=question_text
        )
        db.add(assistant_message)
        db.commit()
        
        # Stream the question
        yield {
            'type': 'question',
            'question_key': next_q.key,
            'question': question_text,
            'question_type': next_q.type,
            'choices': next_q.choices,
            'required': next_q.required
        }
    
    def _process_with_tree(
        self,
        db: Session,
        enquiry: Enquiry,
        tree: DecisionTree,
        user_message: str = None
    ) -> AIResponse:
        """Process enquiry using a decision tree"""
        from app.services.tree_engine import tree_engine
        
        collected_data = enquiry.collected_data or {}
        
        # Get the next unanswered question
        next_q = tree_engine.get_next_question(tree, collected_data)
        
        # Check if the tree has asked any questions yet (has assistant messages)
        assistant_messages = [msg for msg in enquiry.messages if msg.role == "assistant"]
        tree_has_asked_question = len(assistant_messages) > 0
        
        # If user provided a message AND tree has asked a question, process the answer
        if user_message and next_q and tree_has_asked_question:
                # Parse the answer based on question type
                parsed_answer = tree_engine.parse_answer(
                    user_message, 
                    next_q.type, 
                    next_q.choices
                )
                
                # Only store if we got a valid answer
                if parsed_answer is not None:
                    if not enquiry.collected_data:
                        enquiry.collected_data = {}
                    enquiry.collected_data[next_q.key] = parsed_answer
                    
                    # Mark the JSON field as modified so SQLAlchemy detects the change
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(enquiry, "collected_data")
                    
                    db.commit()
                    
                    # IMPORTANT: Re-fetch enquiry to ensure collected_data is fresh
                    db.expire(enquiry)
                    enquiry = db.query(type(enquiry)).filter_by(id=enquiry.id).first()
                    collected_data = enquiry.collected_data or {}
                    
                    print(f"Stored answer: {next_q.key} = {parsed_answer}")
                    print(f"Current collected_data: {collected_data}")
                else:
                    # Invalid answer for choice question - ask again
                    return AIResponse(
                        message=f"I didn't quite understand that. {next_q.question}",
                        questions=[next_q],
                        draft_available=False
                    )
        
        # Check if tree is complete
        if tree_engine.is_complete(tree, enquiry.collected_data or {}):
            # All questions answered, ready for draft
            # Generate a human-readable summary
            summary = self._generate_tree_summary(tree, enquiry.collected_data or {})
            return AIResponse(
                message=summary,
                questions=[],
                draft_available=True
            )
        
        # Get next question
        next_question = tree_engine.get_next_question(tree, enquiry.collected_data or {})
        
        if next_question:
            return AIResponse(
                message=next_question.question,
                questions=[next_question],
                draft_available=False
            )
        
        # Shouldn't reach here, but fallback
        return AIResponse(
            message="Thank you for providing the information.",
            questions=[],
            draft_available=True
        )
    
    def _build_conversation_history(self, enquiry: Enquiry, db: Session = None) -> List[Dict[str, str]]:
        """Build conversation history for AI"""
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Add initial message
        messages.append({
            "role": "user",
            "content": enquiry.initial_message
        })
        
        # Add conversation history - query messages directly to avoid session issues
        if db:
            enquiry_messages = db.query(EnquiryMessage).filter(
                EnquiryMessage.enquiry_id == enquiry.id
            ).order_by(EnquiryMessage.id).all()
            
            for msg in enquiry_messages:
                role = "assistant" if msg.role == "assistant" else "user"
                messages.append({
                    "role": role,
                    "content": msg.content
                })
        else:
            # Fallback to direct access (may cause session issues)
            for msg in enquiry.messages:
                role = "assistant" if msg.role == "assistant" else "user"
                messages.append({
                    "role": role,
                    "content": msg.content
                })
        
        return messages
    
    def _search_knowledge_base(self, query: str) -> str:
        """Search knowledge base for relevant information"""
        try:
            results = vector_store.search(query, limit=3)
            
            if not results:
                return ""
            
            kb_text = ""
            for i, result in enumerate(results):
                kb_text += f"\n{i+1}. {result['content']}\n"
                if result.get('metadata'):
                    meta = result['metadata']
                    if meta.get('item_name'):
                        kb_text += f"   Item: {meta['item_name']}\n"
                    if meta.get('base_price'):
                        kb_text += f"   Price: {meta['base_price']} {meta.get('price_unit', '')}\n"
            
            return kb_text
        except Exception as e:
            print(f"Error searching KB: {str(e)}")
            return ""
    
    def _check_if_ready(self, enquiry: Enquiry) -> bool:
        """Check if enough information is collected for draft"""
        collected = enquiry.collected_data or {}
        
        # Basic required fields
        required_fields = ['item', 'quantity_or_area']
        
        for field in required_fields:
            if field not in collected or not collected[field]:
                return False
        
        return True
    
    def extract_requirements(self, enquiry_text: str) -> Dict[str, Any]:
        """Extract requirements from enquiry using GPT-5"""
        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """Extract key information from this customer conversation.

Return a JSON object with these fields:
- item: Main product/service (e.g., "cat ladder", "parquet flooring", "flagpoles")
- quantity: Number of units or area (default to 1 if not specified)
- location: Location/address
- material: Material type if mentioned (e.g., "aluminium", "steel", "stainless steel")
- height: Height specification if mentioned (e.g., "5m", "10m", "31 feet")
- special_features: Array of special features if mentioned (e.g., ["safety cage", "access door"])

Examples:
- "2 aluminum cat ladders, 5m high, with safety cage" → {"item": "cat ladder", "quantity": 2, "material": "aluminium", "height": "5m", "special_features": ["safety cage"]}
- "1 cat ladder 10m high with cage and door" → {"item": "cat ladder", "quantity": 1, "height": "10m", "special_features": ["safety cage", "access door"]}

Only include fields that were clearly mentioned in the conversation."""
                    },
                    {
                        "role": "user",
                        "content": enquiry_text
                    }
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            extracted = json.loads(response.choices[0].message.content)
            print(f"Raw extracted data: {extracted}")
            return extracted
        except Exception as e:
            print(f"Error extracting requirements: {str(e)}")
            import traceback
            traceback.print_exc()
            return {}
    
    def _user_wants_quote(self, message: str) -> bool:
        """Check if user explicitly wants a quote using AI"""
        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """Determine if the user explicitly wants a quote or pricing information.

Return JSON: {"wants_quote": true/false}

The user wants a quote if they:
- Explicitly ask for a "quote" or "quotation"
- Say "I need a quote for..." with specific service details
- Clearly specify the service type AND request pricing
- Want to get a formal quotation

The user does NOT want a quote if they:
- Are just asking general questions
- Want information about services
- Are browsing or learning
- Ask "what services do you offer?"
- Ask general questions without mentioning pricing
- Ask "how much" without clear service specification
- Mention multiple possible service types that need clarification

Examples:
- "I need a quote for cat ladder installation" → {"wants_quote": true}
- "What services do you offer?" → {"wants_quote": false}
- "Tell me about parquet flooring" → {"wants_quote": false}
- "How much for 3 bedroom parquet" → {"wants_quote": false} (needs clarification)
- "I need a quote for parquet sanding and varnishing" → {"wants_quote": true}
- "Hello" → {"wants_quote": false}"""
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                temperature=0,
                response_format={"type": "json_object"},
                max_tokens=50
            )
            
            result = json.loads(response.choices[0].message.content)
            return result.get('wants_quote', False)
            
        except Exception as e:
            print(f"Error checking quote intent: {str(e)}")
            # Fallback: check for explicit quote keywords only
            quote_keywords = ['quote', 'quotation']
            message_lower = message.lower()
            return any(keyword in message_lower for keyword in quote_keywords)
    
    def _generate_tree_summary(self, tree: DecisionTree, collected_data: Dict[str, Any]) -> str:
        """Generate a human-readable summary from tree answers"""
        try:
            # Build summary from answers
            summary_parts = []
            questions = tree.tree_config.get('questions', [])
            
            for q in questions:
                q_id = q.get('id')
                if q_id in collected_data:
                    answer = collected_data[q_id]
                    question_text = q.get('question', q_id)
                    summary_parts.append(f"- {question_text}: {answer}")
            
            if summary_parts:
                summary = f"Thank you! Here's what I have:\n" + "\n".join(summary_parts)
            else:
                summary = f"All information collected for {tree.display_name}."
            
            return summary
        except Exception as e:
            print(f"Error generating tree summary: {str(e)}")
            return f"All information collected for {tree.display_name}."


# Singleton instance
ai_assistant = AIAssistant()
