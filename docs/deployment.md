# Deployment Runbook: Data Ingestion Infrastructure

**Service:** Python Ingestion Worker  
**Version:** 1.0.0  
**Last Updated:** 2025-11-24

---

## Pre-Deployment Checklist

### Environment Preparation

- [ ] All environment variables documented in `.env.example`
- [ ] Database credentials rotated and stored securely
- [ ] Redis password changed from default
- [ ] Google service account credentials available
- [ ] Docker images built and tagged
- [ ] Database migrations tested in staging
- [ ] Backup of production database created

### Code Preparation

- [ ] All tests passing (`pytest tests/ -v`)
- [ ] Code coverage ≥85% (`pytest --cov=src --cov-report=html`)
- [ ] Linting passes (`ruff check .`)
- [ ] Type checking passes (`mypy src/`)
- [ ] Integration tests pass with Docker services
- [ ] Performance tests validate throughput >1,000 items/min

### Infrastructure

- [ ] PostgreSQL 16+ available and accessible
- [ ] Redis 7+ available and accessible
- [ ] Docker and Docker Compose installed
- [ ] Network connectivity verified
- [ ] Health check endpoints responding

---

## Deployment Steps

### 1. Pre-Deployment Backup

**Critical:** Always backup database before deployment.

```bash
# Create database backup
docker-compose exec postgres pg_dump -U marketbel_user -d marketbel > backup_$(date +%Y%m%d_%H%M%S).sql

# Verify backup file exists and is not empty
ls -lh backup_*.sql
```

### 2. Drain Queue (Zero-Downtime Deployment)

If deploying during active processing:

```bash
# Monitor queue depth
python scripts/monitor_queue.py

# Wait for queue to drain (optional, for zero-downtime)
# Or proceed with deployment (workers will resume processing)
```

### 3. Stop Services

```bash
# Stop all services gracefully
docker-compose down

# Verify services are stopped
docker-compose ps
```

### 4. Update Code

```bash
# Pull latest code
git pull origin main  # or your deployment branch

# Verify you're on the correct commit
git log -1
```

### 5. Build Docker Images

```bash
# Build worker image
docker-compose build worker

# Verify image was created
docker images | grep marketbel-worker
```

### 6. Run Database Migrations

**Important:** Run migrations before starting services.

```bash
# Start only database service
docker-compose up -d postgres

# Wait for database to be ready
docker-compose exec postgres pg_isready -U marketbel_user -d marketbel

# Run migrations
docker-compose run --rm worker alembic upgrade head

# Verify migration succeeded
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "\dt"
```

### 7. Start Services

```bash
# Start all services
docker-compose up -d

# Verify all services are running
docker-compose ps

# Check service health
docker-compose ps | grep -E "(healthy|unhealthy)"
```

### 8. Verify Deployment

```bash
# Check worker logs
docker-compose logs -f worker

# Check worker health
docker-compose exec worker python -m src.health_check

# Verify Redis connection
docker-compose exec worker python -c "from src.health_check import check_redis_connection; import asyncio; print(asyncio.run(check_redis_connection()))"

# Test queue processing (enqueue a test task)
python scripts/enqueue_task.py --parser-type stub --supplier-name "Deployment Test"
```

### 9. Monitor Post-Deployment

```bash
# Monitor logs for errors
docker-compose logs -f worker | grep -i error

# Monitor queue depth
watch -n 5 'python scripts/monitor_queue.py'

# Monitor database connections
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'marketbel';"
```

---

## Rollback Procedures

### When to Rollback

Rollback immediately if:
- Database migration fails or corrupts data
- Service crash loop prevents startup
- Data validation errors exceed 10% of processed items
- Queue processing stops entirely for >5 minutes
- Critical errors in logs indicate data corruption

### Rollback Steps

#### Step 1: Stop Services

```bash
docker-compose down
```

#### Step 2: Restore Database Backup

```bash
# Restore from backup
docker-compose up -d postgres
docker-compose exec -T postgres psql -U marketbel_user -d marketbel < backup_YYYYMMDD_HHMMSS.sql

# Verify restore succeeded
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "SELECT count(*) FROM suppliers;"
```

