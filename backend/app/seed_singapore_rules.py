"""
Seed script to populate Singapore ladder safety rules
Run this script to add the business rules to the database
"""
from app.database import SessionLocal
from app.models import BusinessRule
from datetime import datetime

def seed_singapore_ladder_rules():
    """Seed Singapore ladder safety regulations into the database"""
    
    db = SessionLocal()
    
    try:
        # Check if rule already exists
        existing = db.query(BusinessRule).filter(
            BusinessRule.rule_name == "Singapore Ladder Safety Standards"
        ).first()
        
        if existing:
            print("Singapore ladder rules already exist. Skipping...")
            return
        
        # Create the comprehensive Singapore ladder safety rule
        # All values are configurable - admins can edit through UI
        singapore_rule_config = {
            "rule_type": "ladder_safety_singapore",
            "region": "SGP",
            "gst_rate": 0.09,  # Singapore GST rate - configurable via admin UI
            "source_refs": {
                "wsh_reg": "Workplace Safety and Health (Work at Heights) Regulations - Singapore",
                "iso": "ISO 14122-4:2016",
                "bca": "BCA guidance / Approved Document"
            },
            "fixed_ladder_rules_sg": {
                "min_cage_height_m": 3.0,
                "max_single_flight_no_platform_m": 6.0,
                "rung_pitch_mm": 300,
                "min_internal_clear_width_mm": 350,
                "recommended_wall_clearance_mm": 150,
                "max_cage_hoop_spacing_mm": 1500,
                "step_depth_min_mm": 25,
                "step_load_requirement_n": 1500,
                "exit_handhold_required": True,
                "marking_requirements": [
                    "manufacturer",
                    "year_of_manufacture",
                    "commissioning_date",
                    "standard_reference",
                    "PPE_mandatory_notice"
                ],
                "platform_rules": {
                    "insert_rest_platform_if_height_exceeds_m": 6.0,
                    "platform_at_top_exit_required": True
                },
                "fall_protection_notes": "Cage or ladder safety device required for climbs >3.0 m; fall arrest systems (guided devices) may be used where compliant but must not negate exit protection requirements.",
                "design_checks": {
                    "verify_material_grade": ["SS304", "SS316", "HDG", "Aluminium"],
                    "site_verification_required_if_no_drawings": True,
                    "access_equipment_assumption": "Quote assumes access equipment provided by others unless explicit charge applied",
                    "material_warning_template": "Material '{material}' should be verified against approved grades: {grades}"
                },
                "cage_requirement": {
                    "item_name": "safety cage",
                    "search_terms": ["safety cage", "ladder cage", "cage for ladder", "cage rung"]
                },
                "platform_requirement": {
                    "item_name": "rest platform",
                    "search_terms": ["rest platform", "ladder platform", "intermediate platform"]
                },
                "exit_handhold_config": {
                    "condition_text": "Exit handhold required at top of ladder per Singapore standards"
                }
            }
        }
        
        # Create the business rule
        # Initially only the safety cage rule (height > 3m) is active
        # Other rules can be activated later through the admin UI
        new_rule = BusinessRule(
            rule_name="Singapore Ladder Safety Standards",
            service_type="cat_ladder_installation",
            region="SGP",
            rule_config=singapore_rule_config,
            is_active=True,  # Active by default
            priority=10,  # High priority
            source_reference="WSH (Work at Heights) Regulations, ISO 14122-4:2016",
            description="Singapore safety regulations for fixed ladder installations including safety cage requirements, platform rules, and material standards",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(new_rule)
        db.commit()
        
        print("✓ Singapore ladder safety rules seeded successfully!")
        print(f"  Rule ID: {new_rule.id}")
        print(f"  Rule Name: {new_rule.rule_name}")
        print(f"  Active: {new_rule.is_active}")
        print(f"  Service Type: {new_rule.service_type}")
        print("")
        print("Active requirements:")
        print("  - Safety cage required for ladders > 3m")
        print("  - Rest platform required for ladders > 6m")
        print("  - Material verification (SS304, SS316, HDG, Aluminium)")
        print("  - Exit handhold required at top")
        
    except Exception as e:
        print(f"Error seeding rules: {str(e)}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_singapore_ladder_rules()

