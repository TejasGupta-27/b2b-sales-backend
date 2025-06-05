"""Add fuzzy search support using pg_trgm

Revision ID: add_fuzzy_search
Revises: add_chat_search_index
Create Date: 2024-03-27 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers
revision = 'add_fuzzy_search'
down_revision = 'add_chat_search_index'
branch_labels = None
depends_on = None

def upgrade():
    # Enable pg_trgm extension
    op.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
    
    # Create a GIN index for trigram similarity search
    op.execute(text("""
        CREATE INDEX IF NOT EXISTS idx_chat_messages_content_trgm 
        ON chat_messages 
        USING gin(content gin_trgm_ops)
    """))

def downgrade():
    # Drop the trigram index
    op.execute(text("""
        DROP INDEX IF EXISTS idx_chat_messages_content_trgm
    """))
    
    # Note: We don't drop the pg_trgm extension as it might be used by other parts of the database 