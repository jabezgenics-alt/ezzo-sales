from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI
from sqlalchemy.orm import Session
import json
import re
from app.config import settings
from app.models import Enquiry, KnowledgeChunk
from app.services.vector_store import vector_store


class AIPricingService:
    """AI-powered pricing decisions to replace hardcoded logic"""
    
    def __init__(self):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    def classify_service_type(self, item_name: str, collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to classify service type and extract relevant information"""
        try:
            # Build context for AI
            context_parts = [item_name]
            if collected_data.get('material'):
                context_parts.append(f"Material: {collected_data['material']}")
            if collected_data.get('special_features'):
                features = collected_data['special_features']
                if isinstance(features, list):
                    context_parts.append(f"Features: {', '.join(features)}")
                else:
                    context_parts.append(f"Features: {features}")
            
            context = " ".join(context_parts)
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at classifying construction and renovation services.

Classify the service and extract relevant information from the context.

Return JSON with these fields:
- service_category: One of ["flooring", "painting", "electrical", "plumbing", "construction", "safety", "court_markings", "other"]
- is_area_based: boolean - whether pricing is typically per area (sqft/sqm)
- is_height_based: boolean - whether pricing is typically per height/meter
- is_unit_based: boolean - whether pricing is typically per unit/item
- preferred_unit: The most common pricing unit for this service (e.g., "per sqft", "per sqm", "per meter", "per unit")
- material_specific: boolean - whether material choice significantly affects pricing
- complexity_factors: array of factors that affect pricing complexity

Examples:
- "parquet sanding and varnishing" → {"service_category": "flooring", "is_area_based": true, "preferred_unit": "per sqft", ...}
- "cat ladder installation" → {"service_category": "safety", "is_height_based": true, "preferred_unit": "per meter", ...}
- "basketball court markings" → {"service_category": "court_markings", "is_unit_based": true, "preferred_unit": "per court", ...}"""
                    },
                    {
                        "role": "user",
                        "content": f"Classify this service: {context}"
                    }
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"Error classifying service: {str(e)}")
            # Fallback classification
            return {
                "service_category": "other",
                "is_area_based": False,
                "is_height_based": False,
                "is_unit_based": True,
                "preferred_unit": "per unit",
                "material_specific": False,
                "complexity_factors": []
            }
    
    def analyze_pricing_chunks(self, chunks: List[Dict], service_info: Dict[str, Any], collected_data: Dict[str, Any]) -> Dict[str, Any]:
        """Use AI to analyze pricing chunks and select the best option"""
        try:
            # Prepare chunk information for AI
            chunk_summaries = []
            for i, chunk in enumerate(chunks):
                content = chunk.get('content', '')
                metadata = chunk.get('metadata', {})
                price = metadata.get('base_price') or metadata.get('price', 0)
                price_unit = metadata.get('price_unit', 'unknown')
                
                # Use FULL content for better AI analysis, especially for multi-option pricing documents
                chunk_summaries.append({
                    "index": i,
                    "price": price,
                    "price_unit": price_unit,
                    "full_content": content,  # Send full content to AI
                    "document_name": metadata.get('document_name', 'Unknown')
                })
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an expert at selecting the most appropriate pricing from multiple options.

Service Information:
- Category: {service_info.get('service_category', 'unknown')}
- Preferred Unit: {service_info.get('preferred_unit', 'per unit')}
- Area Based: {service_info.get('is_area_based', False)}
- Height Based: {service_info.get('is_height_based', False)}
- Material Specific: {service_info.get('material_specific', False)}

Customer Requirements:
- Material: {collected_data.get('material', 'not specified')}
- Area: {collected_data.get('total_area', collected_data.get('area', 'not specified'))}
- Height: {collected_data.get('ladder_height', collected_data.get('height', 'not specified'))}
- Features: {collected_data.get('special_features', 'not specified')}

Analyze the FULL CONTENT of each pricing option (not just metadata) and select the BEST match.

**IMPORTANT**: If a document contains multiple material/product options (e.g., "SS304 ladder", "Alum ladder", "Galvanized ladder"), 
you MUST look inside the full content and extract the pricing for the SPECIFIC material the customer requested.
Do NOT just use the metadata price - read the full content to find the exact match.

Selection Criteria (in priority order):
1. **Material/Product Match**: If customer specified a material (e.g., "Stainless Steel", "SS304"), find the EXACT pricing for that material in the content
2. Unit compatibility (preferred_unit should match or be convertible)
3. Service category relevance
4. Price reasonableness (not unrealistically high/low)
5. Document credibility

Return JSON with:
- selected_index: index of the best pricing option (the document/chunk that contains the right material)
- selected_material_price: the ACTUAL price for the customer's material (extracted from content)
- selected_material_unit: the unit for that specific material
- confidence_score: 0-100 confidence in the selection
- reasoning: explanation of why this option was selected and which material price you extracted
- unit_conversion_needed: boolean - whether unit conversion is required
- conversion_factor: number to multiply price by (if conversion needed)
- final_unit: the unit to use in the final quote

