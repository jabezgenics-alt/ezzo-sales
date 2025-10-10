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
        self.vision_model = "gpt-4o"  # GPT-4 with vision for image analysis
        self.system_prompt = """You are a professional sales assistant for Ezzo Sales, a quotation system.

Your role:
1. Help customers with general questions about services and products using the knowledge base
2. Provide helpful information about Ezzo Sales offerings
3. Discuss services conversationally when customers ask "how much" questions
4. Offer to create formal quotes when customers show genuine interest
5. Always be polite, professional, and helpful

CRITICAL - CONVERSATIONAL FLOW:
When customers ask "how much for X" or "price for X":
- DO NOT mention specific prices or numbers
- DO NOT immediately start the formal quote process
- INSTEAD: Discuss the service features, options, materials, and considerations
- Explain what factors affect pricing (e.g., height, material, installation complexity)
- Keep the conversation natural and sales-oriented
- After discussing and if customer shows interest, offer: "Would you like me to create a detailed quote for this?"

NEVER mention specific prices until you're in the formal quote process!

WHEN TO OFFER A FORMAL QUOTE:
After discussing the service conversationally, offer to create a quote if:
- Customer asks detailed questions about the service
- Customer mentions specific requirements (e.g., "I need a 2m ladder")
- Conversation shows genuine interest (not just browsing)
- You've explained the service and options

Say something like:
- "Would you like me to create a detailed quote for this?"
- "I can prepare a formal quotation with exact pricing if you'd like?"
- "Shall I generate a quote with all the details?"

WHEN TO START FORMAL QUOTE PROCESS:
Only start the structured quote collection when:
- Customer explicitly says "I need a quote" or "give me a quote"
- Customer confirms "yes" after you offer to create a quote
- Customer says "proceed", "confirm", "sure" in response to your quote offer

CRITICAL GST INFORMATION:
- Singapore GST rate is 9% (NOT 8%)
- All prices are quoted before GST
- GST is calculated as 9% of the quoted price
- Only mention GST when providing actual pricing in formal quotes

Guidelines:
- Be conversational and helpful
- Use knowledge base to discuss service features and options (NOT prices)
- Build rapport before jumping into formal quoting
- If customer asks "how much", discuss the service first, then offer to create a quote
- Never make up prices - only show prices in formal quotes after gathering all details
- Focus on being consultative and informative
- ALWAYS use 9% GST rate for Singapore (never 8%)

CRITICAL - WORKFLOW FOR GENERATING QUOTES:
1. Collect required information: service type, quantity/area, and location
2. Once ALL information is collected, you have two options:
   
   Option A - Customer explicitly requests the quote:
   - If customer says "give me a quote", "generate quote", "show me the quote", "provide quote", "pls give quote", etc.
   - IMMEDIATELY call the draft_ready function to generate the quote
   - DO NOT ask for additional confirmation
   
   Option B - Customer provides info but doesn't explicitly request quote yet:
   - Summarize what you have collected
   - Ask: "Would you like me to generate a quotation with these details?"
   - Wait for customer to confirm ("yes", "confirm", "proceed", "give quote", etc.)
   - Then call draft_ready function

WHEN TO CALL draft_ready FUNCTION:
- When customer explicitly says "give me a quote", "generate quote", "provide quote", "show quote", etc.
- When customer confirms after you've summarized the collected information
- When customer says "confirm", "yes", "proceed" in response to your summary

WHEN NOT TO CALL draft_ready:
- When you're still collecting information
- When customer is just asking questions about the service
- When information is incomplete

Remember: Build rapport with conversation first, offer quotes when appropriate, then collect details for formal pricing."""
    
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
            
            # Build conversation history for context
            conv_history = ""
            if enquiry.messages:
                recent_msgs = enquiry.messages[-4:]  # Last 4 messages for context
                for msg in recent_msgs:
                    conv_history += f"{msg.role}: {msg.content}\n"
            
            # Only match tree if user explicitly wants a quote
            if self._user_wants_quote(user_message or enquiry.initial_message, conv_history):
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
                        "description": "CALL THIS FUNCTION to generate the actual draft quote. Call it when: 1) Customer explicitly says 'give me a quote', 'generate quote', 'provide quote', etc. OR 2) Customer confirms after you've summarized the information. You MUST have service type, quantity/area collected before calling.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "summary": {
                                    "type": "string",
                                    "description": "Brief summary of the quote details (e.g., 'Vinyl flooring for 31 sqm at Singapore Bedok 42 Street')"
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
            
            # Build conversation history for context
            conv_history = ""
            if enquiry.messages:
                recent_msgs = enquiry.messages[-4:]  # Last 4 messages for context
                for msg in recent_msgs:
                    conv_history += f"{msg.role}: {msg.content}\n"
            
            # Only match tree if user explicitly wants a quote
            if self._user_wants_quote(user_message or enquiry.initial_message, conv_history):
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
                        "description": "CALL THIS FUNCTION to generate the actual draft quote. Call it when: 1) Customer explicitly says 'give me a quote', 'generate quote', 'provide quote', etc. OR 2) Customer confirms after you've summarized the information. You MUST have service type, quantity/area collected before calling.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "summary": {
                                    "type": "string",
                                    "description": "Brief summary of the quote details (e.g., 'Vinyl flooring for 31 sqm at Singapore Bedok 42 Street')"
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
            
            # Check if AI should offer to create a quote
            if not enquiry.service_tree_id and self._should_offer_quote(enquiry, full_content):
                # Append quote offer to the response
                quote_offer = "\n\nWould you like me to create a detailed quote for this?"
                
                # Save the quote offer as part of the message
                assistant_message.content = full_content + quote_offer
                db.commit()
                
                # Yield the quote offer
                yield {
                    'type': 'content',
                    'content': quote_offer
                }
                
                # Mark that we've offered a quote
                collected_data = enquiry.collected_data or {}
                collected_data['_quote_offered'] = True
                enquiry.collected_data = collected_data
                
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(enquiry, "collected_data")
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
            import traceback
            traceback.print_exc()
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
        
        # Check if the tree has asked any questions yet
        # We look for actual answered questions (excluding context metadata)
        actual_answers = {k: v for k, v in collected_data.items() if not k.startswith('_')}
        tree_has_asked_question = len(actual_answers) > 0
        
        # If tree just assigned and no questions answered yet, extract context from conversation
        if not tree_has_asked_question and not collected_data.get('_context_extracted'):
            print("Extracting conversation context for decision tree...")
            context_data = self._extract_conversation_context(enquiry, tree)
            
            if context_data:
                print(f"Extracted context: {context_data}")
                # Store extracted context with metadata
                for q_id, data in context_data.items():
                    collected_data[q_id] = data
                
                collected_data['_context_extracted'] = True
                enquiry.collected_data = collected_data
                
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(enquiry, "collected_data")
                db.commit()
        
        # Get the next unanswered question
        next_q = tree_engine.get_next_question(tree, collected_data)
        
        # If user provided a message AND tree has asked a question, process the answer
        if user_message and next_q and tree_has_asked_question:
            # Check if this was a context confirmation (from_context flag present)
            is_context_confirmation = (
                next_q.key in collected_data and 
                isinstance(collected_data[next_q.key], dict) and 
                collected_data[next_q.key].get('from_context') and
                not collected_data[next_q.key].get('confirmed')
            )
            
            if is_context_confirmation:
                # User is responding to context confirmation
                # Check if they're confirming or correcting
                confirmation_intent = self._check_user_intent(user_message)
                
                if 'yes' in user_message.lower() or 'correct' in user_message.lower() or 'yep' in user_message.lower():
                    # User confirmed context value
                    context_entry = collected_data[next_q.key]
                    context_entry['confirmed'] = True
                    collected_data[next_q.key] = context_entry
                    
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(enquiry, "collected_data")
                    db.commit()
                    
                    print(f"Context confirmed for {next_q.key}: {context_entry.get('value')}")
                    
                    # Get next question
                    next_q = tree_engine.get_next_question(tree, collected_data)
                else:
                    # User is providing a different answer (correction)
                    parsed_answer = tree_engine.parse_answer(
                        user_message, 
                        next_q.type, 
                        next_q.choices
                    )
                    
                    if parsed_answer is not None or (next_q.type == 'boolean' and isinstance(parsed_answer, bool)):
                        collected_data[next_q.key] = parsed_answer
                        
                        from sqlalchemy.orm.attributes import flag_modified
                        flag_modified(enquiry, "collected_data")
                        db.commit()
                        
                        print(f"Context corrected for {next_q.key}: {parsed_answer}")
                        
                        # Get next question
                        next_q = tree_engine.get_next_question(tree, collected_data)
                    else:
                        yield {
                            'type': 'message',
                            'content': f"I didn't quite understand that. {next_q.question}"
                        }
                        return
            else:
                # Normal answer processing
                # First check if user is going sideways (asking a different question)
                if self._is_sideways_question(user_message, next_q.type, next_q.question):
                    # Answer their sideways question
                    sideways_answer = self._answer_sideways_question(user_message, enquiry, db)
                    
                    # Rephrase the pending question naturally
                    rephrased_q = self._rephrase_question_naturally(
                        next_q.question,
                        next_q.type,
                        next_q.choices,
                        enquiry.messages
                    )
                    
                    # Create redirect message
                    redirect_message = f"{sideways_answer}\n\nNow, to continue with your quote: {rephrased_q}"
                    
                    # Save the AI's sideways response
                    sideways_msg = EnquiryMessage(
                        enquiry_id=enquiry.id,
                        role="assistant",
                        content=redirect_message
                    )
                    db.add(sideways_msg)
                    db.commit()
                    
                    # Stream the response
                    yield {
                        'type': 'message',
                        'content': redirect_message
                    }
                    return
                
                # Try to parse the answer based on question type
                parsed_answer = tree_engine.parse_answer(
                    user_message, 
                    next_q.type, 
                    next_q.choices
                )
                
                print(f"Parsed answer for {next_q.key}: {parsed_answer} (type: {type(parsed_answer)})")
                
                # Check if parsing succeeded (note: False is a valid answer for boolean!)
                if parsed_answer is not None or (next_q.type == 'boolean' and isinstance(parsed_answer, bool)):
                    # Store the answer
                    collected_data[next_q.key] = parsed_answer
                    enquiry.collected_data = collected_data
                    
                    # Mark as modified for SQLAlchemy
                    from sqlalchemy.orm.attributes import flag_modified
                    flag_modified(enquiry, "collected_data")
                    
                    db.commit()
                    print(f"Stored answer: {next_q.key} = {parsed_answer}")
                    print(f"Updated collected_data: {enquiry.collected_data}")
                    
                    # Get next question
                    next_q = tree_engine.get_next_question(tree, collected_data)
                else:
                    # Parsing failed - check if user wants to skip or proceed anyway
                    user_intent = self._check_user_intent(user_message)
                    
                    if user_intent == "skip" or user_intent == "proceed_anyway":
                        # User wants to skip this question - mark as empty string for optional questions
                        if not next_q.required:
                            collected_data[next_q.key] = ""
                            enquiry.collected_data = collected_data
                            
                            from sqlalchemy.orm.attributes import flag_modified
                            flag_modified(enquiry, "collected_data")
                            
                            db.commit()
                            next_q = tree_engine.get_next_question(tree, collected_data)
                        else:
                            # Required question - ask AI to respond naturally
                            yield {
                                'type': 'message',
                                'content': f"I need this information to provide an accurate quote: {next_q.question}"
                            }
                            return
                    else:
                        # Failed to parse and not trying to skip - ask for clarification
                        yield {
                            'type': 'message',
                            'content': f"I didn't quite understand that. {next_q.question}"
                        }
                        return
        
        # If no more questions, prepare draft
        if not next_q:
            # Apply business rules before generating draft
            from app.services.rules_engine import rules_engine
            
            service_type = tree.service_name if tree else None
            rules_result = rules_engine.validate_and_apply_rules(db, service_type, collected_data)
            
            # Store rules results in collected_data for quote engine to use
            if rules_result and (rules_result.get("requirements") or rules_result.get("conditions")):
                collected_data["auto_requirements"] = rules_result.get("requirements", [])
                collected_data["auto_conditions"] = rules_result.get("conditions", [])
                enquiry.collected_data = collected_data
                
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(enquiry, "collected_data")
            
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
        # Check if this question has a context value that needs confirmation
        has_context_value = (
            next_q.key in collected_data and 
            isinstance(collected_data[next_q.key], dict) and 
            collected_data[next_q.key].get('from_context')
        )
        
        if has_context_value:
            # Ask for confirmation of context-extracted value
            context_data = collected_data[next_q.key]
            context_value = context_data.get('value')
            context_source = context_data.get('source', '')
            
            question_text = self._confirm_context_value(
                next_q.question,
                context_value,
                context_source
            )
            
            print(f"Asking context confirmation for {next_q.key}: {context_value}")
        else:
            # Rephrase question naturally with AI
            # Get recent conversation context for better rephrasing
            recent_context = ""
            if len(enquiry.messages) > 0:
                recent_msgs = enquiry.messages[-2:]  # Last 2 messages
                recent_context = " ".join([msg.content[:50] for msg in recent_msgs])
            
            question_text = self._rephrase_question_naturally(
                next_q.question,
                next_q.type,
                next_q.choices,
                tree.display_name,
                recent_context
            )
            
            print(f"Rephrased question for {next_q.key}: {question_text[:100]}...")
        
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
            # Apply business rules before generating draft
            from app.services.rules_engine import rules_engine
            
            service_type = tree.service_name if tree else None
            rules_result = rules_engine.validate_and_apply_rules(db, service_type, enquiry.collected_data or {})
            
            # Store rules results in collected_data for quote engine to use
            if rules_result and (rules_result.get("requirements") or rules_result.get("conditions")):
                if not enquiry.collected_data:
                    enquiry.collected_data = {}
                enquiry.collected_data["auto_requirements"] = rules_result.get("requirements", [])
                enquiry.collected_data["auto_conditions"] = rules_result.get("conditions", [])
                
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(enquiry, "collected_data")
                db.commit()
            
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
                content = msg.content
                
                # If user message has an image, prepend context so AI remembers
                if msg.role == "customer" and msg.image_url:
                    content = f"[User uploaded an image with caption: {msg.content}]"
                
                messages.append({
                    "role": role,
                    "content": content
                })
        else:
            # Fallback to direct access (may cause session issues)
            for msg in enquiry.messages:
                role = "assistant" if msg.role == "assistant" else "user"
                content = msg.content
                
                # If user message has an image, prepend context so AI remembers
                if msg.role == "customer" and msg.image_url:
                    content = f"[User uploaded an image with caption: {msg.content}]"
                
                messages.append({
                    "role": role,
                    "content": content
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
- item: Main product/service (e.g., "cat ladder", "parquet flooring", "vinyl flooring", "flagpoles")
- quantity_or_area: Number of units or area (e.g., "21 sqm", "2 units", "100 sqm")
- location: Location/address
- material: Material type if mentioned (e.g., "aluminium", "steel", "stainless steel", "vinyl")
- height: Height specification if mentioned (e.g., "5m", "10m", "31 feet")
- special_features: Array of special features if mentioned (e.g., ["safety cage", "access door", "rubber underlay", "plywood"])

Examples:
- "2 aluminum cat ladders, 5m high, with safety cage" → {"item": "cat ladder", "quantity_or_area": "2 units", "material": "aluminium", "height": "5m", "special_features": ["safety cage"]}
- "vinyl flooring for 21 sqm master bedroom" → {"item": "vinyl flooring", "quantity_or_area": "21 sqm", "special_features": ["rubber underlay", "plywood"]}
- "parquet flooring installation 100 sqm" → {"item": "parquet flooring", "quantity_or_area": "100 sqm"}

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
    
    def _user_wants_quote(self, message: str, conversation_history: str = "") -> bool:
        """Check if user explicitly wants a quote using AI"""
        try:
            # Build the full context
            full_context = message
            if conversation_history:
                full_context = f"Recent conversation:\n{conversation_history}\n\nLatest user message: {message}"
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """Determine if the user explicitly wants to START THE FORMAL QUOTE PROCESS.

Return JSON: {"wants_quote": true/false}

The user wants a quote (return true) if they:
- Explicitly say "I need a quote" or "I want a quote"
- Say "give me a quote", "generate quote", "create a quote", "prepare a quote"
- Say "I'd like a quote" or "id like a quote"
- Say "yes", "yeah", "yea", "yep", "sure", "ok", "okay", "confirm", "proceed" when AI has asked "Would you like me to create/generate/prepare a quote"
- Say "go ahead", "let's do it", "do it", "alright" in response to a quote offer
- Want to get a formal quotation and use the word "quote"

The user does NOT want a quote (return false) if they:
- Ask "how much for X" or "how much does X cost" (they want discussion first)
- Ask "price for X" or "cost of X" (they want discussion first)
- Ask "what's the pricing for X" (they want discussion first)
- Are just asking general questions about services
- Want information or are browsing
- Ask "what services do you offer?"
- Say "tell me about X service"
- Ask questions without explicitly requesting a quote
- Just greet or say hello
- Are in the middle of providing details but haven't confirmed they want the quote yet

CRITICAL: "how much", "price", "cost" questions should return FALSE - user wants discussion first, not immediate quote process!

IMPORTANT: If the conversation shows the AI has asked "Would you like me to create/generate/prepare a quote?" and user responds with ANY affirmative (yes, yeah, yea, ok, okay, sure, alright, proceed, go ahead), return TRUE!

Examples:
- "I need a quote for cat ladder installation" → {"wants_quote": true}
- "give me a quote" → {"wants_quote": true}
- "prepare a quote" → {"wants_quote": true}
- "I'd like a quote" → {"wants_quote": true}
- "yes" (after AI asked "would you like me to create a quote") → {"wants_quote": true}
- "yeah" (after AI offered quote) → {"wants_quote": true}
- "yea" (after AI offered quote) → {"wants_quote": true}
- "ok" (after AI asked "would you like me to generate a quote") → {"wants_quote": true}
- "okay" (after AI offered quote) → {"wants_quote": true}
- "sure" (after AI offered quote) → {"wants_quote": true}
- "alright" (after AI offered quote) → {"wants_quote": true}
- "confirm" (after AI offered quote) → {"wants_quote": true}
- "proceed" (after AI offered quote) → {"wants_quote": true}
- "go ahead" (after AI offered quote) → {"wants_quote": true}
- "how much for 2m high cat ladder" → {"wants_quote": false}
- "how much for cat ladder" → {"wants_quote": false}
- "price for ss316 ladder" → {"wants_quote": false}
- "cost of installation" → {"wants_quote": false}
- "what's the pricing" → {"wants_quote": false}
- "What services do you offer?" → {"wants_quote": false}
- "Tell me about parquet flooring" → {"wants_quote": false}
- "how much" → {"wants_quote": false}
- "Hello" → {"wants_quote": false}
- "aluminum" (just answering a question) → {"wants_quote": false}"""
                    },
                    {
                        "role": "user",
                        "content": full_context
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
            return False
    
    def _should_offer_quote(self, enquiry: Enquiry, current_response: str) -> bool:
        """Determine if AI should offer to create a quote based on conversation context"""
        try:
            # Build conversation history
            messages_text = ""
            for msg in enquiry.messages:
                role = "Customer" if msg.role == "customer" else "AI"
                messages_text += f"{role}: {msg.content}\n"
            
            # Add current AI response
            messages_text += f"AI (current): {current_response}\n"
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """Analyze the conversation to determine if the AI should offer to create a formal quote.

Return JSON: {"should_offer": true/false, "reason": "brief explanation"}

Offer a quote if:
- Customer has asked about pricing/cost ("how much", "price for", "cost of")
- Customer has mentioned specific requirements or details (e.g., "2m ladder", "ss316 material")
- Customer is asking detailed questions showing genuine interest
- Conversation has gone 1-2+ turns discussing a specific service
- Customer seems ready but hasn't explicitly requested a quote yet

Do NOT offer a quote if:
- This is the very first message (too early)
- Customer is just browsing or asking very general questions
- Customer already explicitly said they want a quote (they'll say it themselves)
- AI has ALREADY offered a quote in this conversation (don't repeat)
- Customer is asking about multiple different services (needs focus first)

Check if quote was already offered by looking for phrases like "Would you like me to create" or "Shall I generate" in AI messages.

Examples:
Customer: "how much for cat ladder" 
AI: "Cat ladders come in various materials..." (discusses service)
→ {"should_offer": true, "reason": "Customer asked about pricing, AI has explained the service"}

Customer: "Hello"
AI: "Hello! How can I help?"
→ {"should_offer": false, "reason": "Too early, just a greeting"}

Customer: "I need ss316 2m ladder"
AI: "Great choice! SS316 is corrosion resistant..." (discusses)
→ {"should_offer": true, "reason": "Customer has specific requirements"}"""
                    },
                    {
                        "role": "user",
                        "content": f"Conversation:\n{messages_text}"
                    }
                ],
                temperature=0,
                response_format={"type": "json_object"},
                max_tokens=100
            )
            
            result = json.loads(response.choices[0].message.content)
            should_offer = result.get('should_offer', False)
            reason = result.get('reason', '')
            
            if should_offer:
                print(f"Should offer quote: {reason}")
            
            return should_offer
        except Exception as e:
            print(f"Error checking if should offer quote: {str(e)}")
            return False
    
    def _check_user_intent(self, message: str) -> str:
        """Check user's intent when answering decision tree questions"""
        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """Determine the user's intent from their message.

Return JSON: {"intent": "answer"|"skip"|"proceed_anyway"}

Intents:
- "answer": User is providing an answer to the question
- "skip": User wants to skip this question or doesn't know the answer
- "proceed_anyway": User wants to proceed with the quote/process without answering

Examples:
- "53 square meters" → {"intent": "answer"}
- "master bed 10sqm" → {"intent": "answer"}
- "I don't know" → {"intent": "skip"}
- "Skip this" → {"intent": "skip"}
- "Ask about a quote" → {"intent": "proceed_anyway"}
- "Just give me the quote" → {"intent": "proceed_anyway"}
- "Can we skip this" → {"intent": "skip"}
- "Not sure" → {"intent": "skip"}
- "1 only" → {"intent": "answer"}
- "Apartment" → {"intent": "answer"}"""
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
            return result.get('intent', 'answer')
        except Exception as e:
            print(f"Error checking user intent: {str(e)}")
            return 'answer'  # Default to treating as answer
            # Fallback: check for explicit quote keywords only
            quote_keywords = ['quote', 'quotation', 'confirm', 'proceed', 'finalize', 'complete']
            message_lower = message.lower()
            return any(keyword in message_lower for keyword in quote_keywords)
    
    def _is_sideways_question(self, user_message: str, expected_type: str, expected_question: str) -> bool:
        """Detect if user is asking a question instead of answering the pending question"""
        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """Determine if the user is going "sideways" by asking a different question instead of answering the pending question.

Return JSON: {"is_sideways": true/false}

The user IS going sideways (return true) if they:
- Ask a completely different question (e.g., "what materials do you have?" when asked for height)
- Ask about pricing/cost when we're collecting info
- Ask general questions about the service/product
- Ask "tell me about X" or "what is X"
- Ask clarification about something OTHER than the current question

The user is NOT going sideways (return false) if they:
- Provide an answer to the question (even if informal)
- Ask clarification about the CURRENT question (e.g., "what do you mean by height?")
- Give a partial answer or express uncertainty but attempt to answer
- Say they don't know or want to skip (this is still engaging with the question)

Examples:
Pending question: "What height do you need?"
- "what materials do you offer?" → {"is_sideways": true}
- "3 meters" → {"is_sideways": false}
- "not sure, maybe 2m?" → {"is_sideways": false}
- "what do you mean by height?" → {"is_sideways": false} (clarification of current question)
- "how much will this cost?" → {"is_sideways": true}
- "tell me about your company" → {"is_sideways": true}
- "I don't know" → {"is_sideways": false} (engaging with the question)"""
                    },
                    {
                        "role": "user",
                        "content": f"Pending question: '{expected_question}'\nExpected type: {expected_type}\nUser said: '{user_message}'"
                    }
                ],
                temperature=0,
                response_format={"type": "json_object"},
                max_tokens=50
            )
            
            result = json.loads(response.choices[0].message.content)
            is_sideways = result.get('is_sideways', False)
            
            if is_sideways:
                print(f"User going sideways: '{user_message}' when expecting {expected_type}")
            
            return is_sideways
        except Exception as e:
            print(f"Error checking sideways: {str(e)}")
            return False  # Default to not sideways to avoid blocking valid answers
    
    def _answer_sideways_question(self, question: str, enquiry: Enquiry, db: Session) -> str:
        """Answer user's sideways question briefly using KB and AI"""
        try:
            # Search KB for relevant info
            kb_context = self._search_knowledge_base(question)
            
            # Build conversation context
            conversation_context = ""
            if enquiry.messages:
                recent_msgs = enquiry.messages[-3:]
                for msg in recent_msgs:
                    conversation_context += f"{msg.role}: {msg.content}\n"
            
            # Use AI to generate brief, helpful answer
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are answering a customer's side question during a quote collection process.

