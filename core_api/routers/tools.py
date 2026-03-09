"""Tools router - endpoints for tool registry."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from ..db import get_db
from ..schemas.tools import ToolCreate, ToolResponse, ToolList
from ..services.tool_registry import ToolRegistry

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/", response_model=ToolList)
def list_tools(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    tags: Optional[List[str]] = Query(None),
    db: Session = Depends(get_db),
):
    """List all registered tools."""
    tools = ToolRegistry.list_tools(db, skip=skip, limit=limit, tags=tags)
    return ToolList(tools=tools, count=len(tools))


@router.get("/{tool_id}", response_model=ToolResponse)
def get_tool(tool_id: int, db: Session = Depends(get_db)):
    """Get a specific tool by ID."""
    tool = ToolRegistry.get_tool(db, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.post("/", response_model=ToolResponse, status_code=201)
def register_tool(tool: ToolCreate, db: Session = Depends(get_db)):
    """Register a new tool."""
    # Check if tool with same name already exists
    existing = ToolRegistry.get_tool_by_name(db, tool.name)
    if existing:
        raise HTTPException(status_code=400, detail="Tool with this name already exists")
    
    return ToolRegistry.register_tool(db, tool)


@router.delete("/{tool_id}", status_code=204)
def delete_tool(tool_id: int, db: Session = Depends(get_db)):
    """Delete a tool."""
    success = ToolRegistry.delete_tool(db, tool_id)
    if not success:
        raise HTTPException(status_code=404, detail="Tool not found")