If no suitable option exists, return selected_index: -1 with reasoning."""
                    },
                    {
                        "role": "user",
                        "content": f"Select the best pricing option from these {len(chunk_summaries)} options:\n\n" + 
                                 "\n\n".join([f"Option {i+1}:\nMetadata: ${chunk['price']} {chunk['price_unit']} (from {chunk['document_name']})\nFull Content:\n{chunk['full_content']}\n---" 
                                          for i, chunk in enumerate(chunk_summaries)])
                    }
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            return result
            
        except Exception as e:
            print(f"Error analyzing pricing chunks: {str(e)}")
            # Fallback: select first chunk
            return {
                "selected_index": 0 if chunks else -1,
                "confidence_score": 50,
                "reasoning": "Fallback selection due to AI error",
                "unit_conversion_needed": False,
                "conversion_factor": 1.0,
                "final_unit": "per unit"
            }
    
    def extract_pricing_adjustments(self, selected_chunk: Dict, service_info: Dict[str, Any], collected_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Use AI to extract pricing adjustments from document content"""
        try:
            content = selected_chunk.get('content', '')
            metadata = selected_chunk.get('metadata', {})
            
            # Build context about customer's selections
            customer_context = []
            if collected_data.get('material'):
                customer_context.append(f"Customer's material choice: {collected_data['material']}")
            if collected_data.get('ladder_material'):
                customer_context.append(f"Customer's ladder material: {collected_data['ladder_material']}")
            if collected_data.get('safety_cage') is not None:
                customer_context.append(f"Customer requires safety cage: {collected_data['safety_cage']}")
            if collected_data.get('shop_drawings') is not None:
                customer_context.append(f"Customer requires shop drawings: {collected_data['shop_drawings']}")
            if collected_data.get('pe_endorsement') is not None:
                customer_context.append(f"Customer requires PE endorsement: {collected_data['pe_endorsement']}")
            if collected_data.get('additional_features'):
                customer_context.append(f"Customer's additional features: {collected_data['additional_features']}")
            
            customer_context_str = "\n".join(customer_context) if customer_context else "No specific selections available"
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert at extracting pricing adjustments and conditions from construction documents.

**CRITICAL RULES**:
1. The BASE PRICE has already been selected and applied - DO NOT add it again as an adjustment
2. Only extract ADDITIONAL charges beyond the base price
3. Only extract adjustments RELEVANT to the customer's specific selections

Customer Context:
{customer_context}

**Understanding Pricing Structures**:
- If document says "SS304 ladder w/ cage: $1050/m run + $200/cage rung", this means:
  - $1050/m is the BASE PRICE (already applied)
  - $200/cage rung is an ADDITIONAL charge per rung (only add if customer needs cage rungs)
- DO NOT add the base material price as an adjustment - it's already been applied!

If the document lists multiple material options:
- ONLY extract adjustments for the material the customer selected
- DO NOT include base prices or adjustments for other materials

Look for ADDITIONAL charges only:
1. Per-unit add-ons (e.g., cage rungs, access doors) - ONLY if customer explicitly requested them
2. Optional services (shop drawings, PE certification) - ONLY if customer said YES or true
3. Delivery, installation, special requirements - if applicable
4. GST/tax information (will be calculated separately)

DO NOT extract as adjustments:
- The base price per meter/unit (already applied)
- The material cost itself (already applied)
- Charges for materials customer didn't choose
- Optional services customer declined (e.g., if "shop drawings: false", DO NOT add shop drawings)

Return JSON with:
- adjustments: array of adjustment objects with keys: description, amount, type ("fixed" or "percentage"), applies_to ("base" or "total")
  - Each description should be clear and specific
  - DO NOT duplicate the base price
- conditions: array of condition strings
- gst_rate: GST rate if mentioned (default to 0.09 for Singapore)
- gst_included: boolean - whether GST is included in base price

Only extract adjustments that are:
1. Explicitly mentioned in the document content
2. ADDITIONAL to the base price (not the base price itself)
3. RELEVANT to the customer's specific selections and requirements

