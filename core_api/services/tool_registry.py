"""Tool Registry service - manages tool registration and lookup."""

from typing import List, Optional
from sqlalchemy.orm import Session
from ..models.tools import Tool
from ..schemas.tools import ToolCreate, ToolResponse


class ToolRegistry:
    """Service for managing tools."""

    @staticmethod
    def register_tool(db: Session, tool: ToolCreate) -> ToolResponse:
        """Register a new tool."""
        db_tool = Tool(
            name=tool.name,
            description=tool.description,
            input_schema=tool.input_schema,
            output_schema=tool.output_schema,
            tags=tool.tags,
            module_path=tool.module_path,
            function_name=tool.function_name,
        )
        db.add(db_tool)
        db.commit()
        db.refresh(db_tool)
        return ToolResponse.model_validate(db_tool)

    @staticmethod
    def get_tool(db: Session, tool_id: int) -> Optional[ToolResponse]:
        """Get a tool by ID."""
        db_tool = db.query(Tool).filter(Tool.id == tool_id).first()
        if db_tool:
            return ToolResponse.model_validate(db_tool)
        return None

    @staticmethod
    def get_tool_by_name(db: Session, name: str) -> Optional[ToolResponse]:
        """Get a tool by name."""
        db_tool = db.query(Tool).filter(Tool.name == name).first()
        if db_tool:
            return ToolResponse.model_validate(db_tool)
        return None

    @staticmethod
    def list_tools(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        tags: Optional[List[str]] = None,
    ) -> List[ToolResponse]:
        """List tools with optional filtering."""
        query = db.query(Tool)
        
        if tags:
            # Filter by tags (assuming tags is a JSON array)
            for tag in tags:
                query = query.filter(Tool.tags.contains([tag]))
        
        tools = query.offset(skip).limit(limit).all()
        return [ToolResponse.model_validate(tool) for tool in tools]

    @staticmethod
    def delete_tool(db: Session, tool_id: int) -> bool:
        """Delete a tool."""
        db_tool = db.query(Tool).filter(Tool.id == tool_id).first()
        if db_tool:
            db.delete(db_tool)
            db.commit()
            return True
        return False


