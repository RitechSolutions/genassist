Add these variables to your `.env` file:

```bash
# Multi-tenancy settings
MULTI_TENANT_ENABLED=true
TENANT_HEADER_NAME=X-Tenant-ID
TENANT_SUBDOMAIN_ENABLED=false
```

### Settings

- `MULTI_TENANT_ENABLED`: Enable/disable multi-tenancy (default: false)
- `TENANT_HEADER_NAME`: HTTP header name for tenant identification (default: "X-Tenant-ID")
- `TENANT_SUBDOMAIN_ENABLED`: Enable subdomain-based tenant resolution (default: false)


## Tenant Resolution

The system supports multiple methods for tenant resolution:

### 1. HTTP Header (Recommended)
Send requests with the tenant header:
```bash
curl -H "X-Tenant-ID: acme" http://localhost:8000/api/v1/users
```

### 2. Subdomain (Optional)
If `TENANT_SUBDOMAIN_ENABLED=true`, tenants can be resolved from subdomains:
```bash
curl http://acme.localhost:8000/api/v1/users
```

## API Endpoints

### Tenant Management

- `POST /api/v1/tenants` - Create a new tenant
- `GET /api/v1/tenants` - List all tenants
- `GET /api/v1/tenants/{tenant_id}` - Get tenant by ID
- `GET /api/v1/tenants/slug/{tenant_slug}` - Get tenant by slug
- `PUT /api/v1/tenants/{tenant_id}` - Update tenant
- `DELETE /api/v1/tenants/{tenant_id}` - Deactivate tenant

### Example: Create Tenant

```bash
curl -X POST "http://localhost:8000/api/tenants/" -H "Content-Type: application/json" -d '{"name": "Virgin Voyages", "slug": "virgin-voyages", "description": "A VV tenant"}'
```
```bash
curl -X GET "http://localhost:8000/api/v1/tenants" \
  -H "Content-Type: application/json" 
```

## Database Structure

### Master Database
- `tenants` table stores tenant information
- Used for tenant management and routing

### Tenant Databases
- Each tenant has its own database: `{DB_NAME}_tenant_{slug}`
- Contains identical schema to the main application
- All existing models and tables

## Usage in Code

### Using Tenant-Aware Sessions

```python
from app.dependencies.tenant_dependencies import get_tenant_session

@router.get("/users")
async def get_users(session: AsyncSession = Depends(get_tenant_session)):
    # This will automatically use the correct tenant database
    users = await session.execute(select(UserModel))
    return users.scalars().all()
```

### Using Master Database

```python
from app.dependencies.tenant_dependencies import get_master_session

@router.get("/tenants")
async def list_tenants(session: AsyncSession = Depends(get_master_session)):
    # This uses the master database for tenant management
    tenants = await session.execute(select(TenantModel))
    return tenants.scalars().all()
```

### Manual Tenant Session

```python
from app.services.tenant import TenantService

tenant_service = TenantService()
session = await tenant_service.get_tenant_session("acme")
if session:
    # Use tenant-specific session
    users = await session.execute(select(UserModel))
```

## Migration Management

### Creating Migrations

```bash
# Create a new migration (same as before)
python scripts/alembic_create_migration_wrapper.py "add new feature"
```
