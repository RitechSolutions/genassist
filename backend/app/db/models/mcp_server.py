from sqlalchemy import Column, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MCPServerModel(Base):
    """
    SQLAlchemy model for an MCP Server.
    Auth material is stored in ``auth_values`` (JSONB); shape depends on ``auth_type``.
    """

    __tablename__ = "mcp_servers"
    __table_args__ = (
        UniqueConstraint("name", "user_id", name="unique_name_user"),
        Index("idx_user_active", "user_id", "is_active", "is_deleted"),
    )

    name = Column(String(255), nullable=False)
    auth_type = Column(String(32), nullable=False, default="api_key")  # api_key | oauth2
    auth_values = Column(JSONB, nullable=False)
    description = Column(String, nullable=True)
    is_active = Column(Integer, nullable=False, default=1)
    user_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # Relationships
    user = relationship("UserModel", back_populates="mcp_servers")
    workflows = relationship(
        "MCPServerWorkflowModel",
        back_populates="mcp_server",
        cascade="all, delete-orphan",
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
        UniqueConstraint("mcp_server_id", "tool_name", name="unique_server_tool_name"),
        Index("idx_workflow", "workflow_id"),
    )

    mcp_server_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mcp_servers.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("workflows.id"), nullable=False)
    tool_name = Column(String(255), nullable=False)  # Name to expose as MCP tool
    tool_description = Column(String(255), nullable=False)  # Description for the MCP tool

    # Relationships
    mcp_server = relationship("MCPServerModel", back_populates="workflows")
    workflow = relationship("WorkflowModel", uselist=False)

    def __repr__(self):
        return f"<MCPServerWorkflowModel(id='{self.id}', tool_name='{self.tool_name}', workflow_id='{self.workflow_id}')>"
