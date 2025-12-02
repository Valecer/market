# Quickstart: Admin Control Panel & Master Sync Scheduler

**Estimated Time:** 15-20 minutes for initial setup, ~4 hours for full implementation

---

## Prerequisites

- [ ] Docker Compose running (postgres, redis, worker, bun-api, frontend)
- [ ] Google service account configured with Sheets API access
- [ ] Master Google Sheet created with supplier configuration
- [ ] Phase 1-3 complete and working

---

## Step 1: Create Master Google Sheet (5 min)

1. Create a new Google Spreadsheet
2. Share with your service account email (from `credentials/google-credentials.json`)
3. Add columns in Row 1:
   - `Supplier Name` | `Source URL` | `Format` | `Active` | `Notes`
4. Add sample supplier data (Row 2+):
   ```
   Acme Corp | https://docs.google.com/spreadsheets/d/xxx | google_sheets | TRUE | Main supplier
   Beta Inc | https://example.com/prices.csv | csv | TRUE | Updates weekly
   ```
5. Copy the Master Sheet URL for configuration

---

## Step 2: Configure Environment Variables (2 min)

Add to `services/python-ingestion/.env`:

```bash
# Master Sync Configuration
MASTER_SHEET_URL=https://docs.google.com/spreadsheets/d/YOUR_SHEET_ID
SYNC_INTERVAL_HOURS=8
```

---

## Step 3: Python Worker - MasterSheetIngestor (30 min)

### 3.1 Create Ingestor Service

```bash
# Create new service file
touch services/python-ingestion/src/services/master_sheet_ingestor.py
```

```python
# services/python-ingestion/src/services/master_sheet_ingestor.py
"""Master Sheet Ingestor - reads supplier config from Master Google Sheet."""
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import structlog

from src.parsers.google_sheets_parser import GoogleSheetsParser
from src.models.master_sheet_config import SupplierConfigRow, MasterSyncResult
from src.errors.exceptions import ParserError, ValidationError
from src.db.base import async_session_maker
from src.db.models import Supplier

logger = structlog.get_logger(__name__)

@dataclass
class SupplierConfig:
    """Parsed supplier configuration from Master Sheet."""
    name: str
    source_url: str
    source_type: str
    is_active: bool
    notes: Optional[str] = None

class MasterSheetIngestor:
    """Ingests supplier configuration from Master Google Sheet."""
    
    COLUMN_MAPPING = {
        'supplier_name': ['supplier name', 'name', 'supplier'],
        'source_url': ['source url', 'url', 'source', 'link'],
        'format': ['format', 'type', 'source type'],
        'active': ['active', 'is_active', 'enabled'],
        'notes': ['notes', 'note', 'comments'],
    }
    
    def __init__(self):
        self._parser = GoogleSheetsParser()
    
    async def ingest(self, master_sheet_url: str, sheet_name: str = "Suppliers") -> List[SupplierConfig]:
        """Parse Master Sheet and return supplier configurations."""
        # Implementation follows GoogleSheetsParser pattern
        pass
    
    async def sync_suppliers(self, configs: List[SupplierConfig]) -> MasterSyncResult:
        """Upsert suppliers to database based on configs."""
        # Implementation uses async session
        pass
```

### 3.2 Create Sync Task

```python
# services/python-ingestion/src/tasks/sync_tasks.py
"""Master sync pipeline tasks."""
from typing import Dict, Any
from arq import ArqRedis
import structlog

from src.services.master_sheet_ingestor import MasterSheetIngestor
from src.config import settings

logger = structlog.get_logger(__name__)

async def trigger_master_sync_task(ctx: Dict[str, Any], **kwargs) -> Dict[str, Any]:
    """Execute the master sync pipeline."""
    task_id = kwargs.get('task_id', 'unknown')
    triggered_by = kwargs.get('triggered_by', 'manual')
    
    log = logger.bind(task_id=task_id, triggered_by=triggered_by)
    log.info("master_sync_started")
    
    # 1. Parse Master Sheet
    # 2. Sync suppliers to DB
    # 3. Enqueue parse tasks for active suppliers
    
    return {"status": "success", "task_id": task_id}
```

### 3.3 Register Cron Job

Update `services/python-ingestion/src/worker.py`:

```python
from arq import cron
from src.tasks.sync_tasks import trigger_master_sync_task, scheduled_sync_task
import os

def get_sync_hours() -> set:
    """Calculate cron hours based on SYNC_INTERVAL_HOURS."""
    interval = int(os.getenv('SYNC_INTERVAL_HOURS', '8'))
    return set(range(0, 24, interval))

class WorkerSettings:
    # ... existing settings ...
    
    functions = [
        parse_task,
        match_items_task,
        # ... existing functions ...
        trigger_master_sync_task,  # Add new task
    ]
    
    cron_jobs = [
        # ... existing cron jobs ...
        cron(
            scheduled_sync_task,
            hour=get_sync_hours(),
            minute=0,
            unique=True,
            run_at_startup=False,
        ),
    ]
```

---

## Step 4: Bun API - Ingestion Endpoints (20 min)

### 4.1 Create Ingestion Service

```bash
touch services/bun-api/src/services/ingestion.service.ts
```

