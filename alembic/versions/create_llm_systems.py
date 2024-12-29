"""create llm systems table

Revision ID: create_llm_systems
Revises: 
Create Date: 2024-12-26 16:49:11.000000

"""
from alembic import op
import sqlalchemy as sa
import json


# revision identifiers, used by Alembic.
revision = 'create_llm_systems'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create llm_systems table
    op.create_table(
        'llm_systems',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('api_key_setting', sa.String(), nullable=False),
        sa.Column('default_model', sa.String(), nullable=False),
        sa.Column('available_models', sa.String(), nullable=False),
        sa.Column('is_default', sa.Boolean(), default=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_llm_systems_id'), 'llm_systems', ['id'], unique=False)
    op.create_index(op.f('ix_llm_systems_name'), 'llm_systems', ['name'], unique=True)

    # Insert default OpenAI configuration
    openai_models = [
        "gpt-4-turbo",
        "gpt-4",
        "gpt-3.5-turbo",
        "gpt-3.5-turbo-16k"
    ]
    
    op.execute(
        """
        INSERT INTO llm_systems (name, api_key_setting, default_model, available_models, is_default)
        VALUES ('OpenAI', 'openai_api_key', 'gpt-4-turbo', :models, true)
        """,
        {"models": json.dumps(openai_models)}
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_llm_systems_name'), table_name='llm_systems')
    op.drop_index(op.f('ix_llm_systems_id'), table_name='llm_systems')
    op.drop_table('llm_systems')
