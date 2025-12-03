# Data Model: Refactor Ingestion-to-ML Handover

**Date:** 2025-12-03

**Feature:** 008-ml-ingestion-integration

---

## Overview

This document defines the data structures for the refactored ingestion pipeline. Focus is on inter-service communication models and enhanced job state tracking.

---

## Redis Data Structures

### Enhanced Job State

**Key Pattern:** `job:{job_id}`

**Type:** Hash

**TTL:** 7 days

```json
{
  "job_id": "uuid-string",
  "supplier_id": "uuid-string",
  "supplier_name": "Supplier ABC",
  "task_id": "parse-supplier-abc-1701619200",
  "phase": "downloading|analyzing|matching|complete|failed",
  "status": "pending|processing|completed|failed",
  
  "download_progress": {
    "bytes_downloaded": 1048576,
    "bytes_total": 5242880,
    "percentage": 20
  },
  
  "analysis_progress": {
    "items_processed": 45,
    "items_total": 100,
    "matches_found": 30,
    "review_queue": 10,
    "errors": 5,
    "percentage": 45
  },
  
  "ml_job_id": "uuid-from-ml-analyze",
  "file_path": "/shared/uploads/uuid_timestamp_filename.xlsx",
  "file_type": "excel|csv|pdf",
  "file_size_bytes": 5242880,
  "checksum": "md5-hash",
  
  "error": null,
  "error_details": [],
  "retry_count": 0,
  "max_retries": 3,
  
  "created_at": "2025-12-03T10:00:00Z",
  "started_at": "2025-12-03T10:00:05Z",
  "completed_at": null,
  "updated_at": "2025-12-03T10:01:30Z"
}
```

**Phase State Machine:**

```
┌─────────────┐    download      ┌─────────────┐    trigger ML    ┌───────────┐
│  PENDING    │ ───────────────► │ DOWNLOADING │ ────────────────► │ ANALYZING │
└─────────────┘                  └─────────────┘                   └───────────┘
                                        │                                │
                                        │ download error                 │ ML complete
                                        ▼                                ▼
                                  ┌─────────┐                      ┌──────────┐
                                  │ FAILED  │ ◄──── ML error ───── │ MATCHING │
                                  └─────────┘                      └──────────┘
                                                                         │
                                                                         │ matches done
                                                                         ▼
                                                                   ┌──────────┐
                                                                   │ COMPLETE │
                                                                   └──────────┘
```

---

### File Metadata (Sidecar JSON)

**File Pattern:** `{filepath}.meta.json`

**Purpose:** Track file provenance and enable integrity verification

```json
{
  "original_filename": "supplier_pricelist.xlsx",
  "source_url": "https://docs.google.com/spreadsheets/d/...",
  "source_type": "google_sheets|csv|excel|url",
  "supplier_id": "uuid-string",
  "supplier_name": "Supplier ABC",
  "file_type": "excel",
  "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  "file_size_bytes": 5242880,
  "checksum_md5": "a1b2c3d4e5f6...",
  "downloaded_at": "2025-12-03T10:00:30Z",
  "downloaded_by": "python-ingestion",
  "job_id": "uuid-string"
}
```

---

## Pydantic Models (python-ingestion)

### ML Client Request Model

```python
from pydantic import BaseModel, Field
from uuid import UUID
from typing import Literal
from datetime import datetime

class MLAnalyzeRequest(BaseModel):
    """Request body for triggering ML analysis."""
    
    file_url: str = Field(
        description="Local path on shared volume",
        examples=["/shared/uploads/uuid_1701619200_pricelist.xlsx"]
    )
    supplier_id: UUID = Field(
        description="UUID of supplier owning the file"
    )
    file_type: Literal["pdf", "excel", "csv"] = Field(
        description="Type of file being analyzed"
    )
    metadata: dict | None = Field(
        default=None,
        description="Additional metadata to pass to ML service"
    )


class MLAnalyzeResponse(BaseModel):
    """Response from ML service after triggering analysis."""
    
    job_id: UUID = Field(description="ML job ID for status tracking")
    status: Literal["pending", "processing", "completed", "failed"]
    message: str


class MLJobStatus(BaseModel):
    """Status response from ML service."""
    
    job_id: UUID
    status: Literal["pending", "processing", "completed", "failed"]
    progress_percentage: int = Field(ge=0, le=100)
    items_processed: int = Field(ge=0)
    items_total: int = Field(ge=0)
    errors: list[str] = Field(default_factory=list)
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
```

### Download Task Message

```python
class DownloadTaskMessage(BaseModel):
    """Queue message for download tasks."""
    
    task_id: str = Field(description="Unique task identifier")
    job_id: UUID = Field(description="Associated job ID")
    supplier_id: UUID
    supplier_name: str
    source_type: Literal["google_sheets", "csv", "excel", "url"]
    source_url: str = Field(description="URL or path to download from")
    use_ml_processing: bool = Field(default=True)
    
    # For Google Sheets
    sheet_name: str | None = None
    
    # Options
    max_file_size_mb: int = Field(default=50)
    timeout_seconds: int = Field(default=300)
```

### Job Progress Update