**Critical Examples**:
- If customer context shows "shop drawings: false" → DO NOT add shop drawings adjustment
- If customer context shows "shop drawings: true" → ADD shop drawings adjustment
- If customer context shows "additional_features: Yes, simple access door" → ADD access door adjustment
- If customer context shows "material: SS304" and document lists "SS304 cage rung: $200" → ADD that rung cost
- If customer context shows "material: SS304" and document lists "Alum cage rung: $125" → DO NOT add Alum rung"""
                    },
                    {
                        "role": "user",
                        "content": f"Customer Context:\n{customer_context_str}\n\nDocument Content:\n{content}\n\nExtract ONLY the adjustments relevant to this customer's selections."
                    }
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Ensure GST is always included
            if not result.get('gst_rate'):
                result['gst_rate'] = 0.09  # Singapore GST
            
            return result
            
        except Exception as e:
            print(f"Error extracting adjustments: {str(e)}")
            # Fallback: just GST
            return {
                "adjustments": [],
                "conditions": [],
                "gst_rate": 0.09,
                "gst_included": False
            }
    
    def determine_quantity_and_unit(self, collected_data: Dict[str, Any], service_info: Dict[str, Any]) -> Tuple[float, str]:
        """Use AI to determine the correct quantity and unit from collected data"""
        try:
            # Build context
            context_parts = []
            if collected_data.get('total_area'):
                context_parts.append(f"Total area: {collected_data['total_area']}")
            if collected_data.get('area'):
                context_parts.append(f"Area: {collected_data['area']}")
            if collected_data.get('quantity_or_area'):
                context_parts.append(f"Quantity/Area: {collected_data['quantity_or_area']}")
            if collected_data.get('ladder_height'):
                context_parts.append(f"Ladder height: {collected_data['ladder_height']}")
            if collected_data.get('height'):
                context_parts.append(f"Height: {collected_data['height']}")
            if collected_data.get('quantity'):
                context_parts.append(f"Quantity: {collected_data['quantity']}")
            
            context = " ".join(context_parts) if context_parts else "No quantity information provided"
            
            response = self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": f"""You are an expert at parsing quantity and unit information for construction services.

Service Information:
- Category: {service_info.get('service_category', 'unknown')}
- Preferred Unit: {service_info.get('preferred_unit', 'per unit')}
- Area Based: {service_info.get('is_area_based', False)}
- Height Based: {service_info.get('is_height_based', False)}

Extract the quantity and determine the appropriate unit.

Return JSON with:
- quantity: numeric value (float)
- unit: the unit to use (e.g., "sqft", "sqm", "meter", "unit", "court")
- confidence: 0-100 confidence in the parsing
- reasoning: explanation of the parsing decision

Rules:
- For area-based services, prefer sqft over sqm if both are mentioned
- For height-based services, convert to meters
- For unit-based services, use "unit" or "court" as appropriate
- If multiple values are provided, use the most specific one
- Default to quantity=1, unit="unit" if unclear"""
                    },
                    {
                        "role": "user",
                        "content": f"Parse quantity and unit from: {context}"
                    }
                ],
                temperature=0,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            try:
                quantity = float(result.get('quantity', 1))
                unit = result.get('unit', 'unit')
                return quantity, unit
            except (ValueError, TypeError):
                return 1.0, 'unit'
                
        except Exception as e:
            print(f"Error determining quantity/unit: {str(e)}")
            return 1.0, 'unit'
    
    def calculate_final_pricing(self, base_price: float, quantity: float, unit: str, adjustments: List[Dict], gst_rate: float) -> Dict[str, Any]:
        """Calculate final pricing with AI-determined adjustments"""
        try:
            # Calculate subtotal
            subtotal = base_price * quantity
            
            # Apply adjustments
            total_adjustments = 0
            adjustment_details = []
            
            for adj in adjustments:
                adj_amount = adj.get('amount', 0)
                adj_type = adj.get('type', 'fixed')
                adj_applies_to = adj.get('applies_to', 'base')
                
                if adj_type == 'fixed':
                    if adj_applies_to == 'base':
                        subtotal += adj_amount
                    else:  # applies_to == 'total'
                        total_adjustments += adj_amount
                elif adj_type == 'percentage':
                    if adj_applies_to == 'base':
                        subtotal += (subtotal * adj_amount / 100)
                    else:  # applies_to == 'total'
                        total_adjustments += (subtotal * adj_amount / 100)
                
                adjustment_details.append({
                    'description': adj.get('description', 'Adjustment'),
                    'amount': adj_amount if adj_type == 'fixed' else f"{adj_amount}%",
                    'type': adj_type
                })
            
            # Add GST
            gst_amount = subtotal * gst_rate
            total_price = subtotal + total_adjustments + gst_amount
            
            return {
                'subtotal': round(subtotal, 2),
                'adjustments': adjustment_details,
                'gst_amount': round(gst_amount, 2),
                'total_price': round(total_price, 2),
                'gst_rate': gst_rate
            }
            
        except Exception as e:
            print(f"Error calculating final pricing: {str(e)}")
            # Fallback calculation
            subtotal = base_price * quantity
            gst_amount = subtotal * gst_rate
            total_price = subtotal + gst_amount
            
            return {
                'subtotal': round(subtotal, 2),
                'adjustments': [],
                'gst_amount': round(gst_amount, 2),
                'total_price': round(total_price, 2),
                'gst_rate': gst_rate
            }


# Singleton instance
ai_pricing_service = AIPricingService()
