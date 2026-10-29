"""enable_rls_and_revoke_public_grants

Revision ID: f1a2b3c4d5e6
Revises: e8f901a23b45
Create Date: 2026-10-29 10:52:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e8f901a23b45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PUBLIC_TABLES = [
    'agent_configuration',
    'alembic_version',
    'attendances',
    'browser_profiles',
    'employee_lists',
    'invitation_drafts',
    'meetings',
    'organization_config',
    'presentation_assets',
    'presentation_jobs',
    'presentation_metadata',
    'presentation_questions',
    'presentation_scripts',
    'presentations',
    'runtime_messages',
    'runtimes',
    'sessions',
    'uploads',
    'voice_profiles',
]

def upgrade() -> None:
    # 1. Revoke public PostgREST access (anon, authenticated) on all public tables
    # Preserves backend service_role and postgres roles (which have BYPASSRLS)
    for table in PUBLIC_TABLES:
        op.execute(f"REVOKE ALL ON TABLE public.{table} FROM anon, authenticated;")
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;")
        # Optional explicit service_role bypass/full policy for safety if service_role role is ever evaluated
        op.execute(f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_policies 
                    WHERE schemaname = 'public' 
                      AND tablename = '{table}' 
                      AND policyname = 'service_role_all_{table}'
                ) THEN
                    CREATE POLICY service_role_all_{table} ON public.{table} 
                    FOR ALL TO service_role USING (true) WITH CHECK (true);
                END IF;
            END $$;
        """)

def downgrade() -> None:
    for table in PUBLIC_TABLES:
        op.execute(f"DROP POLICY IF EXISTS service_role_all_{table} ON public.{table};")
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY;")
        op.execute(f"GRANT ALL ON TABLE public.{table} TO anon, authenticated;")