Be helpful but BRIEF (2-3 sentences maximum). Answer their question directly.

Recent conversation context:
{conversation_context}

Knowledge base context:
{kb_context if kb_context else "No specific KB info found"}

After you answer, the system will automatically redirect them back to the pending quote question."""
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            answer = response.choices[0].message.content.strip()
            print(f"Sideways answer generated: {answer[:100]}...")
            return answer
            
        except Exception as e:
            print(f"Error answering sideways question: {str(e)}")
            return "I'd be happy to help with that! However, let's complete your quote first so I can give you accurate information."
    
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
    
    def _rephrase_question_naturally(
        self,
        question: str,
        question_type: str,
        choices: Optional[List[str]] = None,
        service_name: str = "",
        conversation_context: str = ""
    ) -> str:
        """Rephrase a decision tree question naturally using AI"""
        try:
            # Build context for AI
            context_parts = []
            if service_name:
                context_parts.append(f"Service: {service_name}")
            if conversation_context:
                context_parts.append(f"Recent context: {conversation_context}")
            
            context_str = " | ".join(context_parts) if context_parts else "Starting conversation"
            
            # Build choices text
            choices_text = ""
            if choices and question_type == "choice":
                choices_text = f"\nAvailable options: {', '.join(choices)}"
            elif question_type == "boolean":
                choices_text = "\nExpecting: Yes/No answer"
            elif question_type == "number":
                choices_text = "\nExpecting: Numeric value"
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a friendly, professional sales assistant for Ezzo Sales.

Rephrase the given question to sound natural, warm, and conversational while maintaining professionalism.

Guidelines:
- Be friendly but professional
- Use transitional phrases like "Great!", "Perfect", "Wonderful"
- If options are provided, naturally mention them
- Keep it concise (1-2 sentences max)
- Sound like a helpful salesperson, not a form
- Don't be overly formal or robotic

Examples:
- "What is the total ladder height (in meters)?" → "Great! Could you let me know the total height of the ladder you need?"
- "What material do you prefer for the ladder? Options: SS304, HDG, Aluminum" → "Perfect. What material would work best for you? We offer Stainless Steel (SS304), Galvanized Mild Steel (HDG), and Aluminum."
- "Do you require shop drawings?" → "Would you like us to provide shop drawings for review and approval?"

Return ONLY the rephrased question, nothing else."""
                    },
                    {
                        "role": "user",
                        "content": f"Context: {context_str}\n\nRephrase this question naturally:\n{question}{choices_text}"
                    }
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            rephrased = response.choices[0].message.content.strip()
            
            # If choices exist and weren't mentioned, add them at the end
            if choices and question_type == "choice" and not any(choice.lower() in rephrased.lower() for choice in choices):
                rephrased += f"\n\nOptions: {', '.join(choices)}"
            
            return rephrased
            
        except Exception as e:
            print(f"Error rephrasing question: {str(e)}")
            # Fallback to original question
            if choices:
                return f"{question}\n\nOptions: {', '.join(choices)}"
            return question
    
    def _extract_conversation_context(
        self,
        enquiry: Enquiry,
        tree: DecisionTree
    ) -> Dict[str, Any]:
        """Extract pre-filled data from conversation history using AI"""
        try:
            # Build conversation text
            conversation_text = f"Initial request: {enquiry.initial_message}\n\n"
            for msg in enquiry.messages:
                conversation_text += f"{msg.role}: {msg.content}\n"
            
            # Get decision tree questions for reference
            questions = tree.tree_config.get('questions', [])
            question_list = []
            for q in questions:
                q_dict = {
                    'id': q.get('id'),
                    'question': q.get('question'),
                    'type': q.get('type')
                }
                question_list.append(q_dict)
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are extracting information from a conversation to pre-fill a quotation form.