#### Step 3: Rollback Database Migration

```bash
# Rollback to previous migration
docker-compose run --rm worker alembic downgrade -1

# Or rollback to specific revision
docker-compose run --rm worker alembic downgrade <revision_id>
```

#### Step 4: Revert Code

```bash
# Revert to previous commit
git checkout <previous-commit-hash>

# Rebuild Docker image
docker-compose build worker
```

#### Step 5: Restart Services

```bash
# Start services with previous version
docker-compose up -d

# Verify services are healthy
docker-compose ps
docker-compose logs worker
```

#### Step 6: Restore Queue Messages (if needed)

If queue messages were lost:

```bash
# If you backed up queue messages before deployment
python scripts/requeue_from_backup.py < backup_queue.json
```

---

## Health Checks

### Service Health

```bash
# Check all service health statuses
docker-compose ps

# Expected output:
# NAME                STATUS
# marketbel-postgres  Up (healthy)
# marketbel-redis     Up (healthy)
# marketbel-worker    Up (healthy)
```

### Database Health

```bash
# Check database connectivity
docker-compose exec postgres pg_isready -U marketbel_user -d marketbel

# Check database size
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "SELECT pg_size_pretty(pg_database_size('marketbel'));"

# Check active connections
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'marketbel';"
```

### Redis Health

```bash
# Check Redis connectivity
docker-compose exec redis redis-cli --raw incr ping

# Check queue depth
docker-compose exec redis redis-cli LLEN arq:queue:default

# Check dead letter queue depth
docker-compose exec redis redis-cli LLEN arq:queue:dead
```

### Worker Health

```bash
# Run health check script
docker-compose exec worker python -m src.health_check

# Check worker logs for errors
docker-compose logs worker | grep -i error | tail -20

# Check worker process
docker-compose exec worker ps aux | grep arq
```

---

## Monitoring

### Key Metrics

Monitor these metrics post-deployment:

1. **Queue Depth:**
   ```bash
   python scripts/monitor_queue.py
   ```
   - Alert if queue depth > 1000
   - Alert if DLQ depth > 0

2. **Processing Rate:**
   ```bash
   docker-compose logs worker | grep "items_parsed" | tail -10
   ```
   - Target: >1,000 items/min
   - Alert if < 500 items/min

3. **Error Rate:**
   ```sql
   SELECT error_type, count(*) 
   FROM parsing_logs 
   WHERE created_at > NOW() - INTERVAL '1 hour'
   GROUP BY error_type;
   ```
   - Alert if error rate > 10%

4. **Database Connections:**
   ```sql
   SELECT count(*) FROM pg_stat_activity WHERE datname = 'marketbel';
   ```
   - Alert if connections > 80% of pool size (20)

5. **Memory Usage:**
   ```bash
   docker stats marketbel-worker --no-stream
   ```
   - Alert if memory > 512MB per worker

### Log Monitoring

```bash
# Watch for errors
docker-compose logs -f worker | grep -i error

# Watch for warnings
docker-compose logs -f worker | grep -i warning

# Watch for task completions
docker-compose logs -f worker | grep "task completed"
```

---

## Troubleshooting

### Service Won't Start

**Symptoms:** `docker-compose up` fails or services exit immediately

**Diagnosis:**
```bash
# Check logs
docker-compose logs worker
docker-compose logs postgres
docker-compose logs redis

# Check service status
docker-compose ps
```

**Common Causes:**
- Missing environment variables
- Database connection failure
- Redis connection failure
- Invalid credentials
- Port conflicts

**Solution:**
1. Verify `.env` file exists and has all required variables
2. Check database is accessible: `docker-compose exec postgres pg_isready`
3. Check Redis is accessible: `docker-compose exec redis redis-cli ping`
4. Verify credentials are correct

### Database Migration Fails

**Symptoms:** `alembic upgrade head` fails with error

**Diagnosis:**
```bash
# Check current migration version
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "SELECT version_num FROM alembic_version;"

# Check migration errors
docker-compose run --rm worker alembic upgrade head --verbose
```

