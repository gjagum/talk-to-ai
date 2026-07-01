"""agent_management: agents, tools, agent_tools

Revision ID: 0003_agent_management
Revises: 0002_auth
Create Date: 2026-06-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0003_agent_management"
down_revision: Union[str, None] = "0002_auth"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tools",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("parameters", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("handler_key", sa.String(length=120), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_tools_name", "tools", ["name"], unique=True)
    op.create_index("ix_tools_handler_key", "tools", ["handler_key"], unique=False)

    op.create_table(
        "agents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("persona", sa.Text(), nullable=False),
        sa.Column("greeting", sa.Text(), nullable=False),
        sa.Column("stt_provider", sa.String(length=40), nullable=False, server_default="deepgram"),
        sa.Column("stt_model", sa.String(length=80), nullable=False, server_default="nova-3"),
        sa.Column("tts_provider", sa.String(length=40), nullable=False, server_default="deepgram"),
        sa.Column("tts_model", sa.String(length=80), nullable=False, server_default="aura-asteria-en"),
        sa.Column("llm_provider", sa.String(length=40), nullable=False, server_default="open_ai"),
        sa.Column("llm_model", sa.String(length=80), nullable=False, server_default="gpt-4o-mini"),
        sa.Column("llm_temperature", sa.Float(), nullable=False, server_default="0.7"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_agents_name", "agents", ["name"], unique=True)

    op.create_table(
        "agent_tools",
        sa.Column("agent_id", sa.Integer(), nullable=False),
        sa.Column("tool_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tool_id"], ["tools.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id", "tool_id"),
    )


def downgrade() -> None:
    op.drop_table("agent_tools")
    op.drop_index("ix_agents_name", table_name="agents")
    op.drop_table("agents")
    op.drop_index("ix_tools_handler_key", table_name="tools")
    op.drop_index("ix_tools_name", table_name="tools")
    op.drop_table("tools")
