# Quickstart: Refactor Ingestion-to-ML Handover

**Time to complete:** 20-30 minutes

**Prerequisites:**
- Docker & Docker Compose installed
- Services running (`docker-compose up -d`)
- Ollama running with models installed

---

## Overview

This guide walks through the implementation of the refactored ingestion pipeline where `python-ingestion` downloads files and `ml-analyze` handles parsing.

---

## Step 1: Verify Infrastructure (2 min)

Both services already share the uploads volume. Verify:

```bash
# Check volume mounts
docker-compose exec worker ls -la /shared/uploads
docker-compose exec ml-analyze ls -la /shared/uploads

# Test internal network connectivity
docker-compose exec worker curl -s http://ml-analyze:8001/health | jq
```

**Expected:** Both commands succeed; health check shows "healthy" status.

---

## Step 2: Add ML Client to python-ingestion (10 min)

Create the HTTP client for inter-service communication:

**File:** `services/python-ingestion/src/services/ml_client.py`

```python
"""HTTP client for ml-analyze service communication."""
import httpx
import structlog
from uuid import UUID
from typing import Optional
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

logger = structlog.get_logger(__name__)

ML_ANALYZE_URL = "http://ml-analyze:8001"
TIMEOUT = 30.0


class MLAnalyzeRequest(BaseModel):
    file_url: str
    supplier_id: UUID
    file_type: str


class MLClient:
    """Client for ml-analyze service API."""
    
    def __init__(self, base_url: str = ML_ANALYZE_URL):
        self.base_url = base_url
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=TIMEOUT,
            )
        return self._client
    
    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
    )
    async def check_health(self) -> bool:
        """Check if ML service is healthy."""
        client = await self._get_client()
        try:
            response = await client.get("/health")
            data = response.json()
            return data.get("status") == "healthy"
        except Exception as e:
            logger.warning("ml_health_check_failed", error=str(e))
            return False
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
    )
    async def trigger_analysis(
        self,
        file_path: str,
        supplier_id: UUID,
        file_type: str,
    ) -> dict:
        """Trigger file analysis in ML service."""
        client = await self._get_client()
        
        request = MLAnalyzeRequest(
            file_url=file_path,
            supplier_id=supplier_id,
            file_type=file_type,
        )
        
        logger.info(
            "triggering_ml_analysis",
            file_path=file_path,
            supplier_id=str(supplier_id),
            file_type=file_type,
        )
        
        response = await client.post(
            "/analyze/file",
            json=request.model_dump(mode="json"),
        )
        response.raise_for_status()
        return response.json()
    
    async def get_job_status(self, job_id: UUID) -> dict:
        """Get ML job status."""
        client = await self._get_client()
        response = await client.get(f"/analyze/status/{job_id}")
        response.raise_for_status()
        return response.json()


# Singleton instance
ml_client = MLClient()
```

---

## Step 3: Create Download Task (10 min)

Replace parsing logic with download + ML trigger:

**File:** `services/python-ingestion/src/tasks/download_tasks.py`

