# P1-1 E2E Integration Test Guide

## Current Status

### ✅ Completed (Unit/Mock Testing)
- **Logic validation**: Return schema, status values, client access
- **Mock testing**: 20/20 tests passed
- **Documentation**: Complete

### ⏳ Pending (Real E2E Testing)
- **Live service testing**: FastAPI + Qdrant + Ollama
- **Smoke tests**: With actual endpoints
- **Collection validation**: With real Qdrant

---

## Real E2E Test Requirements

### Prerequisites

1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

2. **Start Services**
```bash
# Terminal 1: Qdrant
docker run -p 6333:6333 qdrant/qdrant
# OR use local Qdrant installation

# Terminal 2: Ollama  
ollama serve
# Ensure model is available: ollama pull bge-m3
```

3. **Configure Environment**
```bash
# Copy test environment
cp .env.test .env

# Windows: Fix encoding
chcp 65001
set PYTHONIOENCODING=utf-8
```

---

## E2E Test Execution

### Method 1: Automated Runner (Recommended)
```bash
python run_e2e_tests.py
```

This will automatically:
1. Check prerequisites (Qdrant, Ollama)
2. Start FastAPI server
3. Run smoke tests
4. Validate collections
5. Check security
6. Generate report

### Method 2: Manual Step-by-Step

#### Step 1: Server Startup Test
```bash
# Start server
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

# Expected logs:
# ✅ "Starting collection validation"
# ✅ overall_status: "success" (or "warning")
# ✅ "Dynamic collection namespace: {'mail': '...', 'doc': '...'}"
```

#### Step 2: Smoke Tests
```bash
# Run pytest smoke tests
pytest backend/tests/test_smoke.py::TestSmoke::test_app_boot_and_ask_basic -q
pytest backend/tests/test_smoke.py::TestSmoke::test_status_endpoint -q

# Manual API test
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "test", "source": "mail"}'
```

#### Step 3: Collection Validation
```bash
python scripts/validate_collections.py --sources mail doc --verbose

# Expected: 
# ✅ expected_dimension matches collection dimension
# ✅ overall_status in ["success", "warning", "error"]
```

#### Step 4: Security Checks
```bash
# Check for security issues
git grep -n 'allow_origins=\["\*"\]'
git grep -n 'mail_my_documents\|doc_my_documents' | grep -v 'fallback\|legacy'
```

---

## Success Criteria

### Pass Conditions
1. **Server starts** without crashes
2. **Status shows** "success" or "warning" (not "error")
3. **Smoke tests** pass (2/2)
4. **API responds** with 200 and correct Content-Type
5. **Collections validate** with matching dimensions

### Acceptable Warnings
- Collections not found (if first run)
- Warnings in validation (non-critical)
- Legacy names in fallback code

### Failure Conditions
- Server crashes on startup
- overall_status = "error"
- Dimension mismatch
- Smoke tests fail
- API returns 500 errors

---

## Common Issues & Solutions

### Issue 1: ModuleNotFoundError
```
ModuleNotFoundError: No module named 'fastapi'
```
**Solution**: `pip install -r requirements.txt`

### Issue 2: Qdrant Connection Error
```
Connection refused: 127.0.0.1:6333
```
**Solution**: Start Qdrant service

### Issue 3: Embedding Model Error
```
No module named 'sentence_transformers'
```
**Solution**: Set `EMBED_BACKEND=ollama` in .env

### Issue 4: Windows Encoding Error
```
UnicodeDecodeError: 'cp949' codec can't decode
```
**Solution**: 
```bash
chcp 65001
set PYTHONIOENCODING=utf-8
```

---

## Regression Tests

Two pytest files have been added for regression prevention:

### backend/tests/test_startup_validation.py
- Tests return schema structure
- Validates all required fields
- Ensures backward compatibility

### backend/tests/test_status_values.py  
- Tests status values (success/warning/error)
- Ensures no "ok" value used
- Validates error conditions

Run regression tests:
```bash
pytest backend/tests/test_startup_validation.py -v
pytest backend/tests/test_status_values.py -v
```

---

## Test Results Documentation

### Automated Results
Running `run_e2e_tests.py` generates:
- Console output with pass/fail status
- Detailed logs for each test
- Summary with statistics

### Manual Checklist
- [ ] Prerequisites checked (Qdrant, Ollama)
- [ ] Dependencies installed
- [ ] Server starts successfully
- [ ] Startup validation passes
- [ ] Smoke tests pass (2/2)
- [ ] /ask endpoint works
- [ ] /status shows namespace
- [ ] Collection validation succeeds
- [ ] Security checks pass

---

## Certification

When all E2E tests pass:

**P1-1 Implementation Certified**:
- ✅ Unit tests: 20/20 passed
- ✅ E2E tests: 4/4 passed
- ✅ Production ready
- ✅ Risk mitigated

---

## Summary

**Current State**: Unit/mock testing complete (100% pass)
**Next Step**: Run E2E tests with live services
**Command**: `python run_e2e_tests.py`

Once E2E tests pass, P1-1 is fully validated and production-ready.

---

**Document Version**: 1.0  
**Date**: 2025-01-26  
**Author**: Claude Code