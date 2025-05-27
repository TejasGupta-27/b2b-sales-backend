from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = 'initial_migration'
down_revision = None
branch_labels = None
depends_on = None

# Define the ENUM globally
message_type_enum = postgresql.ENUM('user', 'assistant', 'system', name='messagetype')

def upgrade():
    bind = op.get_bind()
    # Only create ENUM if it doesn't exist
    result = bind.execute(text("SELECT 1 FROM pg_type WHERE typname = 'messagetype'"))
    if result.first() is None:
        message_type_enum.create(bind)

    # Create leads table first
    op.create_table(
        'leads',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('company_name', sa.String(), nullable=False),
        sa.Column('contact_name', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('phone', sa.String()),
        sa.Column('industry', sa.String()),
        sa.Column('company_size', sa.String()),
        sa.Column('annual_revenue', sa.String()),
        sa.Column('pain_points', postgresql.JSONB(), default=list),
        sa.Column('budget_range', sa.String()),
        sa.Column('decision_timeline', sa.String()),
        sa.Column('decision_makers', postgresql.JSONB(), default=list),
        sa.Column('status', sa.String()),
        sa.Column('lead_score', sa.Integer()),
        sa.Column('notes', sa.String()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_contact', sa.DateTime()),
        sa.Column('next_follow_up', sa.DateTime()),
        sa.PrimaryKeyConstraint('id')
    )

    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('lead_id', sa.String(), nullable=False),
        sa.Column('message_type', postgresql.ENUM('user', 'assistant', 'system', name='messagetype', create_type=False), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('stage', sa.String()),
        sa.Column('message_metadata', postgresql.JSONB()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('idx_chat_messages_lead_id', 'chat_messages', ['lead_id'])
    op.create_index('idx_chat_messages_created_at', 'chat_messages', ['created_at'])

def downgrade():
    # Drop tables in correct order
    op.drop_table('chat_messages')
    op.drop_table('leads')
    
    # Drop ENUM if exists
    bind = op.get_bind()
    result = bind.execute(text("SELECT 1 FROM pg_type WHERE typname = 'messagetype'"))
    if result.first():
        bind.execute(text("DROP TYPE messagetype"))
