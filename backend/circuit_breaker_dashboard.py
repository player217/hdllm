"""
Circuit Breaker Dashboard for HD현대미포 Gauss-1 RAG System
Author: Claude Code
Date: 2025-01-26
Description: Phase 2A-2 - 운영 지표 기반 Circuit Breaker 모니터링 대시보드
"""

import asyncio
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from resource_manager import get_resource_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

@router.get("/circuit-breaker", response_class=HTMLResponse)
async def circuit_breaker_dashboard():
    """Circuit Breaker 모니터링 대시보드 HTML"""
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>HD현대미포 Gauss-1 - Circuit Breaker Dashboard</title>
        <style>
            body { 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 20px; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: #333;
            }
            .container { 
                max-width: 1400px; 
                margin: 0 auto; 
                background: white;
                border-radius: 10px;
                padding: 30px;
                box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            }
            .header {
                text-align: center;
                margin-bottom: 30px;
                padding-bottom: 20px;
                border-bottom: 2px solid #eee;
            }
            .header h1 {
                color: #2c3e50;
                margin: 0;
                font-size: 2.5em;
            }
            .header .subtitle {
                color: #7f8c8d;
                font-size: 1.1em;
                margin-top: 10px;
            }
            .metrics-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-bottom: 30px;
            }
            .metric-card {
                background: #f8f9fa;
                border-radius: 8px;
                padding: 20px;
                border-left: 4px solid #3498db;
                transition: transform 0.2s;
            }
            .metric-card:hover {
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.1);
            }
            .metric-card.danger {
                border-left-color: #e74c3c;
                background: #fdf2f2;
            }
            .metric-card.warning {
                border-left-color: #f39c12;
                background: #fefbf3;
            }
            .metric-card.success {
                border-left-color: #27ae60;
                background: #f2f9f6;
            }
            .metric-title {
                font-size: 0.9em;
                color: #666;
                margin-bottom: 5px;
                text-transform: uppercase;
                letter-spacing: 1px;
            }
            .metric-value {
                font-size: 2.2em;
                font-weight: bold;
                margin-bottom: 5px;
            }
            .metric-detail {
                font-size: 0.85em;
                color: #888;
            }
            .status-indicator {
                display: inline-block;
                width: 12px;
                height: 12px;
                border-radius: 50%;
                margin-right: 8px;
            }
            .status-closed { background-color: #27ae60; }
            .status-open { background-color: #e74c3c; }
            .status-half-open { background-color: #f39c12; }
            .breaker-list {
                background: white;
                border-radius: 8px;
                overflow: hidden;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }
            .breaker-item {
                padding: 15px 20px;
                border-bottom: 1px solid #eee;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .breaker-item:last-child {
                border-bottom: none;
            }
            .breaker-name {
                font-weight: bold;
                font-size: 1.1em;
            }
            .breaker-metrics {
                display: flex;
                gap: 20px;
                font-size: 0.9em;
            }
            .refresh-btn {
                background: #3498db;
                color: white;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                font-size: 1em;
                transition: background 0.2s;
            }
            .refresh-btn:hover {
                background: #2980b9;
            }
            .last-updated {
                text-align: center;
                color: #666;
                font-size: 0.9em;
                margin-top: 20px;
            }
            @keyframes pulse {
                0% { opacity: 1; }
                50% { opacity: 0.5; }
                100% { opacity: 1; }
            }
            .loading { animation: pulse 1.5s infinite; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🔧 Circuit Breaker Dashboard</h1>
                <div class="subtitle">HD현대미포 Gauss-1 RAG System - Phase 2A-2 운영 모니터링</div>
                <button class="refresh-btn" onclick="refreshData()">🔄 새로고침</button>
            </div>
            
            <div class="metrics-grid" id="metricsGrid">
                <div class="metric-card loading">
                    <div class="metric-title">전체 Circuit Breaker</div>
                    <div class="metric-value" id="totalBreakers">-</div>
                    <div class="metric-detail">활성 상태 모니터링</div>
                </div>
                
                <div class="metric-card loading">
                    <div class="metric-title">열린 브레이커</div>
                    <div class="metric-value" id="openBreakers">-</div>
                    <div class="metric-detail">장애 상태</div>
                </div>
                
                <div class="metric-card loading">
                    <div class="metric-title">평균 에러율</div>
                    <div class="metric-value" id="avgErrorRate">-</div>
                    <div class="metric-detail">최근 30초 기준</div>
                </div>
                
                <div class="metric-card loading">
                    <div class="metric-title">평균 P95 지연시간</div>
                    <div class="metric-value" id="avgP95">-</div>
                    <div class="metric-detail">밀리초</div>
                </div>
            </div>
            
            <div class="breaker-list" id="breakerList">
                <div class="breaker-item">
                    <div class="loading">Circuit Breaker 정보 로딩 중...</div>
                </div>
            </div>
            
            <div class="last-updated" id="lastUpdated">
                마지막 업데이트: -
            </div>
        </div>
        
        <script>
            async function fetchCircuitBreakerStatus() {
                try {
                    const response = await fetch('/dashboard/circuit-breaker/status');
                    const data = await response.json();
                    updateDashboard(data);
                } catch (error) {
                    console.error('Failed to fetch circuit breaker status:', error);
                    showError('Circuit Breaker 상태를 가져올 수 없습니다.');
                }
            }
            
            function updateDashboard(data) {
                // 전체 메트릭 업데이트
                const totalBreakers = data.circuit_breakers.length;
                const openBreakers = data.circuit_breakers.filter(cb => cb.state === 'open').length;
                const avgErrorRate = data.circuit_breakers.reduce((sum, cb) => sum + cb.error_rate, 0) / totalBreakers;
                const avgP95 = data.circuit_breakers.reduce((sum, cb) => sum + cb.p95_latency_ms, 0) / totalBreakers;
                
                document.getElementById('totalBreakers').textContent = totalBreakers;
                document.getElementById('openBreakers').textContent = openBreakers;
                document.getElementById('avgErrorRate').textContent = (avgErrorRate * 100).toFixed(1) + '%';
                document.getElementById('avgP95').textContent = Math.round(avgP95) + 'ms';
                
                // 카드 상태 업데이트
                updateCardStatus('openBreakers', openBreakers > 0 ? 'danger' : 'success');
                updateCardStatus('avgErrorRate', avgErrorRate > 0.2 ? 'danger' : (avgErrorRate > 0.1 ? 'warning' : 'success'));
                updateCardStatus('avgP95', avgP95 > 5000 ? 'danger' : (avgP95 > 3000 ? 'warning' : 'success'));
                
                // Circuit Breaker 리스트 업데이트
                const breakerList = document.getElementById('breakerList');
                breakerList.innerHTML = data.circuit_breakers.map(cb => `
                    <div class="breaker-item">
                        <div>
                            <span class="status-indicator status-${cb.state}"></span>
                            <span class="breaker-name">${cb.name}</span>
                        </div>
                        <div class="breaker-metrics">
                            <span>상태: ${getStateText(cb.state)}</span>
                            <span>에러율: ${(cb.error_rate * 100).toFixed(1)}%</span>
                            <span>P95: ${Math.round(cb.p95_latency_ms)}ms</span>
                            <span>요청수: ${cb.recent_requests}</span>
                            <span>실패수: ${cb.failure_count}</span>
                        </div>
                    </div>
                `).join('');
                
                // 마지막 업데이트 시간
                document.getElementById('lastUpdated').textContent = 
                    '마지막 업데이트: ' + new Date().toLocaleString('ko-KR');
                
                // 로딩 상태 제거
                document.querySelectorAll('.loading').forEach(el => el.classList.remove('loading'));
            }
            
            function updateCardStatus(cardId, status) {
                const card = document.getElementById(cardId).closest('.metric-card');
                card.className = `metric-card ${status}`;
            }
            
            function getStateText(state) {
                const stateMap = {
                    'closed': '정상',
                    'open': '열림',
                    'half_open': '반열림'
                };
                return stateMap[state] || state;
            }
            
            function showError(message) {
                const breakerList = document.getElementById('breakerList');
                breakerList.innerHTML = `
                    <div class="breaker-item">
                        <div style="color: #e74c3c;">❌ ${message}</div>
                    </div>
                `;
            }
            
            function refreshData() {
                document.querySelectorAll('.metric-card').forEach(card => card.classList.add('loading'));
                fetchCircuitBreakerStatus();
            }
            
            // 초기 로딩 및 자동 새로고침
            fetchCircuitBreakerStatus();
            setInterval(fetchCircuitBreakerStatus, 5000); // 5초마다 자동 새로고침
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@router.get("/circuit-breaker/status")
async def get_circuit_breaker_status():
    """Circuit Breaker 상태 API"""
    try:
        resource_manager = await get_resource_manager()
        
        # 모든 Circuit Breaker 상태 수집
        circuit_breakers = []
        
        # Ollama Circuit Breaker
        if hasattr(resource_manager.ollama_token_bucket, 'circuit_breaker'):
            ollama_cb = resource_manager.ollama_token_bucket.circuit_breaker
            circuit_breakers.append(ollama_cb.get_status())
        
        # Qdrant Circuit Breakers
        for pool_name, pool in resource_manager.qdrant_pools.items():
            if hasattr(pool, 'circuit_breaker'):
                cb_status = pool.circuit_breaker.get_status()
                cb_status['name'] = f"qdrant_{pool_name}"
                circuit_breakers.append(cb_status)
        
        # 전체 시스템 상태 계산
        total_breakers = len(circuit_breakers)
        open_breakers = len([cb for cb in circuit_breakers if cb['state'] == 'open'])
        half_open_breakers = len([cb for cb in circuit_breakers if cb['state'] == 'half_open'])
        
        system_status = "healthy"
        if open_breakers > 0:
            system_status = "degraded"
        elif half_open_breakers > 0:
            system_status = "recovering"
        
        return {
            "timestamp": datetime.now().isoformat(),
            "system_status": system_status,
            "summary": {
                "total_breakers": total_breakers,
                "open_breakers": open_breakers,
                "half_open_breakers": half_open_breakers,
                "closed_breakers": total_breakers - open_breakers - half_open_breakers
            },
            "circuit_breakers": circuit_breakers
        }
        
    except Exception as e:
        logger.error(f"Failed to get circuit breaker status: {e}")
        raise HTTPException(status_code=500, detail="Circuit Breaker 상태를 가져올 수 없습니다")

@router.get("/circuit-breaker/metrics/history")
async def get_circuit_breaker_history(hours: int = 1):
    """Circuit Breaker 메트릭 히스토리 (추후 구현)"""
    # TODO: 실제 구현에서는 시계열 데이터베이스(InfluxDB 등)에서 메트릭 히스토리를 가져옴
    return {
        "message": "Circuit Breaker 히스토리 기능은 Phase 2B에서 구현 예정",
        "requested_hours": hours,
        "available_from": "Phase 2B-1"
    }

@router.post("/circuit-breaker/{breaker_name}/reset")
async def reset_circuit_breaker(breaker_name: str):
    """Circuit Breaker 수동 리셋"""
    try:
        resource_manager = await get_resource_manager()
        
        # 해당 Circuit Breaker 찾기 및 리셋
        breaker = None
        
        if breaker_name == "ollama" and hasattr(resource_manager.ollama_token_bucket, 'circuit_breaker'):
            breaker = resource_manager.ollama_token_bucket.circuit_breaker
        elif breaker_name.startswith("qdrant_"):
            pool_name = breaker_name.replace("qdrant_", "")
            if pool_name in resource_manager.qdrant_pools:
                pool = resource_manager.qdrant_pools[pool_name]
                if hasattr(pool, 'circuit_breaker'):
                    breaker = pool.circuit_breaker
        
        if not breaker:
            raise HTTPException(status_code=404, detail=f"Circuit Breaker '{breaker_name}'을 찾을 수 없습니다")
        
        # 수동 리셋 (CLOSED 상태로 강제 전환)
        with breaker.lock:
            breaker.state = breaker.state.__class__.CLOSED  # CircuitBreakerState.CLOSED
            breaker.failure_count = 0
            breaker.last_failure_time = 0
            breaker.metrics.clear()
        
        logger.info(f"🔧 Circuit Breaker '{breaker_name}' manually reset to CLOSED state")
        
        return {
            "message": f"Circuit Breaker '{breaker_name}'이 성공적으로 리셋되었습니다",
            "new_state": "closed",
            "reset_time": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to reset circuit breaker {breaker_name}: {e}")
        raise HTTPException(status_code=500, detail="Circuit Breaker 리셋에 실패했습니다")