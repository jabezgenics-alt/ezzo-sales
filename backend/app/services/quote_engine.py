from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models import Enquiry, KnowledgeChunk, Quote
from app.services.vector_store import vector_store
from app.services.ai_pricing_service import ai_pricing_service
from app.schemas import QuoteAdjustment, DraftQuotePreview


class QuoteCalculationEngine:
    """Calculate quotes based on KB data and customer requirements"""
    
    def __init__(self):
        # Minimal configuration - AI will handle most decisions
        self.config = {
            'default_item_name': 'Unknown Item',
            'default_quantity': 1,
            'default_unit': 'unit',
            'default_base_price': 0,
            'max_price_threshold': 10000,
            'search_limit': 10,
            'pricing_not_available': 'Pricing Not Available',
            'gst_notice': 'Price includes GST'
        }
    
    def _calculate_ai_driven_quote(
        self,
        db: Session,
        enquiry: Enquiry,
        collected: Dict[str, Any]
    ) -> DraftQuotePreview:
        """Calculate quote using AI-driven decisions instead of hardcoded logic"""
        
        # Step 1: Classify the service using AI
        item_name = collected.get('item', self.config['default_item_name'])
        service_info = ai_pricing_service.classify_service_type(item_name, collected)
        
        print(f"AI Service Classification: {service_info}")
        
        # Step 2: Determine quantity and unit using AI
        quantity, unit = ai_pricing_service.determine_quantity_and_unit(collected, service_info)
        
        print(f"AI Quantity/Unit Determination: {quantity} {unit}")
        
        # Step 3: Search for relevant pricing chunks with enhanced query building
        # Build multiple search variations to maximize chances of finding relevant data
        search_queries = [item_name]
        
        # Add query with material
        if collected.get('material'):
            search_queries.append(f"{item_name} {collected['material']}")
        
        # Add query with area/service type
        if collected.get('area_service_type'):
            search_queries.append(f"{item_name} {collected['area_service_type']}")
        
        # Add comprehensive query
        comprehensive_query = item_name
        if collected.get('material'):
            comprehensive_query += f" {collected['material']}"
        if collected.get('special_features'):
            features = collected['special_features']
            if isinstance(features, list):
                comprehensive_query += " " + " ".join(features)
        search_queries.append(comprehensive_query)
        
        # Search with all queries and combine results
        all_chunks = []
        seen_chunk_ids = set()
        for query in search_queries:
            chunks = self._find_relevant_chunks(db, query)
            for chunk in chunks:
                chunk_id = chunk.get('id') or str(chunk.get('content', ''))[:50]
                if chunk_id not in seen_chunk_ids:
                    seen_chunk_ids.add(chunk_id)
                    all_chunks.append(chunk)
        
        relevant_chunks = all_chunks[:self.config['search_limit']]  # Limit total results
        
        if not relevant_chunks:
            return self._empty_quote(f"No pricing information found for {item_name}")
        
        # Step 4: Use AI to analyze and select the best pricing option
        pricing_analysis = ai_pricing_service.analyze_pricing_chunks(relevant_chunks, service_info, collected)
        
        print(f"AI Pricing Analysis: {pricing_analysis}")
        
        if pricing_analysis['selected_index'] == -1:
            return self._empty_quote(f"No suitable pricing found for {item_name}")
        
        # Get the selected chunk
        selected_chunk = relevant_chunks[pricing_analysis['selected_index']]
        selected_metadata = selected_chunk.get('metadata', {})
        
        # Use AI-extracted material-specific price if available (for multi-option documents)
        if pricing_analysis.get('selected_material_price'):
            base_price = float(pricing_analysis['selected_material_price'])
            if pricing_analysis.get('selected_material_unit'):
                unit = pricing_analysis['selected_material_unit']
        else:
            # Fallback to metadata price
            base_price = float(selected_metadata.get('base_price') or selected_metadata.get('price', 0))
        
        # Apply unit conversion if needed
        if pricing_analysis.get('unit_conversion_needed', False):
            conversion_factor = pricing_analysis.get('conversion_factor', 1.0)
            base_price = base_price * conversion_factor
            unit = pricing_analysis.get('final_unit', unit)
        
        # Step 5: Extract adjustments using AI
        adjustment_data = ai_pricing_service.extract_pricing_adjustments(selected_chunk, service_info, collected)
        
        # Step 6: Calculate final pricing
        pricing_calculation = ai_pricing_service.calculate_final_pricing(
            base_price, quantity, unit, adjustment_data.get('adjustments', []), adjustment_data.get('gst_rate', 0.09)
        )
        
        # Convert adjustments to QuoteAdjustment objects
        adjustments = []
        for adj in pricing_calculation['adjustments']:
            adjustments.append(QuoteAdjustment(
                description=adj['description'],
                amount=float(adj['amount']) if isinstance(adj['amount'], (int, float)) else 0,
                type=adj['type']
            ))
        
        # Add GST as adjustment
        if pricing_calculation['gst_amount'] > 0:
            adjustments.append(QuoteAdjustment(
                description=f"GST ({pricing_calculation['gst_rate']*100:.0f}%)",
                amount=pricing_calculation['gst_amount'],
                type="fixed"
            ))
        
        # Get conditions from AI analysis
        conditions = adjustment_data.get('conditions', [])
        conditions.append(self.config['gst_notice'])
        
        # Get source references
        source_refs = []
        for chunk in relevant_chunks[:3]:
            metadata = chunk.get('metadata', {})
            source = metadata.get('source') or metadata.get('document_name', 'Knowledge Base')
            if source not in source_refs:
                source_refs.append(source)
        
        return DraftQuotePreview(
            item_name=item_name,
            base_price=base_price,
            unit=unit,
            quantity=quantity,
            adjustments=adjustments,
            total_price=pricing_calculation['total_price'],
            conditions=conditions,
            source_references=source_refs,
            missing_info=[],
            can_submit=True
        )
    
    def calculate_draft_quote(
        self,
        db: Session,
        enquiry: Enquiry
    ) -> DraftQuotePreview:
        """Calculate draft quote from enquiry using AI-driven decisions"""
        
        # Get collected data
        collected = enquiry.collected_data or {}
        
        # Check if this is from a decision tree
        if enquiry.service_tree_id:
            return self._calculate_from_tree(db, enquiry, collected)
        
        # Use AI-driven quote calculation instead of hardcoded logic
        return self._calculate_ai_driven_quote(db, enquiry, collected)
    
    def _calculate_from_tree(
        self,
        db: Session,
        enquiry: Enquiry,
        collected: Dict[str, Any]
    ) -> DraftQuotePreview:
        """Calculate quote from decision tree data using AI-driven decisions"""
        from app.models import DecisionTree
        
        # Get the tree
        tree = db.query(DecisionTree).filter(DecisionTree.id == enquiry.service_tree_id).first()
        if not tree:
            return self._empty_quote("Service tree not found")
        
        # Let AI dynamically map decision tree data to pricing format
        # No hardcoded values - AI figures out what to search for
        mapped_data = {
            'item': tree.display_name,  # Use display name as starting point
        }
        
        # Intelligently map area/quantity data
        if collected.get('total_area'):
            mapped_data['quantity_or_area'] = f"{collected['total_area']} sqm"
        
        # Intelligently map material/finish information
        if collected.get('varnish_type'):
            mapped_data['material'] = collected['varnish_type']
        
        # Build special features list from various tree fields
        special_features = []
        if collected.get('finish_type'):
            special_features.append(f"{collected['finish_type']} finish")
        if collected.get('area_service_type'):
            special_features.append(collected['area_service_type'])
        if special_features:
            mapped_data['special_features'] = special_features
        
        # Map location
        if collected.get('site_address'):
            mapped_data['location'] = collected['site_address']
        
        # Keep all original tree data for AI to use
        for key, value in collected.items():
            if key not in mapped_data and value:
                mapped_data[key] = value
        
        # Use AI-driven calculation - AI will search knowledge base and calculate pricing
        base_quote = self._calculate_ai_driven_quote(db, enquiry, mapped_data)
        
        # Apply auto-requirements from business rules
        auto_requirements = collected.get('auto_requirements', [])
        auto_conditions = collected.get('auto_conditions', [])
        
        if auto_requirements:
            base_quote = self._apply_auto_requirements(db, base_quote, auto_requirements, auto_conditions)
        
        return base_quote
    
    
    
    def _apply_auto_requirements(
        self,
        db: Session,
        base_quote: DraftQuotePreview,
        auto_requirements: List[Dict[str, Any]],
        auto_conditions: List[str]
    ) -> DraftQuotePreview:
        """Apply automatic requirements from business rules to the quote"""
        
        additional_adjustments = []
        additional_conditions = list(auto_conditions)  # Start with auto conditions
        
        for requirement in auto_requirements:
            item_name = requirement.get("item", "")
            search_terms = requirement.get("search_terms", [item_name])
            reason = requirement.get("reason", "")
            
            # Search knowledge base for pricing
            best_price = None
            best_unit = "unit"
            
            for search_term in search_terms:
                chunks = self._find_relevant_chunks(db, search_term)
                if chunks:
                    # Use the first relevant chunk
                    chunk = chunks[0]
                    metadata = chunk.get('metadata', {})
                    price = metadata.get('base_price') or metadata.get('price', 0)
                    
                    if price and (best_price is None or price < best_price):
                        best_price = float(price)
                        best_unit = metadata.get('price_unit', 'unit')
                        break
            
            if best_price:
                # Add as adjustment
                additional_adjustments.append(QuoteAdjustment(
                    description=f"{item_name.title()} (Required: {reason})",
                    amount=best_price,
                    type="fixed"
                ))
            else:
                # No pricing found, add as condition
                additional_conditions.append(f"{item_name.title()} required ({reason}) - pricing to be confirmed")
        
        # Recalculate total with GST on all items (base + original adjustments + auto requirements)
        # Remove GST from original adjustments to recalculate
        non_gst_adjustments = [adj for adj in base_quote.adjustments if 'GST' not in adj.description]
        all_non_gst_adjustments = non_gst_adjustments + additional_adjustments
        
        # Calculate subtotal (base + all non-GST adjustments)
        subtotal = base_quote.base_price * (base_quote.quantity or 1)
        for adj in all_non_gst_adjustments:
            subtotal += adj.amount
        
        # Get GST rate from business rules or fallback to extract from original adjustments
        gst_rate = self._get_gst_rate(db, base_quote)
        gst_amount = subtotal * gst_rate
        
        # Add GST adjustment
        final_adjustments = all_non_gst_adjustments + [QuoteAdjustment(
            description=f"GST ({int(gst_rate*100)}%)",
            amount=gst_amount,
            type="fixed"
        )]
        
        # Calculate final total
        total_price = subtotal + gst_amount
        
        # Update the quote with recalculated values
        updated_quote = DraftQuotePreview(
            item_name=base_quote.item_name,
            base_price=base_quote.base_price,
            unit=base_quote.unit,
            quantity=base_quote.quantity,
            adjustments=final_adjustments,
            total_price=round(total_price, 2),
            conditions=base_quote.conditions + additional_conditions,
            source_references=base_quote.source_references,
            missing_info=base_quote.missing_info,
            can_submit=base_quote.can_submit
        )
        
        return updated_quote
    
    def _get_gst_rate(self, db: Session, base_quote: DraftQuotePreview) -> float:
        """Get GST rate from business rules or extract from original quote (no hardcoded values)"""
        
        # Try to get GST rate from business rules
        from app.models import BusinessRule
        
        rules = db.query(BusinessRule).filter(
            BusinessRule.is_active == True,
            BusinessRule.region == 'SGP'
        ).first()
        
        if rules and rules.rule_config:
            gst_rate = rules.rule_config.get('gst_rate')
            if gst_rate:
                return float(gst_rate)
        
        # Fallback: Extract from original quote's GST adjustment
        for adj in base_quote.adjustments:
            if 'GST' in adj.description and '%' in adj.description:
                # Extract percentage from description like "GST (9%)"
                import re
                match = re.search(r'(\d+)%', adj.description)
                if match:
                    return float(match.group(1)) / 100
        
        # Last resort fallback: return 0.09 (Singapore standard)
        # This should ideally never be reached as GST should come from business rules
        return 0.09
    
    def _empty_quote(self, reason: str) -> DraftQuotePreview:
        """Return an empty quote with error message"""
        return DraftQuotePreview(
            item_name=self.config['pricing_not_available'],
            base_price=self.config['default_base_price'],
            unit=self.config['default_unit'],
            quantity=self.config['default_quantity'],
            adjustments=[],
            total_price=self.config['default_base_price'],
            conditions=[reason],
            source_references=[],
            missing_info=["Pricing information"],
            can_submit=False
        )
    
    def _find_relevant_chunks(
        self,
        db: Session,
        item_name: str
    ) -> List[Dict]:
        """Find all relevant chunks for an item from ChromaDB"""
        
        # Search vector store - this has all the data we need
        vector_results = vector_store.search(item_name, limit=self.config['search_limit'])
        
        if not vector_results:
            return []
        
        # Return ChromaDB results directly (they have all metadata)
        return vector_results
    
    

    
    
    
    
    
    def create_quote_from_draft(
        self,
        db: Session,
        enquiry_id: int,
        draft: DraftQuotePreview,
        source_chunk_ids: List[int]
    ) -> Quote:
        """Create a quote record from draft"""
        
        quote = Quote(
            enquiry_id=enquiry_id,
            item_name=draft.item_name,
            quantity=draft.quantity,
            unit=draft.unit,
            base_price=draft.base_price,
            adjustments=[adj.dict() for adj in draft.adjustments],
            total_price=draft.total_price,
            conditions=draft.conditions,
            source_chunks=source_chunk_ids,
            status="pending_admin"
        )
        
        db.add(quote)
        db.commit()
        db.refresh(quote)
        
        return quote


# Singleton instance
quote_engine = QuoteCalculationEngine()