```python
class JobProgressUpdate(BaseModel):
    """Model for updating job progress in Redis."""
    
    job_id: UUID
    phase: Literal["downloading", "analyzing", "matching", "complete", "failed"]
    
    # Download phase
    download_bytes: int | None = None
    download_total: int | None = None
    
    # Analysis phase
    items_processed: int | None = None
    items_total: int | None = None
    matches_found: int | None = None
    review_queue_count: int | None = None
    error_count: int | None = None
    
    # Error info
    error_message: str | None = None
    error_details: list[str] = Field(default_factory=list)
    
    # ML correlation
    ml_job_id: UUID | None = None
```

---

## TypeScript Types (Frontend)

### Job Status Response

```typescript
// types/ingestion.ts

export type JobPhase = 
  | 'downloading' 
  | 'analyzing' 
  | 'matching' 
  | 'complete' 
  | 'failed';

export type JobStatus = 
  | 'pending' 
  | 'processing' 
  | 'completed' 
  | 'failed';

export interface DownloadProgress {
  bytes_downloaded: number;
  bytes_total: number | null;
  percentage: number;
}

export interface AnalysisProgress {
  items_processed: number;
  items_total: number;
  matches_found: number;
  review_queue: number;
  errors: number;
  percentage: number;
}

export interface IngestionJob {
  job_id: string;
  supplier_id: string;
  supplier_name: string;
  phase: JobPhase;
  status: JobStatus;
  download_progress: DownloadProgress | null;
  analysis_progress: AnalysisProgress | null;
  file_type: 'excel' | 'csv' | 'pdf';
  error: string | null;
  error_details: string[];
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface IngestionStatusResponse {
  sync_state: string;
  current_phase: JobPhase | null;
  jobs: IngestionJob[];
  suppliers: SupplierStatus[];
  recent_logs: ParsingLog[];
  last_sync_at: string | null;
  next_scheduled_at: string;
}
```

### Supplier with ML Flag

```typescript
export interface Supplier {
  id: string;
  name: string;
  source_type: 'google_sheets' | 'csv' | 'excel';
  source_url: string;
  meta: {
    is_active: boolean;
    use_ml_processing: boolean;  // NEW
    last_parsed_at: string | null;
    items_count: number;
  };
  created_at: string;
  updated_at: string;
}
```

---

## Database Changes

### Supplier Meta Extension

No schema migration needed - uses existing JSONB `meta` field.

**New meta fields:**

```json
{
  "use_ml_processing": true,
  "ml_processing_enabled_at": "2025-12-03T10:00:00Z"
}
```

**SQL to update existing suppliers:**

```sql
-- Enable ML processing for all active suppliers
UPDATE suppliers 
SET meta = meta || '{"use_ml_processing": true}'::jsonb
WHERE meta->>'is_active' = 'true';
```

---

## Validation Rules

### File Metadata

| Field | Validation |
|-------|------------|
| `original_filename` | 1-255 chars, sanitized (no path separators) |
| `source_url` | Valid URL or file path |
| `file_size_bytes` | > 0, < MAX_FILE_SIZE_MB * 1024 * 1024 |
| `checksum_md5` | 32 hex characters |
| `file_type` | One of: pdf, excel, csv |

### Job State

| Field | Validation |
|-------|------------|
| `job_id` | Valid UUID v4 |
| `phase` | Valid phase enum value |
| `progress_percentage` | 0-100 |
| `retry_count` | >= 0, <= max_retries |

---

## State Transitions

### Valid Phase Transitions

```
pending → downloading     (download started)
downloading → analyzing   (download complete, ML triggered)
downloading → failed      (download error after retries)
analyzing → matching      (parsing complete, matching started)
analyzing → failed        (ML service error)
matching → complete       (all items matched/queued)
matching → failed         (matching error)
failed → downloading      (manual retry triggered)
```

### Invalid Transitions (Error)

- `complete` → any (terminal state)
- `analyzing` → `downloading` (cannot go backward)
- `matching` → `downloading` (cannot go backward)

---

## Example Flows

### Successful Processing

```json
// T+0s: Job created
{ "phase": "pending", "status": "pending" }

// T+1s: Download started
{ "phase": "downloading", "download_progress": { "percentage": 0 } }

// T+10s: Download progress
{ "phase": "downloading", "download_progress": { "percentage": 50, "bytes_downloaded": 2621440 } }

// T+20s: Download complete, ML triggered
{ "phase": "analyzing", "ml_job_id": "uuid-ml", "analysis_progress": { "percentage": 0 } }

// T+60s: Analysis progress
{ "phase": "analyzing", "analysis_progress": { "items_processed": 50, "items_total": 100, "percentage": 50 } }

// T+120s: Matching started
{ "phase": "matching", "analysis_progress": { "items_processed": 100, "matches_found": 80 } }

// T+150s: Complete
{ "phase": "complete", "status": "completed", "analysis_progress": { "matches_found": 85, "review_queue": 15 } }
```

### Failed with Retry

```json
// T+0s: Download started
{ "phase": "downloading", "retry_count": 0 }

// T+30s: Download failed (network error)
{ "phase": "failed", "error": "Connection timeout", "retry_count": 1 }

// T+35s: Auto-retry
{ "phase": "downloading", "retry_count": 1 }

// T+65s: Download failed again
{ "phase": "failed", "error": "Connection timeout", "retry_count": 2 }

// T+70s: Auto-retry
{ "phase": "downloading", "retry_count": 2 }

// T+100s: Success after retry
{ "phase": "analyzing" }
```

