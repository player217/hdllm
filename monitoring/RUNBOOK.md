# RAG System Production Monitoring Runbook

## P1-4 모니터링 구현 완료
작성일: 2025-01-28
버전: 1.0

## 📊 Overview

HD현대미포 Gauss-1 RAG 시스템의 프로덕션 모니터링이 완료되었습니다.
Prometheus 메트릭 수집, Grafana 대시보드, 알림 규칙이 구성되어 있습니다.

## 🚀 Quick Start

### 1. Prometheus 설정

```yaml
# prometheus.yml
global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    environment: 'production'
    site: 'hdmipo'

rule_files:
  - '/etc/prometheus/rules/rules-rag.yml'

scrape_configs:
  - job_name: 'rag-backend'
    static_configs:
      - targets: ['localhost:8080']
    metrics_path: '/metrics'
```

### 2. Grafana 대시보드 Import

1. Grafana 접속 → Dashboards → Import
2. `monitoring/dashboard-rag.json` 파일 업로드
3. Prometheus 데이터소스 선택
4. Import 클릭

### 3. 알림 채널 설정

```yaml
# alertmanager.yml
route:
  receiver: 'team-platform'
  group_wait: 10s
  group_interval: 5m
  repeat_interval: 1h
  
receivers:
  - name: 'team-platform'
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_URL}'
        channel: '#rag-alerts'
        title: 'RAG System Alert'
```

## 📈 Key Metrics

### HTTP 메트릭
- `rag_http_requests_total`: 총 요청 수
- `rag_http_request_duration_seconds`: 요청 처리 시간
- `rag_active_connections`: 활성 연결 수

### Business 메트릭
- `rag_rag_requests_total`: RAG 요청 수
- `rag_embed_seconds`: 임베딩 생성 시간
- `rag_search_seconds`: 벡터 검색 시간
- `rag_qdrant_errors_total`: Qdrant 에러

### Cache 메트릭
- `rag_cache_hits_total`: 캐시 히트
- `rag_cache_misses_total`: 캐시 미스

### LLM 메트릭
- `rag_llm_tokens_total`: LLM 토큰 사용량

## 🚨 Alert Runbook

### RAGHighErrorRate
**증상**: RAG 에러율 5% 초과
**대응**:
1. `/metrics` 엔드포인트에서 에러 유형 확인
2. 로그에서 구체적인 에러 메시지 확인
3. Qdrant 서비스 상태 점검
4. Backend 서버 재시작 고려

### AskP95LatencyHigh
**증상**: /ask P95 지연 2초 초과
**대응**:
1. 활성 연결 수 확인
2. 캐시 히트율 확인
3. Qdrant 응답 시간 체크
4. 필요시 스케일 아웃

### QdrantErrorSpike
**증상**: Qdrant 에러 급증
**대응**:
1. Qdrant 프로세스 확인: `ps aux | grep qdrant`
2. 포트 점검: `netstat -an | grep 6333`
3. 스토리지 용량 확인
4. Qdrant 재시작: `systemctl restart qdrant`

### EmbeddingCacheMissRateHigh
**증상**: 임베딩 캐시 미스율 50% 초과
**대응**:
1. 캐시 크기 확인
2. 쿼리 패턴 분석
3. 캐시 TTL 조정 고려
4. 캐시 크기 증가 검토

### ActiveConnectionsHigh
**증상**: 활성 연결 100개 초과
**대응**:
1. 트래픽 패턴 확인
2. 로드 밸런서 설정 검토
3. 백엔드 인스턴스 추가
4. Rate limiting 설정 강화

## 📋 Health Check Script

```bash
#!/bin/bash
# health_check.sh

# Check backend
curl -f http://localhost:8080/health || echo "Backend unhealthy"

# Check metrics endpoint
curl -s http://localhost:8080/metrics | grep -q "rag_http_requests_total" || echo "Metrics not exposed"

# Check Qdrant
curl -f http://localhost:6333/health || echo "Qdrant unhealthy"

# Check Ollama
curl -f http://localhost:11434/api/tags || echo "Ollama unhealthy"
```

## 🔄 Regular Maintenance

### Daily
- [ ] Check dashboard for anomalies
- [ ] Review alert history
- [ ] Verify backup completion

### Weekly
- [ ] Analyze performance trends
- [ ] Review error logs
- [ ] Update documentation

### Monthly
- [ ] Performance optimization review
- [ ] Capacity planning
- [ ] Security audit

## 📝 DoD Checklist ✅

### Phase 1-4 Monitoring Complete:

✅ **Metrics Implementation**
- [x] Prometheus client 설치
- [x] HTTP request/response 메트릭
- [x] Business logic 메트릭
- [x] Cache performance 메트릭
- [x] Error tracking

✅ **Endpoints**
- [x] `/metrics` endpoint 구현
- [x] Localhost-only 보안 설정
- [x] Prometheus format 지원

✅ **Integration**
- [x] Request middleware 통합
- [x] RAG pipeline 메트릭
- [x] Resource manager 메트릭
- [x] Error handling 메트릭

✅ **Configuration**
- [x] Environment variables
- [x] Metric namespace 설정
- [x] Feature toggle 지원

✅ **Monitoring Assets**
- [x] Prometheus alert rules
- [x] Grafana dashboard JSON
- [x] Operational runbook

✅ **Testing**
- [x] Metrics endpoint 동작 확인
- [x] Counter/Histogram 수집 확인
- [x] Label cardinality 적정

## 🎯 Next Steps

### P1-5: Security Hardening (Recommended)
- JWT authentication
- Rate limiting
- Input validation
- Audit logging

### P2: Performance Optimization
- GPU acceleration
- Parallel processing
- Advanced caching
- Query optimization

### P3: High Availability
- Multi-instance deployment
- Load balancing
- Auto-scaling
- Disaster recovery

## 📚 References

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Dashboards](https://grafana.com/docs/)
- [FastAPI Metrics](https://fastapi.tiangolo.com/)
- [RAG System Architecture](../CLAUDE.md)

---

**Status**: ✅ P1-4 Implementation Complete
**Version**: 1.0
**Date**: 2025-01-28
**Author**: Claude Code