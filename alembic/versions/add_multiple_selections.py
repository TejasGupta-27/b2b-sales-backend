"""add multiple selections support

Revision ID: add_multiple_selections
Revises: add_chat_search_index
Create Date: 2024-03-21 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON

# revision identifiers, used by Alembic.
revision = 'add_multiple_selections'
down_revision = 'add_chat_search_index'
branch_labels = None
depends_on = None

def upgrade():
    # Add new columns for multiple selections
    op.add_column('recommendation_sets', sa.Column('selected_recommendations', JSON, nullable=True, server_default='[]'))
    op.add_column('recommendation_sets', sa.Column('selection_timestamps', JSON, nullable=True, server_default='{}'))
    op.add_column('recommendation_sets', sa.Column('quote_data', JSON, nullable=True))
    op.add_column('recommendation_sets', sa.Column('quote_generated_at', sa.DateTime(), nullable=True))
    
    # Migrate existing data
    connection = op.get_bind()
    recommendation_sets = connection.execute(
        "SELECT id, selected_recommendation, selection_timestamp FROM recommendation_sets WHERE selected_recommendation IS NOT NULL"
    ).fetchall()
    
    for rec_set in recommendation_sets:
        if rec_set.selected_recommendation:
            connection.execute(
                """
                UPDATE recommendation_sets 
                SET selected_recommendations = :selected_recommendations,
                    selection_timestamps = :selection_timestamps
                WHERE id = :id
                """,
                {
                    'id': rec_set.id,
                    'selected_recommendations': [rec_set.selected_recommendation],
                    'selection_timestamps': {rec_set.selected_recommendation: rec_set.selection_timestamp.isoformat() if rec_set.selection_timestamp else None}
                }
            )
    
    # Drop old columns
    op.drop_column('recommendation_sets', 'selected_recommendation')
    op.drop_column('recommendation_sets', 'selection_timestamp')

def downgrade():
    # Add back old columns
    op.add_column('recommendation_sets', sa.Column('selected_recommendation', sa.String(), nullable=True))
    op.add_column('recommendation_sets', sa.Column('selection_timestamp', sa.DateTime(), nullable=True))
    
    # Migrate data back
    connection = op.get_bind()
    recommendation_sets = connection.execute(
        "SELECT id, selected_recommendations, selection_timestamps FROM recommendation_sets WHERE selected_recommendations IS NOT NULL"
    ).fetchall()
    
    for rec_set in recommendation_sets:
        if rec_set.selected_recommendations and len(rec_set.selected_recommendations) > 0:
            first_selection = rec_set.selected_recommendations[0]
            timestamp = rec_set.selection_timestamps.get(first_selection) if rec_set.selection_timestamps else None
            
            connection.execute(
                """
                UPDATE recommendation_sets 
                SET selected_recommendation = :selected_recommendation,
                    selection_timestamp = :selection_timestamp
                WHERE id = :id
                """,
                {
                    'id': rec_set.id,
                    'selected_recommendation': first_selection,
                    'selection_timestamp': timestamp
                }
            )
    
    # Drop new columns
    op.drop_column('recommendation_sets', 'selected_recommendations')
    op.drop_column('recommendation_sets', 'selection_timestamps')
    op.drop_column('recommendation_sets', 'quote_data')
    op.drop_column('recommendation_sets', 'quote_generated_at') 