Decision Tree Questions:
{json.dumps(question_list, indent=2)}

Analyze the conversation and extract answers for any questions that were already discussed.

Return JSON with:
- For each question ID where information is available: {{ "question_id": {{"value": "extracted_answer", "confidence": 0-100, "source": "quote from conversation"}} }}
- Only include questions where the answer is CLEARLY stated
- Use exact question IDs from the list above
- For numeric answers, extract the number
- For choice answers, match to the closest option
- For text answers, extract the relevant information

Example:
If conversation mentions "5 meter ladder" and there's a "ladder_height" question, return:
{{ "ladder_height": {{"value": 5, "confidence": 95, "source": "5 meter ladder"}} }}

Return empty object {{}} if no clear information found."""
                    },
                    {
                        "role": "user",
                        "content": f"Conversation:\n{conversation_text}\n\nExtract information for the decision tree questions."
                    }
                ],
                temperature=0,
                response_format={"type": "json_object"},
                max_tokens=500
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Convert to simple dict of question_id: value
            extracted_data = {}
            for q_id, data in result.items():
                if isinstance(data, dict) and 'value' in data:
                    extracted_data[q_id] = {
                        'value': data['value'],
                        'from_context': True,
                        'confirmed': False,
                        'confidence': data.get('confidence', 0),
                        'source': data.get('source', '')
                    }
            
            return extracted_data
            
        except Exception as e:
            print(f"Error extracting conversation context: {str(e)}")
            return {}
    
    def _confirm_context_value(
        self,
        question: str,
        context_value: Any,
        context_source: str = ""
    ) -> str:
        """Generate a natural confirmation message for context-extracted values"""
        try:
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a friendly sales assistant confirming information with a customer.

Generate a natural confirmation question that:
1. Mentions what you understood from the conversation
2. Asks if that's correct
3. Sounds warm and professional
4. Gives them a chance to correct if needed

Examples:
- Question: "What is the ladder height?" | Value: 5 | Source: "5 meter ladder"
  → "I see you mentioned a 5 meter ladder earlier - is that the total height you need?"

- Question: "What material?" | Value: "Aluminum" | Source: "aluminum ladder"
  → "Just to confirm, you'd like this in Aluminum, correct?"

- Question: "Location" | Value: "Singapore" | Source: "site in Singapore"
  → "And this will be installed in Singapore, right?"

Return ONLY the confirmation question."""
                    },
                    {
                        "role": "user",
                        "content": f"Question: {question}\nValue from conversation: {context_value}\nSource: {context_source}\n\nGenerate confirmation question."
                    }
                ],
                temperature=0.7,
                max_tokens=100
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            print(f"Error generating confirmation: {str(e)}")
            # Fallback
            return f"I understood from our conversation that the answer is: {context_value}. Is that correct?"
    
    def analyze_image(self, image_path: str, context: str = "") -> str:
        """Analyze an image using GPT-4o Vision with a sales-lead focus.
        - Ignore OS/toolbars/browser chrome and any UI that is not relevant to quoting.
        - If the image appears unrelated to a product/site (e.g., a desktop screenshot), state that succinctly
          and ask for a photo relevant to the requested service.
        - Otherwise, return a concise, sales-focused assessment with actionable next steps.
        """
        import base64
        from pathlib import Path
        
        try:
            # Read and encode image
            with open(image_path, "rb") as image_file:
                image_data = base64.b64encode(image_file.read()).decode('utf-8')
            
            # Determine image type
            image_ext = Path(image_path).suffix.lower()
            mime_type = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.gif': 'image/gif',
                '.webp': 'image/webp'
            }.get(image_ext, 'image/jpeg')
            
            # Build a strict, sales-oriented system instruction
            system_msg = (
                "You are a sales estimator for Ezzo Sales. "
                "Given an image and short context, respond only with information useful for a sales lead/quotation. "
                "Strictly ignore and do NOT describe OS UI, browser toolbars, docks, status bars, or unrelated UI elements. "
                "If the image is not relevant to a product/site for quotation (e.g., a computer screenshot), reply briefly: "
                "'This image doesn't appear relevant for a quotation. Please upload a photo of the site/product relevant to <service>.' "
                "Otherwise provide: 1) Lead summary (1 line), 2) Observations that affect pricing (3-5 bullets), 3) Next questions (max 3). "
                "Keep it under 120 words. Professional, specific, sales-focused."
            )
            
            # Compose a user prompt using the provided context (may include caption/service)
            prompt = (
                f"Context: {context}\n"
                "Analyze the attached image strictly for sales/quotation relevance only."
            )
            
            # Call GPT-4 Vision
            response = self.client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {"role": "system", "content": system_msg},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{image_data}"}},
                        ],
                    },
                ],
                max_tokens=350,
                temperature=0.4,
            )
            
            analysis = response.choices[0].message.content
            print(f"Image analysis complete: {len(analysis)} chars")
            return analysis
            
        except Exception as e:
            print(f"Error analyzing image: {str(e)}")
            import traceback
            traceback.print_exc()
            return (
                "Thanks for the image. I couldn't analyze it right now; please try again or upload a photo "
                "that clearly shows the product/site for quotation."
            )


# Singleton instance
ai_assistant = AIAssistant()
