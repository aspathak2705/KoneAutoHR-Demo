# Development Workflow

## Iteration Cycles
1. Modify database models or schemas.
2. Run database migrations:
   ```bash
   alembic revision --autogenerate -m "description"
   ```
3. Run verification tests.
4. Verify build and type checking of both backend and frontend.
