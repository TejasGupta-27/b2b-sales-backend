"""Add full-text search index for chat messages

Revision ID: add_chat_search_index
Revises: fix_enum_values
Create Date: 2024-03-27 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers
revision = 'add_chat_search_index'
down_revision = 'fix_enum_values'
branch_labels = None
depends_on = None

def upgrade():
    # Create a GIN index for full-text search on the content column
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_content_gin 
        ON chat_messages 
        USING gin(to_tsvector('english', content))
    """))

def downgrade():
    # Drop the GIN index
    op.execute(text("""
        DROP INDEX IF EXISTS idx_chat_messages_content_gin
    """)) 