```python
"""Download tasks for the courier pipeline."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any
from uuid import UUID, uuid4

import structlog
from arq.connections import ArqRedis

from src.services.ml_client import ml_client
from src.config import settings

logger = structlog.get_logger(__name__)

SHARED_UPLOADS_DIR = Path("/shared/uploads")


async def download_and_trigger_ml(
    ctx: Dict[str, Any],
    job_id: str,
    supplier_id: str,
    supplier_name: str,
    source_type: str,
    source_url: str,
    use_ml_processing: bool = True,
    **kwargs
) -> Dict[str, Any]:
    """Download file and trigger ML analysis.
    
    Args:
        ctx: arq context with Redis
        job_id: Unique job identifier
        supplier_id: UUID of supplier
        supplier_name: Human-readable supplier name
        source_type: google_sheets, csv, excel, or url
        source_url: URL or path to download from
        use_ml_processing: Whether to use ML pipeline
        
    Returns:
        Dict with job result
    """
    redis: ArqRedis = ctx["redis"]
    log = logger.bind(job_id=job_id, supplier_name=supplier_name)
    
    try:
        # Update phase to downloading
        await _update_job_phase(redis, job_id, "downloading")
        
        # Step 1: Download file
        log.info("starting_download", source_type=source_type)
        file_path, file_type, file_size = await _download_file(
            source_type=source_type,
            source_url=source_url,
            supplier_id=supplier_id,
            job_id=job_id,
            redis=redis,
        )
        
        log.info(
            "download_complete",
            file_path=str(file_path),
            file_type=file_type,
            file_size=file_size,
        )
        
        if not use_ml_processing:
            # Legacy path - would call old parser here
            log.info("legacy_processing_not_implemented")
            return {"status": "error", "error": "Legacy processing disabled"}
        
        # Step 2: Check ML service health
        if not await ml_client.check_health():
            raise RuntimeError("ML service is not healthy")
        
        # Step 3: Trigger ML analysis
        await _update_job_phase(redis, job_id, "analyzing")
        
        ml_response = await ml_client.trigger_analysis(
            file_path=str(file_path),
            supplier_id=UUID(supplier_id),
            file_type=file_type,
        )
        
        ml_job_id = ml_response["job_id"]
        log.info("ml_analysis_triggered", ml_job_id=ml_job_id)
        
        # Store ML job ID for status tracking
        await redis.hset(f"job:{job_id}", "ml_job_id", ml_job_id)
        
        return {
            "status": "success",
            "job_id": job_id,
            "ml_job_id": ml_job_id,
            "file_path": str(file_path),
            "file_type": file_type,
        }
        
    except Exception as e:
        log.exception("download_task_failed", error=str(e))
        await _update_job_phase(redis, job_id, "failed", error=str(e))
        return {"status": "error", "error": str(e)}


async def _download_file(
    source_type: str,
    source_url: str,
    supplier_id: str,
    job_id: str,
    redis: ArqRedis,
) -> tuple[Path, str, int]:
    """Download file based on source type.
    
    Returns:
        Tuple of (file_path, file_type, file_size)
    """
    timestamp = int(datetime.now(timezone.utc).timestamp())
    
    if source_type == "google_sheets":
        from src.parsers.google_sheets_parser import GoogleSheetsParser
        parser = GoogleSheetsParser()
        
        # Export as XLSX
        file_name = f"{supplier_id}_{timestamp}_export.xlsx"
        file_path = SHARED_UPLOADS_DIR / file_name
        
        await parser.export_to_xlsx(source_url, file_path)
        file_type = "excel"
        
    elif source_type in ("csv", "excel"):
        # Direct file - copy to shared volume
        import shutil
        src_path = Path(source_url)
        file_name = f"{supplier_id}_{timestamp}_{src_path.name}"
        file_path = SHARED_UPLOADS_DIR / file_name
        shutil.copy(src_path, file_path)
        file_type = source_type
        
    elif source_type == "url":
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(source_url)
            response.raise_for_status()
            
            # Determine file type from content-type or extension
            content_type = response.headers.get("content-type", "")
            if "pdf" in content_type:
                file_type = "pdf"
                ext = ".pdf"
            elif "excel" in content_type or "spreadsheet" in content_type:
                file_type = "excel"
                ext = ".xlsx"
            else:
                file_type = "csv"
                ext = ".csv"
            
            file_name = f"{supplier_id}_{timestamp}_download{ext}"
            file_path = SHARED_UPLOADS_DIR / file_name
            file_path.write_bytes(response.content)
    else:
        raise ValueError(f"Unknown source type: {source_type}")
    
    file_size = file_path.stat().st_size
    
    # Write metadata sidecar
    meta = {
        "original_filename": file_path.name,
        "source_url": source_url,
        "source_type": source_type,
        "supplier_id": supplier_id,
        "file_type": file_type,
        "file_size_bytes": file_size,
        "checksum_md5": _compute_md5(file_path),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "job_id": job_id,
    }
    meta_path = file_path.with_suffix(file_path.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2))
    
    return file_path, file_type, file_size


def _compute_md5(file_path: Path) -> str:
    """Compute MD5 checksum of file."""
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


async def _update_job_phase(
    redis: ArqRedis,
    job_id: str,
    phase: str,
    error: str = None,
):
    """Update job phase in Redis."""
    await redis.hset(f"job:{job_id}", mapping={
        "phase": phase,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        **({"error": error} if error else {}),
    })
```

---

## Step 4: Update Frontend Status Component (5 min)

Add phase-aware display to the status card:

**File:** `services/frontend/src/components/admin/JobPhaseIndicator.tsx`