```typescript
// services/bun-api/src/services/ingestion.service.ts
import { queueService, RedisUnavailableError } from './queue.service'
import type { IngestionStatusResponse, TriggerSyncResponse } from '../types/ingestion.types'

export class IngestionService {
  async triggerSync(): Promise<TriggerSyncResponse> {
    // Check if sync already running (Redis lock)
    // Enqueue trigger_master_sync_task
    // Return task_id
  }
  
  async getStatus(): Promise<IngestionStatusResponse> {
    // Get sync state from Redis
    // Get suppliers with status
    // Get recent logs
    // Calculate next scheduled time
  }
}

export const ingestionService = new IngestionService()
```

### 4.2 Create Controller Routes

Add to `services/bun-api/src/controllers/admin/index.ts`:

```typescript
// Add new routes in adminController group
.post(
  '/ingestion/sync',
  async ({ set }) => {
    set.status = 202
    return ingestionService.triggerSync()
  },
  {
    beforeHandle({ user, set }) {
      if (!user || user.role !== 'admin') {
        set.status = 403
        return { error: { code: 'FORBIDDEN', message: 'Admin role required' } }
      }
    },
    // ... response schemas
  }
)
.get(
  '/ingestion/status',
  async ({ query }) => {
    return ingestionService.getStatus(query.log_limit)
  },
  {
    query: t.Object({ log_limit: t.Optional(t.Number()) }),
    // ... response schemas
  }
)
```

---

## Step 5: Frontend - Ingestion Page (30 min)

### 5.1 Create Hook

```bash
touch services/frontend/src/hooks/useIngestionStatus.ts
```

```typescript
// services/frontend/src/hooks/useIngestionStatus.ts
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'

export function useIngestionStatus() {
  return useQuery({
    queryKey: ['ingestion-status'],
    queryFn: async () => {
      const { data, error } = await apiClient.GET('/api/v1/admin/ingestion/status')
      if (error) throw error
      return data
    },
    refetchInterval: 3000,
    refetchIntervalInBackground: false,
  })
}

export function useTriggerSync() {
  const queryClient = useQueryClient()
  
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await apiClient.POST('/api/v1/admin/ingestion/sync')
      if (error) throw error
      return data
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['ingestion-status'] })
    },
  })
}
```

### 5.2 Create Page Component

```bash
mkdir -p services/frontend/src/pages/admin
touch services/frontend/src/pages/admin/IngestionPage.tsx
```

```tsx
// services/frontend/src/pages/admin/IngestionPage.tsx
import { useIngestionStatus, useTriggerSync } from '@/hooks/useIngestionStatus'
import { SyncControlCard } from '@/components/admin/SyncControlCard'
import { LiveLogViewer } from '@/components/admin/LiveLogViewer'
import { SupplierStatusTable } from '@/components/admin/SupplierStatusTable'

export function IngestionPage() {
  const { data, isLoading } = useIngestionStatus()
  const triggerSync = useTriggerSync()
  
  return (
    <div className="container mx-auto p-6 space-y-6">
      <h1 className="text-2xl font-bold">Ingestion Control Panel</h1>
      
      <SyncControlCard
        syncState={data?.sync_state ?? 'idle'}
        progress={data?.progress ?? null}
        lastSyncAt={data?.last_sync_at ?? null}
        nextScheduledAt={data?.next_scheduled_at ?? ''}
        onSyncNow={() => triggerSync.mutate()}
        isSyncing={triggerSync.isPending}
      />
      
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SupplierStatusTable
          suppliers={data?.suppliers ?? []}
          isLoading={isLoading}
        />
        <LiveLogViewer
          logs={data?.recent_logs ?? []}
          isLoading={isLoading}
        />
      </div>
    </div>
  )
}
```

### 5.3 Add Route

Update `services/frontend/src/routes.tsx`:

```tsx
import { IngestionPage } from '@/pages/admin/IngestionPage'

// Add to admin routes
{ path: '/admin/ingestion', element: <IngestionPage /> }
```

---

## Step 6: Verify Setup (5 min)

### 6.1 Start Services

```bash
docker-compose up -d
```

### 6.2 Test API Endpoints

```bash
# Login as admin
TOKEN=$(curl -s -X POST http://localhost:3000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@marketbel.com","password":"admin123"}' | jq -r '.token')

# Get status
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:3000/api/v1/admin/ingestion/status | jq

# Trigger sync
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:3000/api/v1/admin/ingestion/sync | jq
```

### 6.3 Check Worker Logs

```bash
docker-compose logs -f worker
```

### 6.4 Open Frontend

Navigate to `http://localhost:5173/admin/ingestion` (login as admin first)

---

## Troubleshooting

### Master Sheet Access Denied
- Verify service account email has Viewer access to sheet
- Check `credentials/google-credentials.json` is mounted

### Sync Not Starting
- Check Redis is running: `docker-compose exec redis redis-cli ping`
- Check worker is running: `docker-compose logs worker`
- Verify `MASTER_SHEET_URL` is set correctly

### Logs Not Appearing
- Wait 3-5 seconds for polling refresh
- Check browser console for API errors
- Verify admin JWT token is valid

---

## Next Steps

After completing quickstart:

1. Implement full `MasterSheetIngestor` with column mapping
2. Add sync lock mechanism in Redis
3. Create remaining UI components (`SyncControlCard`, `LiveLogViewer`, `SupplierStatusTable`)
4. Add i18n translations
5. Write unit and integration tests

