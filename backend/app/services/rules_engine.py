from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from app.models import BusinessRule


class RulesEngine:
    """Business rules validation and application engine"""
    
    def __init__(self):
        pass
    
    def validate_and_apply_rules(
        self,
        db: Session,
        service_type: str,
        collected_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Validate collected data against active business rules and apply requirements.
        
        Returns:
        {
            "requirements": [{"item": "safety cage", "reason": "Singapore regulation..."}],
            "conditions": ["Safety cage required for ladders > 3m"],
            "adjustments": [],
            "warnings": []
        }
        """
        
        # Get all active rules for this service type (or general rules)
        rules = db.query(BusinessRule).filter(
            BusinessRule.is_active == True
        ).filter(
            (BusinessRule.service_type == service_type) | (BusinessRule.service_type == None)
        ).order_by(BusinessRule.priority.asc()).all()
        
        result = {
            "requirements": [],
            "conditions": [],
            "adjustments": [],
            "warnings": []
        }
        
        # Apply each rule
        for rule in rules:
            rule_result = self._apply_single_rule(rule, collected_data)
            
            # Merge results
            if rule_result:
                result["requirements"].extend(rule_result.get("requirements", []))
                result["conditions"].extend(rule_result.get("conditions", []))
                result["adjustments"].extend(rule_result.get("adjustments", []))
                result["warnings"].extend(rule_result.get("warnings", []))
        
        return result
    
    def _apply_single_rule(
        self,
        rule: BusinessRule,
        collected_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Apply a single business rule to collected data"""
        
        rule_config = rule.rule_config
        rule_type = rule_config.get("rule_type")
        
        # Route to specific rule handler based on type
        if rule_type == "ladder_safety_singapore":
            return self._apply_ladder_safety_rules(rule_config, collected_data)
        
        # Add more rule types here as needed
        
        return None
    
    def _apply_ladder_safety_rules(
        self,
        rule_config: Dict[str, Any],
        collected_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply ladder safety regulations based on configurable rule_config"""
        
        result = {
            "requirements": [],
            "conditions": [],
            "adjustments": [],
            "warnings": []
        }
        
        # Get the regulations from rule config
        regulations = rule_config.get("fixed_ladder_rules_sg", {})
        source_refs = rule_config.get("source_refs", {})
        region = rule_config.get("region", "")
        
        # Get configurable text templates (defaults for backward compatibility)
        regulation_name = source_refs.get("wsh_reg", "Safety Regulations")
        standards_label = f"{region} standards" if region else "safety standards"
        
        # Extract height from collected data
        height = self._extract_height(collected_data)
        
        if height is None:
            return result
        
        # Rule 1: Safety cage requirement (fully configurable from rule_config)
        min_cage_height = regulations.get("min_cage_height_m")
        if min_cage_height and height > min_cage_height:
            # Get configurable search terms and labels
            cage_config = regulations.get("cage_requirement", {})
            item_name = cage_config.get("item_name", "safety cage")
            search_terms = cage_config.get("search_terms", ["safety cage", "ladder cage", "cage for ladder"])
            
            result["requirements"].append({
                "item": item_name,
                "reason": f"{regulation_name} require {item_name} for ladders exceeding {min_cage_height}m",
                "search_terms": search_terms,
                "mandatory": True
            })
            result["conditions"].append(
                f"{item_name.title()} required (ladder height {height}m exceeds {min_cage_height}m minimum per {regulation_name})"
            )
        
        # Rule 2: Rest platform requirement (fully configurable)
        platform_rules = regulations.get("platform_rules", {})
        max_single_flight = platform_rules.get("insert_rest_platform_if_height_exceeds_m")
        
        if max_single_flight and height > max_single_flight:
            platform_config = regulations.get("platform_requirement", {})
            item_name = platform_config.get("item_name", "rest platform")
            search_terms = platform_config.get("search_terms", ["rest platform", "ladder platform", "intermediate platform"])
            
            result["requirements"].append({
                "item": item_name,
                "reason": f"{item_name.title()} required for ladder heights exceeding {max_single_flight}m",
                "search_terms": search_terms,
                "mandatory": True
            })
            result["conditions"].append(
                f"{item_name.title()} required (height {height}m exceeds {max_single_flight}m per regulations)"
            )
        
        # Rule 3: Material validation (configurable materials list)
        material = collected_data.get("material", "").lower()
        design_checks = regulations.get("design_checks", {})
        valid_materials = design_checks.get("verify_material_grade", [])
        
        if material and valid_materials:
            # Check if material matches any valid option (case insensitive)
            material_valid = any(
                mat.lower() in material or material in mat.lower()
                for mat in valid_materials
            )
            
            if not material_valid:
                warning_template = design_checks.get("material_warning_template", 
                    "Material '{material}' should be verified against approved grades: {grades}")
                result["warnings"].append(
                    warning_template.format(material=material, grades=', '.join(valid_materials))
                )
        
        # Rule 4: Exit handhold requirement (configurable)
        if regulations.get("exit_handhold_required", False):
            handhold_config = regulations.get("exit_handhold_config", {})
            condition_text = handhold_config.get("condition_text", 
                f"Exit handhold required at top of ladder per {standards_label}")
            result["conditions"].append(condition_text)
        
        return result
    
    def _extract_actual_value(self, data: Any) -> Any:
        """Extract actual value from context metadata or return as-is"""
        if isinstance(data, dict) and 'value' in data:
            # This is context data with metadata
            return data['value']
        return data
    
    def _extract_height(self, collected_data: Dict[str, Any]) -> Optional[float]:
        """Extract height value from collected_data (supports various formats and context data)"""
        
        # Try direct 'height' key
        if "height" in collected_data:
            value = self._extract_actual_value(collected_data["height"])
            return self._parse_height_value(value)
        
        # Try 'ladder_height'
        if "ladder_height" in collected_data:
            value = self._extract_actual_value(collected_data["ladder_height"])
            return self._parse_height_value(value)
        
        # Try 'total_height'
        if "total_height" in collected_data:
            value = self._extract_actual_value(collected_data["total_height"])
            return self._parse_height_value(value)
        
        return None
    
    def _parse_height_value(self, value: Any) -> Optional[float]:
        """Parse height value from various formats (numbers, strings with units)"""
        
        if isinstance(value, (int, float)):
            return float(value)
        
        if isinstance(value, str):
            # Remove common units and whitespace
            cleaned = value.lower().replace("m", "").replace("meter", "").replace("metres", "").strip()
            
            try:
                return float(cleaned)
            except ValueError:
                # Try to extract first number
                import re
                match = re.search(r'(\d+(?:\.\d+)?)', cleaned)
                if match:
                    return float(match.group(1))
        
        return None


# Singleton instance
rules_engine = RulesEngine()

