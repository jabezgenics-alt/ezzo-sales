from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import BusinessRule, User, UserRole
from app.schemas import BusinessRuleCreate, BusinessRuleUpdate, BusinessRuleResponse
from app.auth import get_current_user

router = APIRouter(prefix="/api/business-rules", tags=["business_rules"])


@router.get("/", response_model=List[BusinessRuleResponse])
def list_business_rules(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List all business rules (admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    rules = db.query(BusinessRule).order_by(BusinessRule.priority.asc()).all()
    return rules


@router.get("/{rule_id}", response_model=BusinessRuleResponse)
def get_business_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific business rule (admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    rule = db.query(BusinessRule).filter(BusinessRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business rule not found"
        )
    
    return rule


@router.post("/", response_model=BusinessRuleResponse)
def create_business_rule(
    rule_data: BusinessRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new business rule (admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    # Create new rule
    new_rule = BusinessRule(
        rule_name=rule_data.rule_name,
        service_type=rule_data.service_type,
        region=rule_data.region,
        rule_config=rule_data.rule_config,
        is_active=rule_data.is_active,
        priority=rule_data.priority,
        source_reference=rule_data.source_reference,
        description=rule_data.description
    )
    
    db.add(new_rule)
    db.commit()
    db.refresh(new_rule)
    
    return new_rule


@router.put("/{rule_id}", response_model=BusinessRuleResponse)
def update_business_rule(
    rule_id: int,
    rule_data: BusinessRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Update a business rule (admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    rule = db.query(BusinessRule).filter(BusinessRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business rule not found"
        )
    
    # Update fields
    if rule_data.rule_name is not None:
        rule.rule_name = rule_data.rule_name
    if rule_data.service_type is not None:
        rule.service_type = rule_data.service_type
    if rule_data.region is not None:
        rule.region = rule_data.region
    if rule_data.rule_config is not None:
        rule.rule_config = rule_data.rule_config
    if rule_data.is_active is not None:
        rule.is_active = rule_data.is_active
    if rule_data.priority is not None:
        rule.priority = rule_data.priority
    if rule_data.source_reference is not None:
        rule.source_reference = rule_data.source_reference
    if rule_data.description is not None:
        rule.description = rule_data.description
    
    db.commit()
    db.refresh(rule)
    
    return rule


@router.patch("/{rule_id}/toggle", response_model=BusinessRuleResponse)
def toggle_business_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Toggle a business rule active/inactive (admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    rule = db.query(BusinessRule).filter(BusinessRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business rule not found"
        )
    
    rule.is_active = not rule.is_active
    db.commit()
    db.refresh(rule)
    
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_business_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a business rule (admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    
    rule = db.query(BusinessRule).filter(BusinessRule.id == rule_id).first()
    if not rule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Business rule not found"
        )
    
    db.delete(rule)
    db.commit()
    
    return None