**Solution:**
1. Review migration file for syntax errors
2. Check if migration conflicts with existing schema
3. Test migration in staging first
4. Rollback if needed: `alembic downgrade -1`

### Queue Not Processing

**Symptoms:** Tasks enqueued but not processed

**Diagnosis:**
```bash
# Check queue depth
python scripts/monitor_queue.py

# Check worker logs
docker-compose logs worker | tail -50

# Check if worker is running
docker-compose exec worker ps aux | grep arq
```

**Solution:**
1. Verify worker is running: `docker-compose ps worker`
2. Check Redis connection: `docker-compose exec worker python -m src.health_check`
3. Restart worker: `docker-compose restart worker`
4. Check for errors in logs

### High Error Rate

**Symptoms:** Many entries in `parsing_logs` table

**Diagnosis:**
```sql
SELECT error_type, count(*) as error_count
FROM parsing_logs
WHERE created_at > NOW() - INTERVAL '1 hour'
GROUP BY error_type
ORDER BY error_count DESC;
```

**Solution:**
1. Review error messages: `SELECT error_message FROM parsing_logs WHERE error_type = 'ValidationError' LIMIT 10;`
2. Check source data quality
3. Verify parser configuration
4. Update parser if needed

### Performance Degradation

**Symptoms:** Processing rate < 1,000 items/min

**Diagnosis:**
```bash
# Check processing time per task
docker-compose logs worker | grep "processing_time"

# Check database query performance
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "EXPLAIN ANALYZE SELECT * FROM supplier_items LIMIT 100;"

# Check connection pool usage
docker-compose exec postgres psql -U marketbel_user -d marketbel -c "SELECT count(*) FROM pg_stat_activity WHERE datname = 'marketbel';"
```

**Solution:**
1. Check database indexes: `\d+ supplier_items`
2. Analyze slow queries
3. Increase worker count: `MAX_WORKERS=10`
4. Optimize parser code

---

## Emergency Procedures

### Complete Service Failure

If all services are down:

1. **Stop all services:**
   ```bash
   docker-compose down
   ```

2. **Check system resources:**
   ```bash
   df -h  # Disk space
   free -h  # Memory
   docker system df  # Docker disk usage
   ```

3. **Restart services:**
   ```bash
   docker-compose up -d
   ```

4. **Verify health:**
   ```bash
   docker-compose ps
   docker-compose logs worker
   ```

### Data Corruption

If data corruption is suspected:

1. **Stop services immediately:**
   ```bash
   docker-compose down
   ```

2. **Restore from backup:**
   ```bash
   docker-compose up -d postgres
   docker-compose exec -T postgres psql -U marketbel_user -d marketbel < backup_YYYYMMDD_HHMMSS.sql
   ```

3. **Verify data integrity:**
   ```sql
   SELECT count(*) FROM suppliers;
   SELECT count(*) FROM supplier_items;
   SELECT count(*) FROM price_history;
   ```

4. **Contact database administrator if needed**

### Security Incident

If credentials are compromised:

1. **Rotate all credentials immediately:**
   - Database password
   - Redis password
   - Google service account credentials

2. **Update `.env` file with new credentials**

3. **Restart all services:**
   ```bash
   docker-compose down
   docker-compose up -d
   ```

4. **Review access logs for unauthorized access**

---

## Post-Deployment Validation

After successful deployment, validate:

- [ ] All services healthy: `docker-compose ps`
- [ ] Health checks passing: `docker-compose exec worker python -m src.health_check`
- [ ] Queue processing: Enqueue test task and verify processing
- [ ] Database accessible: `docker-compose exec postgres psql -U marketbel_user -d marketbel -c "SELECT 1;"`
- [ ] Redis accessible: `docker-compose exec redis redis-cli ping`
- [ ] No errors in logs: `docker-compose logs worker | grep -i error | tail -10`
- [ ] Performance acceptable: Processing rate > 1,000 items/min

---

## Contact Information

**On-Call Engineer:** [Contact Info]  
**Database Administrator:** [Contact Info]  
**DevOps Team:** [Contact Info]

**Emergency Escalation:** [Escalation Process]

---

**Last Updated:** 2025-11-24  
**Next Review:** After next deployment

