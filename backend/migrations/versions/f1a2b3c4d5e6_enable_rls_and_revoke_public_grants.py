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
    # Safe on both Supabase and standard local PostgreSQL:
    # Revoke public PostgREST roles (anon, authenticated) ONLY IF they exist in pg_roles.
    for table in PUBLIC_TABLES:
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    EXECUTE 'REVOKE ALL ON TABLE public.{table} FROM anon';
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    EXECUTE 'REVOKE ALL ON TABLE public.{table} FROM authenticated';
                END IF;
            END $$;
        """)
        op.execute(f"ALTER TABLE public.{table} ENABLE ROW LEVEL SECURITY;")
        # Optional explicit service_role bypass/full policy for safety if service_role role exists
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_policies 
                        WHERE schemaname = 'public' 
                          AND tablename = '{table}' 
                          AND policyname = 'service_role_all_{table}'
                    ) THEN
                        EXECUTE 'CREATE POLICY service_role_all_{table} ON public.{table} FOR ALL TO service_role USING (true) WITH CHECK (true)';
                    END IF;
                END IF;
            END $$;
        """)

def downgrade() -> None:
    for table in PUBLIC_TABLES:
        op.execute(f"DROP POLICY IF EXISTS service_role_all_{table} ON public.{table};")
        op.execute(f"ALTER TABLE public.{table} DISABLE ROW LEVEL SECURITY;")
        op.execute(f"""
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                    EXECUTE 'GRANT ALL ON TABLE public.{table} TO anon';
                END IF;
                IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                    EXECUTE 'GRANT ALL ON TABLE public.{table} TO authenticated';
                END IF;
            END $$;
        """)