```tsx
import { useTranslation } from 'react-i18next'

type JobPhase = 'downloading' | 'analyzing' | 'matching' | 'complete' | 'failed'

interface JobPhaseIndicatorProps {
  phase: JobPhase
  downloadProgress?: { percentage: number; bytes_downloaded: number } | null
  analysisProgress?: { percentage: number; items_processed: number; items_total: number } | null
}

const phaseConfig: Record<JobPhase, { icon: string; color: string; bgColor: string }> = {
  downloading: { icon: '📥', color: 'text-blue-600', bgColor: 'bg-blue-100' },
  analyzing: { icon: '🔬', color: 'text-yellow-600', bgColor: 'bg-yellow-100' },
  matching: { icon: '🔗', color: 'text-purple-600', bgColor: 'bg-purple-100' },
  complete: { icon: '✅', color: 'text-green-600', bgColor: 'bg-green-100' },
  failed: { icon: '❌', color: 'text-red-600', bgColor: 'bg-red-100' },
}

export function JobPhaseIndicator({
  phase,
  downloadProgress,
  analysisProgress,
}: JobPhaseIndicatorProps) {
  const { t } = useTranslation()
  const config = phaseConfig[phase]
  
  const getProgress = () => {
    if (phase === 'downloading' && downloadProgress) {
      return downloadProgress.percentage
    }
    if ((phase === 'analyzing' || phase === 'matching') && analysisProgress) {
      return analysisProgress.percentage
    }
    if (phase === 'complete') return 100
    return 0
  }
  
  const progress = getProgress()
  
  return (
    <div className="flex items-center gap-3">
      <span className={`text-xl ${config.bgColor} p-2 rounded-full`}>
        {config.icon}
      </span>
      <div className="flex-1">
        <div className="flex items-center justify-between">
          <span className={`font-medium ${config.color}`}>
            {t(`ingestion.phase.${phase}`)}
          </span>
          <span className="text-sm text-slate-500">{progress}%</span>
        </div>
        <div className="mt-1 h-2 bg-slate-200 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${
              phase === 'failed' ? 'bg-red-500' : 'bg-primary'
            }`}
            style={{ width: `${progress}%` }}
          />
        </div>
        {phase === 'analyzing' && analysisProgress && (
          <p className="mt-1 text-xs text-slate-500">
            {analysisProgress.items_processed} / {analysisProgress.items_total} {t('ingestion.items')}
          </p>
        )}
      </div>
    </div>
  )
}
```

---

## Step 5: Add Translations (2 min)

**File:** `services/frontend/public/locales/en/common.json` (add to existing):

```json
{
  "ingestion": {
    "phase": {
      "downloading": "Downloading",
      "analyzing": "Analyzing",
      "matching": "Matching",
      "complete": "Complete",
      "failed": "Failed"
    },
    "items": "items",
    "useMlProcessing": "Process via ML",
    "useMlProcessingHint": "Use AI-powered parsing for better accuracy"
  }
}
```

---

## Step 6: Test the Integration (5 min)

```bash
# 1. Start services
docker-compose up -d

# 2. Create a test file in shared volume
docker-compose exec worker bash -c 'echo "name,price\nProduct A,100" > /shared/uploads/test.csv'

# 3. Verify ML can see it
docker-compose exec ml-analyze ls -la /shared/uploads/test.csv

# 4. Test ML API directly
docker-compose exec worker curl -X POST http://ml-analyze:8001/analyze/file \
  -H "Content-Type: application/json" \
  -d '{"file_url": "/shared/uploads/test.csv", "supplier_id": "00000000-0000-0000-0000-000000000001", "file_type": "csv"}'

# 5. Check job status
docker-compose exec worker curl http://ml-analyze:8001/analyze/status/{job_id_from_step_4}
```

---

## Verification Checklist

- [ ] Both services can access `/shared/uploads`
- [ ] ML health check passes from worker container
- [ ] File download creates file + metadata JSON
- [ ] ML analysis trigger returns job ID
- [ ] Job status polling works
- [ ] Frontend shows phase-specific indicators

---

## Next Steps

1. Update `sync_tasks.py` to use new download pipeline
2. Add file cleanup cron task
3. Implement retry button in Admin UI
4. Add E2E tests for full pipeline

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Connection refused" to ML | Check `ml-analyze` container is running: `docker-compose ps` |
| "File not found" in ML | Verify volume mount: `docker-compose exec ml-analyze ls /shared/uploads` |
| "Permission denied" | Check volume permissions: both services should run as same user |
| Job stuck in "analyzing" | Check Ollama: `curl http://localhost:11434/api/tags` |

