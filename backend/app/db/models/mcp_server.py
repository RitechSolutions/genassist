from typing import List
from sqlalchemy import Column, String, Integer, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import relationship, Mapped, mapped_column
from sqlalchemy.dialects.postgresql import UUID
from app.db.base import Base


class MCPServerModel(Base):
    """
    SQLAlchemy model for an MCP Server.
    Stores MCP server configuration with encrypted API keys.
    """

    __tablename__ = "mcp_servers"
    __table_args__ = (
        UniqueConstraint('name', 'user_id', name='unique_name_user'),
        Index('idx_api_key_hash', 'api_key_hash'),
        Index('idx_user_active', 'user_id', 'is_active', 'is_deleted'),
    )

    name = Column(String(255), nullable=False)
    api_key_encrypted = Column(String, nullable=False)  # Encrypted API key
    api_key_hash = Column(String(255), nullable=False, index=True)  # Hash for fast lookup
    description = Column(String, nullable=True)
    is_active = Column(Integer, nullable=False, default=1)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("UserModel", back_populates="mcp_servers")
    workflows = relationship(
        "MCPServerWorkflowModel",
        back_populates="mcp_server",
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<MCPServerModel(id='{self.id}', name='{self.name}', user_id='{self.user_id}')>"


class MCPServerWorkflowModel(Base):
    """
    SQLAlchemy model for MCP Server Workflows.
    Links workflows to MCP servers with custom tool names and descriptions.
    """

    __tablename__ = "mcp_server_workflows"
    __table_args__ = (
        UniqueConstraint('mcp_server_id', 'tool_name', name='unique_server_tool_name'),
        Index('idx_workflow', 'workflow_id'),
    )

    mcp_server_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    tool_name = Column(String(255), nullable=False)  # Name to expose as MCP tool
    tool_description = Column(String, nullable=False)  # Description for the MCP tool

    # Relationships
    mcp_server = relationship("MCPServerModel", back_populates="workflows")
    workflow = relationship("WorkflowModel", uselist=False)

    def __repr__(self):
        return f"<MCPServerWorkflowModel(id='{self.id}', tool_name='{self.tool_name}', workflow_id='{self.workflow_id}')>"

