# Architecture Compliance Fixes - April 2026

## Overview
The backend has been reviewed against the system architecture review and the following critical issues have been fixed.

## ✅ Fixed Issues

### 1. **FastAPI Deprecated Event Handlers** 
**File:** `backend/app/main.py`

**Issue:** The code was using the deprecated `@app.on_event("startup")` decorator, which triggers a deprecation warning in FastAPI.

**Fix Applied:**
- Added `from contextlib import asynccontextmanager` import
- Replaced `@app.on_event("startup")` with a modern `lifespan` context manager
- Converted the startup handler to work within the lifespan context

**Before:**
```python
@app.on_event("startup")
def ensure_schema_columns():
    # startup logic
```

**After:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    _ensure_schema_columns()
    yield
    # Shutdown - add any cleanup here if needed

app = FastAPI(lifespan=lifespan)
```

**Status:** ✅ Verified - Backend starts without deprecation warnings

---

## ✅ Verified Compliance

### 2. **Transaction Safety & Concurrency Control**
**File:** `backend/app/sales.py` (create_order function)

**Status:** ✅ COMPLIANT
- ✅ Row-level locking implemented with `with_for_update()` on products
- ✅ Idempotency-Key support for checkout operations
- ✅ Transaction scope properly managed with `db.commit()`
- ✅ Inventory reservation atomically locked during checkout

### 3. **Payment Callback Idempotency**
**File:** `backend/app/payments.py`

**Status:** ✅ COMPLIANT
- ✅ Idempotency-Key support in payment initiation
- ✅ Transaction reuse detection to prevent duplicate charges
- ✅ Payment attempt tracking with idempotency tracking
- ✅ Duplicate transaction detection before processing

### 4. **Multi-Item Order Support**
**File:** `backend/app/sales.py`

**Status:** ✅ COMPLIANT
- ✅ Multi-item checkout supported with grouping by seller/provider
- ✅ Atomic inventory updates for all items
- ✅ Order creation handles multiple items per transaction

### 5. **Order Status History & Normalization**
**Files:** `backend/app/sales.py`, `backend/app/order_runtime.py`

**Status:** ✅ COMPLIANT
- ✅ Order model properly separated from legacy Sale records
- ✅ OrderItem records created and tracked
- ✅ Order status history maintained with `log_order_status()`
- ✅ Delivery Failed state explicitly handled and tracked
- ✅ Audit logs created for sensitive actions

### 6. **Persistent Chat & Messaging**
**File:** `backend/app/business.py`, conversation thread functions

**Status:** ✅ COMPLIANT
- ✅ Conversation threads stored persistently
- ✅ Message receipt tracking implemented
- ✅ Read receipt handling for messages
- ✅ Shared order thread for customer, seller, and logistics

---

## ⚠️ Remaining Architecture Work (Per System Review)

### Phase 1: Schema Management ⚠️
**Priority:** HIGH

The code currently runs runtime schema patching at startup via the `_ensure_schema_columns()` function. While this works for legacy databases, the architecture review recommends:

**Recommendations:**
- [ ] Move all schema ALTER TABLE statements to Alembic migrations
- [ ] Remove the `ALTER TABLE IF NOT EXISTS` pattern from startup
- [ ] Use Alembic for all future schema evolution
- [ ] Set up migration validation in CI/CD pipeline

**Impact:** Once migrated, deployments will be safer and schema drift will be eliminated.

### Phase 2: File Upload Storage 
**Priority:** MEDIUM

The code currently stores uploads on the local filesystem:
```python
uploads_dir = Path(__file__).resolve().parents[1] / "uploads"
```

**Recommendations:**
- [ ] Migrate to Azure Blob Storage or similar cloud object storage
- [ ] Update file path references to use object store URLs
- [ ] Implement signed URLs for secure file access
- [ ] Set up lifecycle policies for old uploads

**Impact:** Uploads will survive service redeploys and be resilient across multiple instances.

### Phase 3: Async Queue & Background Jobs
**Priority:** MEDIUM

**Recommendations:**
- [ ] Implement async queue for notifications (currently background_tasks are basic)
- [ ] Add retry logic for failed notifications
- [ ] Implement dead-letter handling for failed jobs
- [ ] Add metrics for job throughput and failures

**Impact:** System will scale better and be more resilient to slow external services.

### Phase 4: Observability & Monitoring
**Priority:** MEDIUM

**Recommendations:**
- [ ] Add structured logging with correlation IDs
- [ ] Implement metrics for: order throughput, payment success rate, delivery SLA
- [ ] Add alerts for: failed payments, dispatch backlog, websocket failures
- [ ] Create dashboard for operational health

**Impact:** Operations team will have visibility into system health and performance.

---

## Testing & Validation

### Backend Startup Test
✅ **PASSED** - Backend starts successfully on port 8001 without errors or deprecation warnings

### Functional Areas Verified
- ✅ Order creation and inventory locking works as expected
- ✅ Multi-item cart checkout supported
- ✅ Payment idempotency prevents duplicate charges
- ✅ Order status transitions tracked correctly
- ✅ Conversation threads persist and are accessible

---

## Developer Notes

1. **FastAPI Lifespan Handlers:** The modern approach uses async context managers. If you need to add shutdown logic, add it after the `yield` statement in the `lifespan()` function.

2. **Alembic Migrations:** All future schema changes should use Alembic. Do NOT add more `ALTER TABLE` statements to `main.py`.

3. **Transactional Guarantees:** The current code properly uses SQLAlchemy sessions for transaction management. Always ensure database operations are within the session context.

4. **Idempotency:** Payment and order creation operations rely on idempotency keys. Clients should always provide these headers for retry-safety.

---

## Next Steps

1. ✅ **Immediate:** Deploy the lifespan handler fix (already done)
2. **Short-term (Next sprint):** Create Alembic migration for schema consolidation
3. **Medium-term:** Migrate file uploads to cloud storage
4. **Long-term:** Implement async queue and observability

---

## References
- System Architecture Review: `docs/system-architecture-review.md`
- FastAPI Lifespan Docs: https://fastapi.tiangolo.com/advanced/events/
- Alembic Docs: https://alembic.sqlalchemy.org/
