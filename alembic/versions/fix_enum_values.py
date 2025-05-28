"""Fix enum values to match database expectations

Revision ID: fix_enum_values
Revises: initial_migration
Create Date: 2025-05-27 20:15:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = 'fix_enum_values'
down_revision = 'initial_migration'
branch_labels = None
depends_on = None

def upgrade():
    # Update existing enum values if any exist
    op.execute("UPDATE chat_messages SET message_type = 'USER' WHERE message_type = 'user'")
    op.execute("UPDATE chat_messages SET message_type = 'ASSISTANT' WHERE message_type = 'assistant'")
    op.execute("UPDATE leads SET status = 'NEW' WHERE status = 'new'")
    op.execute("UPDATE leads SET status = 'QUALIFIED' WHERE status = 'qualified'")
    op.execute("UPDATE leads SET status = 'PROPOSAL' WHERE status = 'proposal'")
    op.execute("UPDATE leads SET status = 'NEGOTIATION' WHERE status = 'negotiation'")
    op.execute("UPDATE leads SET status = 'CLOSED_WON' WHERE status = 'closed_won'")
    op.execute("UPDATE leads SET status = 'CLOSED_LOST' WHERE status = 'closed_lost'")

def downgrade():
    # Revert enum values if needed
    op.execute("UPDATE chat_messages SET message_type = 'user' WHERE message_type = 'USER'")
    op.execute("UPDATE chat_messages SET message_type = 'assistant' WHERE message_type = 'ASSISTANT'")
    op.execute("UPDATE leads SET status = 'new' WHERE status = 'NEW'")
    op.execute("UPDATE leads SET status = 'qualified' WHERE status = 'QUALIFIED'")
    op.execute("UPDATE leads SET status = 'proposal' WHERE status = 'PROPOSAL'")
    op.execute("UPDATE leads SET status = 'negotiation' WHERE status = 'NEGOTIATION'")
    op.execute("UPDATE leads SET status = 'closed_won' WHERE status = 'CLOSED_WON'")
    op.execute("UPDATE leads SET status = 'closed_lost' WHERE status = 'CLOSED_LOST'") 