from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models import User, DecisionTree
from app.schemas import DecisionTreeCreate, DecisionTreeUpdate, DecisionTreeResponse
from app.auth import get_current_admin

router = APIRouter(prefix="/api/decision-trees", tags=["Decision Trees"])


@router.get("/", response_model=List[DecisionTreeResponse])
def list_decision_trees(
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """List all decision trees (admin only)"""
    trees = db.query(DecisionTree).order_by(DecisionTree.service_name).all()
    return trees


@router.get("/{tree_id}", response_model=DecisionTreeResponse)
def get_decision_tree(
    tree_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Get a specific decision tree"""
    tree = db.query(DecisionTree).filter(DecisionTree.id == tree_id).first()
    if not tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision tree not found"
        )
    return tree


@router.post("/", response_model=DecisionTreeResponse)
def create_decision_tree(
    tree_data: DecisionTreeCreate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Create a new decision tree (admin only)"""
    
    # Check if service name already exists
    existing = db.query(DecisionTree).filter(
        DecisionTree.service_name == tree_data.service_name
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Decision tree for '{tree_data.service_name}' already exists"
        )
    
    tree = DecisionTree(
        service_name=tree_data.service_name,
        display_name=tree_data.display_name,
        description=tree_data.description,
        tree_config=tree_data.tree_config.dict(),
        created_by=current_user.id
    )
    
    db.add(tree)
    db.commit()
    db.refresh(tree)
    
    return tree


@router.put("/{tree_id}", response_model=DecisionTreeResponse)
def update_decision_tree(
    tree_id: int,
    tree_data: DecisionTreeUpdate,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Update a decision tree (admin only)"""
    
    tree = db.query(DecisionTree).filter(DecisionTree.id == tree_id).first()
    if not tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision tree not found"
        )
    
    # Update fields
    if tree_data.display_name is not None:
        tree.display_name = tree_data.display_name
    if tree_data.description is not None:
        tree.description = tree_data.description
    if tree_data.tree_config is not None:
        tree.tree_config = tree_data.tree_config.dict()
    if tree_data.is_active is not None:
        tree.is_active = tree_data.is_active
    
    db.commit()
    db.refresh(tree)
    
    return tree


@router.delete("/{tree_id}")
def delete_decision_tree(
    tree_id: int,
    current_user: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Delete a decision tree (admin only)"""
    
    tree = db.query(DecisionTree).filter(DecisionTree.id == tree_id).first()
    if not tree:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Decision tree not found"
        )
    
    db.delete(tree)
    db.commit()
    
    return {"message": "Decision tree deleted successfully"}

