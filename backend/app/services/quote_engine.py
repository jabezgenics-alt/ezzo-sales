from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from app.models import Enquiry, KnowledgeChunk, Quote
from app.services.vector_store import vector_store
from app.schemas import QuoteAdjustment, DraftQuotePreview


class QuoteCalculationEngine:
    """Calculate quotes based on KB data and customer requirements"""
    
    def __init__(self):
        # Configuration values - can be overridden by knowledge base
        self.config = {
            'default_item_name': 'Unknown Item',
            'default_quantity': 1,
            'default_unit': 'unit',
            'default_base_price': 0,
            'max_price_threshold': 10000,
            'flooring_keywords': ['flooring', 'floor', 'parquet', 'hardwood', 'vinyl', 'tile', 'marble', 'terrazzo'],
            'search_limit': 10,
            'feet_to_meters': 0.3048,
            'rungs_per_meter': 2,
            'gst_rate': 0.09,
            'gst_multiplier': 1.09,
            'gst_description': 'GST (9%)',
            'gst_notice': 'Price includes 9% GST',
            'pricing_not_available': 'Pricing Not Available',
            'court_markings_default_unit': 'per court',
            'generic_tree_default_unit': 'per unit'
        }
        # Load configuration from knowledge base
        self._load_config_from_kb()
    
    def _load_config_from_kb(self):
        """Load configuration values from knowledge base"""
        try:
            # Search for configuration information
            config_results = vector_store.search("GST rate configuration pricing settings", limit=5)
            
            for result in config_results:
                content = result.get('content', '').lower()
                metadata = result.get('metadata', {})
                
                # Extract GST rate if found
                if 'gst' in content and '9%' in content:
                    # GST rate is already correct in config
                    pass
                
                # Extract other configuration values if present
                if 'max price' in content or 'price threshold' in content:
                    # Could extract price thresholds from KB if available
                    pass
                    
        except Exception as e:
            print(f"Error loading config from KB: {str(e)}")
            # Continue with default config
    
    def calculate_draft_quote(
        self,
        db: Session,
        enquiry: Enquiry
    ) -> DraftQuotePreview:
        """Calculate draft quote from enquiry"""
        
        # Get collected data
        collected = enquiry.collected_data or {}
        
        # Check if this is from a decision tree
        if enquiry.service_tree_id:
            return self._calculate_from_tree(db, enquiry, collected)
        
        # Legacy path: extract key information
        item_name = collected.get('item', self.config['default_item_name'])
        
        # Parse quantity_or_area field
        quantity_or_area = collected.get('quantity_or_area') or collected.get('quantity') or collected.get('area') or self.config['default_quantity']
        
        # Extract numeric value and unit from quantity_or_area
        import re
        quantity_str = str(quantity_or_area)
        area_match = re.search(r'(\d+(?:\.\d+)?)\s*(sqm|sq m|square meter|unit|bedroom)', quantity_str.lower())
        
        if area_match:
            quantity = float(area_match.group(1))
            quantity_unit = area_match.group(2)
            print(f"Parsed quantity: {quantity} {quantity_unit}")
        else:
            try:
                quantity = float(quantity_or_area)
                quantity_unit = None
            except (ValueError, TypeError):
                quantity = self.config['default_quantity']
                quantity_unit = None
        
        # Build search query with more context
        search_query = item_name
        if collected.get('material'):
            search_query += f" {collected['material']}"
        if collected.get('height'):
            search_query += f" {collected['height']}"
        if collected.get('special_features'):
            features = collected['special_features']
            if isinstance(features, list):
                search_query += " " + " ".join(features)
        
        print(f"Quote search query: {search_query}")
        
        # Search for relevant chunks with highest prices
        relevant_chunks = self._find_relevant_chunks(db, search_query)
        
        if not relevant_chunks:
            return DraftQuotePreview(
                item_name=item_name,
                base_price=self.config['default_base_price'],
                unit=self.config['default_unit'],
                quantity=quantity,
                adjustments=[],
                total_price=self.config['default_base_price'],
                conditions=["No pricing information available"],
                source_references=[],
                missing_info=["Pricing information"],
                can_submit=False
            )
        
        # Smart pricing: check if height-based calculation is needed
        height_spec = collected.get('height', '')
        calculated_price = self._calculate_height_based_pricing(relevant_chunks, collected)
        
        if calculated_price:
            # Use calculated per-meter pricing
            base_price = calculated_price['total_price']
            price_unit = self.config['default_unit']
            highest_chunk = calculated_price['source_chunk']
            print(f"Using height-based pricing: ${base_price} (breakdown: {calculated_price['breakdown']})")
        else:
            # Fall back to smart pricing logic - filter by relevance first
            chunks_with_prices = []
            for chunk in relevant_chunks:
                metadata = chunk.get('metadata', {})
                content = chunk.get('content', '').lower()
                
                # Only consider chunks that are actually relevant to the item
                if self._is_relevant_chunk(item_name, content):
                    price = metadata.get('base_price') or metadata.get('price', 0)
                    if price:
                        try:
                            price_val = float(price)
                            # Filter out unrealistic prices using config threshold
                            if price_val <= self.config['max_price_threshold']:
                                chunks_with_prices.append({'chunk': chunk, 'price': price_val})
                        except (ValueError, TypeError):
                            continue
            
            if not chunks_with_prices:
                # No relevant pricing found, use default
                base_price = self.config['default_base_price']
                price_unit = self.config['default_unit']
                highest_chunk = None
            else:
                # Get most relevant price (not necessarily highest)
                # For flooring, prefer per sqm pricing
                if any(keyword in item_name.lower() for keyword in self.config['flooring_keywords']):
                    # Look for per sqm pricing first
                    sqm_chunks = [c for c in chunks_with_prices if 'sqm' in c['chunk'].get('content', '').lower() or 'per sqm' in c['chunk'].get('content', '').lower()]
                    if sqm_chunks:
                        selected = max(sqm_chunks, key=lambda x: x['price'])
                    else:
                        selected = max(chunks_with_prices, key=lambda x: x['price'])
                else:
                    # For other services, use highest relevant price
                    selected = max(chunks_with_prices, key=lambda x: x['price'])
                
                highest_chunk = selected['chunk']
                chunk_price = selected['price']
                chunk_metadata = highest_chunk.get('metadata', {})
                price_unit = chunk_metadata.get('price_unit', self.config['default_unit'])
                
                # Check if the chunk has an area/quantity that we need to scale from
                chunk_content = highest_chunk.get('content', '').lower()
                chunk_area_match = re.search(r'(\d+(?:\.\d+)?)\s*sqm', chunk_content)
                
                if chunk_area_match and quantity_unit in ['sqm', 'sq m', 'square meter']:
                    # Found reference area in chunk - calculate per sqm rate
                    chunk_area = float(chunk_area_match.group(1))
                    per_sqm_rate = chunk_price / chunk_area
                    base_price = per_sqm_rate
                    price_unit = 'sqm'
                    print(f"Calculated per sqm rate: ${per_sqm_rate:.2f} (${chunk_price} for {chunk_area} sqm)")
                else:
                    # Use chunk price as-is
                    base_price = chunk_price
        
        # Calculate adjustments
        adjustments = self._calculate_adjustments(collected, base_price)
        
        # Calculate total
        total_price = self._calculate_total(base_price, quantity, adjustments)
        
        # Get conditions
        conditions = self._extract_conditions(highest_chunk, collected)
        
        # Get source references from ChromaDB metadata
        source_refs = []
        for chunk in relevant_chunks:
            metadata = chunk.get('metadata', {})
            doc_name = metadata.get('document_name', 'Unknown')
            source = metadata.get('source', doc_name)
            source_refs.append(source)
        
        # Check for missing information
        missing_info = self._check_missing_info(collected)
        
        return DraftQuotePreview(
            item_name=item_name,
            base_price=base_price,
            unit=price_unit,
            quantity=quantity,
            adjustments=adjustments,
            total_price=total_price,
            conditions=conditions,
            source_references=source_refs,
            missing_info=missing_info,
            can_submit=len(missing_info) == 0
        )
    
    def _calculate_from_tree(
        self,
        db: Session,
        enquiry: Enquiry,
        collected: Dict[str, Any]
    ) -> DraftQuotePreview:
        """Calculate quote from decision tree data"""
        from app.models import DecisionTree
        
        # Get the tree
        tree = db.query(DecisionTree).filter(DecisionTree.id == enquiry.service_tree_id).first()
        if not tree:
            return self._empty_quote("Service tree not found")
        
        service_name = tree.service_name
        
        # Build item name and search query based on service type
        if service_name == 'court_markings':
            return self._calculate_court_markings(db, collected)
        else:
            # Generic tree-based calculation
            return self._calculate_generic_tree(db, tree, collected)
    
    def _calculate_court_markings(
        self,
        db: Session,
        collected: Dict[str, Any]
    ) -> DraftQuotePreview:
        """Calculate court markings quote from tree data"""
        
        court_type = collected.get('court_type', 'Unknown')
        
        # Build descriptive item name
        item_parts = [court_type, "Court Markings"]
        
        # Add court-specific details
        if court_type == 'Basketball':
            size = collected.get('basketball_size', '')
            need_3pt = collected.get('need_3pt_line', False)
            
            if size:
                item_parts.insert(1, size)
            
            search_query = f"{court_type} court markings {size}"
            if need_3pt:
                search_query += " 3-point line"
                item_parts.append("with 3-point line")
            else:
                search_query += " no 3-point line"
        
        elif court_type == 'Pickleball':
            num_courts = collected.get('pickleball_courts', self.config['default_quantity'])
            item_parts.insert(1, f"{num_courts}x")
            search_query = f"pickleball court markings {num_courts} courts"
        
        elif court_type == 'Tennis':
            num_courts = collected.get('tennis_courts', self.config['default_quantity'])
            item_parts.insert(1, f"{num_courts}x")
            search_query = f"tennis court markings {num_courts} courts"
        
        else:
            search_query = f"{court_type} court markings"
        
        item_name = " ".join(item_parts)
        
        print(f"Court Markings Quote - Item: {item_name}")
        print(f"Search query: {search_query}")
        print(f"Collected data: {collected}")
        
        # Search for pricing in knowledge base
        relevant_chunks = self._find_relevant_chunks(db, search_query)
        
        if not relevant_chunks:
            print(f"No pricing found for: {search_query}")
            return self._empty_quote(f"No pricing found for {item_name}")
        
        # Extract pricing from chunks
        chunks_with_prices = []
        for chunk in relevant_chunks:
            metadata = chunk.get('metadata', {})
            price = metadata.get('base_price') or metadata.get('price', 0)
            if price:
                try:
                    chunks_with_prices.append({
                        'chunk': chunk,
                        'price': float(price),
                        'content': chunk.get('content', '')
                    })
                    print(f"Found price: ${price} - {chunk.get('content', '')[:100]}")
                except (ValueError, TypeError):
                    continue
        
        if not chunks_with_prices:
            print(f"No valid prices in chunks")
            return self._empty_quote(f"Pricing not available for {item_name}")
        
        # Get highest price (most comprehensive option)
        highest = max(chunks_with_prices, key=lambda x: x['price'])
        highest_chunk = highest['chunk']
        base_price = highest['price']
        price_unit = highest_chunk.get('metadata', {}).get('price_unit', self.config['court_markings_default_unit'])
        
        print(f"Selected price: ${base_price} {price_unit}")
        
        # Quantity is typically 1 for court markings
        quantity = self.config['default_quantity']
        
        # Calculate GST as adjustment
        gst_amount = round(base_price * self.config['gst_rate'], 2)
        adjustments = [
            QuoteAdjustment(
                description=self.config['gst_description'],
                amount=gst_amount,
                type="fixed"
            )
        ]
        
        # Calculate total with GST
        total_price = round(base_price + gst_amount, 2)
        
        # Get conditions from knowledge base
        conditions = self._extract_conditions(highest_chunk, collected)
        
        # Get source references
        source_refs = []
        for chunk in relevant_chunks[:3]:  # Top 3 sources
            metadata = chunk.get('metadata', {})
            source = metadata.get('source') or metadata.get('document_name', 'Knowledge Base')
            if source not in source_refs:
                source_refs.append(source)
        
        return DraftQuotePreview(
            item_name=item_name,
            base_price=base_price,
            unit=price_unit,
            quantity=quantity,
            adjustments=adjustments,
            total_price=total_price,
            conditions=conditions,
            source_references=source_refs,
            missing_info=[],
            can_submit=True
        )
    
    def _calculate_generic_tree(
        self,
        db: Session,
        tree: Any,
        collected: Dict[str, Any]
    ) -> DraftQuotePreview:
        """Generic calculation for any decision tree"""
        
        # Build item name from first few answers
        item_parts = [tree.display_name]
        search_parts = [tree.display_name]
        
        for key, value in list(collected.items())[:3]:
            if value and str(value).lower() not in ['true', 'false', 'yes', 'no']:
                item_parts.append(str(value))
                search_parts.append(str(value))
        
        item_name = " ".join(item_parts)
        search_query = " ".join(search_parts)
        
        print(f"Generic Tree Quote - Item: {item_name}")
        print(f"Search query: {search_query}")
        
        # Search and calculate
        relevant_chunks = self._find_relevant_chunks(db, search_query)
        
        if not relevant_chunks:
            return self._empty_quote(f"No pricing found for {item_name}")
        
        # Apply same relevance filtering as main quote engine
        chunks_with_prices = []
        for chunk in relevant_chunks:
            metadata = chunk.get('metadata', {})
            content = chunk.get('content', '').lower()
            
            # Only consider chunks that are actually relevant to the item
            if self._is_relevant_chunk(item_name, content):
                price = metadata.get('base_price') or metadata.get('price', 0)
                if price:
                        try:
                            price_val = float(price)
                            # Filter out unrealistic prices using config threshold
                            if price_val <= self.config['max_price_threshold']:
                                chunks_with_prices.append({
                                    'chunk': chunk,
                                    'price': price_val
                                })
                        except (ValueError, TypeError):
                            continue
        
        if not chunks_with_prices:
            return self._empty_quote(f"Pricing not available for {item_name}")
        
        # Get most relevant price (not necessarily highest)
        # For flooring, prefer per sqm pricing
        if any(keyword in item_name.lower() for keyword in self.config['flooring_keywords']):
            # Look for per sqm pricing first
            sqm_chunks = [c for c in chunks_with_prices if 'sqm' in c['chunk'].get('content', '').lower() or 'per sqm' in c['chunk'].get('content', '').lower()]
            if sqm_chunks:
                selected = max(sqm_chunks, key=lambda x: x['price'])
            else:
                selected = max(chunks_with_prices, key=lambda x: x['price'])
        else:
            # For other services, use highest relevant price
            selected = max(chunks_with_prices, key=lambda x: x['price'])
        
        base_price = selected['price']
        price_unit = selected['chunk'].get('metadata', {}).get('price_unit', self.config['generic_tree_default_unit'])
        
        total_price = round(base_price * self.config['gst_multiplier'], 2)
        
        return DraftQuotePreview(
            item_name=item_name,
            base_price=base_price,
            unit=price_unit,
            quantity=self.config['default_quantity'],
            adjustments=[],
            total_price=total_price,
            conditions=self._extract_conditions(selected['chunk'], collected),
            source_references=[],
            missing_info=[],
            can_submit=True
        )
    
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
    
    def _is_relevant_chunk(self, item_name: str, content: str) -> bool:
        """Check if a chunk is actually relevant to the requested item"""
        
        item_lower = item_name.lower()
        content_lower = content.lower()
        
        # Define service categories and their keywords - loaded from config
        service_keywords = {
            'flooring': self.config['flooring_keywords'],
            'painting': ['paint', 'painting', 'repaint', 'exterior', 'interior', 'wall', 'ceiling'],
            'electrical': ['electrical', 'wiring', 'power', 'lighting', 'switch', 'outlet', 'circuit'],
            'plumbing': ['plumbing', 'pipe', 'water', 'drain', 'toilet', 'sink', 'faucet'],
            'construction': ['construction', 'renovation', 'renovate', 'build', 'install', 'installation']
        }
        
        # Identify the service category from item name
        item_category = None
        for category, keywords in service_keywords.items():
            if any(keyword in item_lower for keyword in keywords):
                item_category = category
                break
        
        if not item_category:
            # If we can't categorize, be more lenient
            return True
        
        # Check if content matches the service category
        category_keywords = service_keywords[item_category]
        content_matches_category = any(keyword in content_lower for keyword in category_keywords)
        
        # Also check for obvious mismatches
        other_categories = [cat for cat in service_keywords.keys() if cat != item_category]
        content_matches_other = any(
            any(keyword in content_lower for keyword in service_keywords[cat]) 
            for cat in other_categories
        )
        
        # Relevant if it matches the category OR doesn't strongly match other categories
        # This makes the filter more lenient to avoid $0 pricing
        return content_matches_category or not content_matches_other
    
    def _calculate_height_based_pricing(
        self,
        chunks: List[Dict],
        collected_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate pricing based on height (per-meter) if applicable"""
        
        height_str = collected_data.get('height', '')
        if not height_str:
            return None
        
        # Extract numeric height
        import re
        height_match = re.search(r'(\d+(?:\.\d+)?)\s*(m|meter|metre|ft|feet)', str(height_str).lower())
        if not height_match:
            return None
        
        height_value = float(height_match.group(1))
        height_unit = height_match.group(2)
        
        # Convert feet to meters if needed
        if height_unit in ['ft', 'feet']:
            height_value = height_value * self.config['feet_to_meters']
        
        # Look for per-meter pricing in chunks
        per_meter_rate = None
        cage_rung_rate = None
        access_door_price = None
        source_chunk = None
        
        for chunk in chunks:
            content = chunk.get('content', '').lower()
            
            # Look for per-meter pricing patterns
            # Pattern: "$550/m run" or "$550 per meter"
            if '/m run' in content or 'per m' in content or 'per meter' in content:
                meter_match = re.search(r'\$?\s*(\d+(?:\.\d+)?)\s*(?:/m|per\s*m(?:eter)?)', content)
                if meter_match and (not per_meter_rate or float(meter_match.group(1)) > per_meter_rate):
                    per_meter_rate = float(meter_match.group(1))
                    source_chunk = chunk
            
            # Look for cage rung pricing
            if 'cage' in content and 'rung' in content:
                rung_match = re.search(r'\$?\s*(\d+(?:\.\d+)?)\s*/\s*(?:cage\s*)?rung', content)
                if rung_match:
                    cage_rung_rate = float(rung_match.group(1))
            
            # Look for access door pricing
            if 'access door' in content or 'door' in content:
                door_match = re.search(r'\$?\s*(\d+(?:\.\d+)?)\s*(?:access\s*)?door', content)
                if door_match:
                    access_door_price = float(door_match.group(1))
        
        if not per_meter_rate:
            return None
        
        # Calculate total based on height
        total = height_value * per_meter_rate
        breakdown = f"${per_meter_rate}/m × {height_value}m"
        
        # Add cage rungs if applicable (estimate ~2 rungs per meter)
        special_features = collected_data.get('special_features', [])
        if isinstance(special_features, list):
            features_str = ' '.join(special_features).lower()
        else:
            features_str = str(special_features).lower()
        
        if cage_rung_rate and ('cage' in features_str or 'safety cage' in features_str):
            estimated_rungs = int(height_value * self.config['rungs_per_meter'])  # Configurable rungs per meter
            cage_cost = estimated_rungs * cage_rung_rate
            total += cage_cost
            breakdown += f" + {estimated_rungs} rungs × ${cage_rung_rate}"
        
        if access_door_price and ('door' in features_str or 'access door' in features_str):
            total += access_door_price
            breakdown += f" + door ${access_door_price}"
        
        return {
            'total_price': round(total, 2),
            'source_chunk': source_chunk,
            'breakdown': breakdown
        }

    
    def _calculate_adjustments(
        self,
        collected_data: Dict[str, Any],
        base_price: float
    ) -> List[QuoteAdjustment]:
        """Calculate price adjustments - ONLY from knowledge base, no hardcoded values"""
        adjustments = []
        
        # NO hardcoded adjustments
        # All pricing adjustments must come from the knowledge base documents
        # If adjustments are needed, they should be extracted from ChromaDB metadata
        # or document content during processing
        
        return adjustments
    
    def _calculate_total(
        self,
        base_price: float,
        quantity: Any,
        adjustments: List[QuoteAdjustment]
    ) -> float:
        """Calculate total price with GST"""
        
        # Parse quantity
        try:
            qty = float(quantity) if quantity else 1
        except (ValueError, TypeError):
            qty = 1
        
        # Start with base
        subtotal = base_price * qty
        
        # Apply adjustments
        for adj in adjustments:
            if adj.type == "fixed":
                subtotal += adj.amount
            elif adj.type == "percentage":
                subtotal += (subtotal * adj.amount / 100)
        
        # Add GST (always applied)
        subtotal_with_gst = subtotal * self.config['gst_multiplier']
        
        return round(subtotal_with_gst, 2)
    
    def _extract_conditions(
        self,
        chunk: Dict,
        collected_data: Dict[str, Any]
    ) -> List[str]:
        """Extract applicable conditions ONLY from knowledge base - no hardcoded conditions"""
        conditions = []
        
        # ONLY from ChromaDB metadata (from uploaded documents)
        if chunk:
            metadata = chunk.get('metadata', {})
            chunk_conditions = metadata.get('conditions')
            
            if chunk_conditions:
                if isinstance(chunk_conditions, list):
                    conditions.extend(chunk_conditions)
                elif isinstance(chunk_conditions, str):
                    # Split by pipe if it's a concatenated string
                    conditions.extend([c.strip() for c in chunk_conditions.split('|')])
                elif isinstance(chunk_conditions, dict):
                    conditions.extend(chunk_conditions.values())
        
        # Add delivery location info (not a pricing condition, just contextual)
        if collected_data.get('location'):
            conditions.append(f"Delivery to: {collected_data['location']}")
        
        # Always add GST notice
        conditions.append(self.config['gst_notice'])
        
        return conditions
    
    def _check_missing_info(self, collected_data: Dict[str, Any]) -> List[str]:
        """Check what information is still missing"""
        missing = []
        
        required_fields = {
            'item': 'Product/service type',
            'quantity': 'Quantity or area',
            'location': 'Location/address'
        }
        
        for key, label in required_fields.items():
            if not collected_data.get(key):
                missing.append(label)
        
        return missing
    
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
