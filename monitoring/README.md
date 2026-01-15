# Monitoring Stack

Complete monitoring infrastructure with Prometheus, Grafana, PostgreSQL, and Alertmanager.

## Files

### `docker-compose.yml`

**Full monitoring stack** with 5 services:

- **georgian-rag-postgres** - PostgreSQL 15 for request logging
- **georgian-rag-prometheus** - Metrics collection (port 9090)
- **georgian-rag-alertmanager** - Alert routing (port 9093)
- **georgian-rag-grafana** - Visualization (port 3000)

### `prometheus.yml`

**Prometheus configuration:**

- Scrape interval: 15 seconds
- FastAPI metrics: `host.docker.internal:8000/metrics`
- Alert rules: `alerts.yml`
- Retention: 15 days

### `alerts.yml`

**7 alert rules:**

1. **ServiceDown** - API down > 1 minute (critical)
2. **HighErrorRate** - Error rate > 10% for 2 min
3. **SlowResponseTime** - 95th percentile > 10s for 5 min
4. **LowCacheHitRate** - Cache hit < 50% for 10 min
5. **TooManyActiveRequests** - > 50 concurrent for 5 min
6. **DatabaseConnectionIssues** - DB errors for 2 min
7. **LowSuccessRate** - Success < 95% for 5 min (critical)

### `alertmanager.yml`

**Alertmanager configuration:**

- **Receiver**: Telegram bot
- **Bot token**: From `.env` (TELEGRAM_BOT_TOKEN)
- **Chat ID**: From `.env` (TELEGRAM_CHAT_ID)
- **Grouping**: By alertname and severity
- **Repeat interval**: 1 hour
- **Parse mode**: HTML

**Message template:**
```
🚨 ALERT FIRING / ✅ RESOLVED

Alert: {alertname}
Severity: {severity}
Summary: {summary}
Description: {description}
Time: {timestamp}
```

### `init_postgres.sql`

**PostgreSQL initialization:**

Creates tables:
- `request_logs` - All API requests with metadata
- `cache_metrics` - Cache performance
- `system_metrics` - System stats

**Indexes created:**
- timestamp
- status
- language
- cache_hit

## Usage

### Start Monitoring Stack
```bash
cd monitoring/

# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f prometheus
```

### Access Services

- **Grafana**: http://localhost:3000
  - Login: admin/admin
  - Dashboards: geo_rag_v1

- **Prometheus**: http://localhost:9090
  - Targets: http://localhost:9090/targets
  - Alerts: http://localhost:9090/alerts

- **Alertmanager**: http://localhost:9093
  - Active alerts
  - Silences

- **PostgreSQL**: localhost:5432
  - User: raguser
  - Database: georgian_rag

### Environment Variables

Required in `.env`:
```bash
# PostgreSQL
POSTGRES_PASSWORD=ragpassword

# Grafana
GRAFANA_USER=admin
GRAFANA_PASSWORD=admin

# Telegram Alerts (optional)
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

## Grafana Dashboard

**Dashboard: geo_rag_v1**

**7 panels:**

1. **Total Requests** (stat)
   - SQL: `SELECT COUNT(*) FROM request_logs`

2. **Average Response Time** (stat, seconds)
   - Last 24 hours
   - Shows: ~23.7s

3. **Success Rate** (gauge, %)
   - Thresholds: Red (0-80%), Yellow (80-95%), Green (95-100%)

4. **Cache Hit Rate** (gauge, %)
   - Thresholds: Red (0%), Yellow (20%), Green (50%+)

5. **Requests by Language** (pie chart)
   - Distribution across 18 languages

6. **Recent Queries** (table)
   - Last 20 queries with details

7. **Error Types** (bar chart)
   - 7-day error distribution

**Data sources:**
- PostgreSQL: request_logs table
- Prometheus: real-time metrics

## Alert Testing

### Test ServiceDown
```bash
# Stop API
docker-compose -f docker-compose.yml stop georgian-rag-api

# Wait 2 minutes
# Should receive: 🚨 ALERT FIRING in Telegram

# Restart API
docker-compose -f docker-compose.yml start georgian-rag-api

# Should receive: ✅ RESOLVED in Telegram
```

### Test HighErrorRate
```bash
# Generate errors
for i in {1..10}; do
  curl -X POST http://localhost:8000/query \
    -H "Content-Type: application/json" \
    -d '{"query": "test", "language": "zzz", "top_k": 999}'
  sleep 1
done

# Check Prometheus: http://localhost:9090/alerts
# Should see HighErrorRate pending → firing
```

## PostgreSQL Queries

### Request Statistics
```sql
-- Total requests
SELECT COUNT(*) FROM request_logs;

-- Average response time
SELECT AVG(duration_total) FROM request_logs;

-- Cache hit rate
SELECT 
  COUNT(*) FILTER (WHERE cache_hit = true) * 100.0 / COUNT(*) 
FROM request_logs;

-- Requests by language
SELECT language, COUNT(*) 
FROM request_logs 
GROUP BY language 
ORDER BY COUNT(*) DESC;

-- Recent errors
SELECT timestamp, query, error_message 
FROM request_logs 
WHERE status = 'error' 
ORDER BY timestamp DESC 
LIMIT 10;
```

### Cache Performance
```sql
-- Cache statistics
SELECT 
  COUNT(*) as total_requests,
  COUNT(*) FILTER (WHERE cache_hit = true) as cache_hits,
  ROUND(COUNT(*) FILTER (WHERE cache_hit = true)::numeric / COUNT(*)::numeric * 100, 2) as hit_rate_percent
FROM request_logs;
```

## Prometheus Queries

### Request Rate
```promql
# Requests per second
rate(rag_requests_total[5m])

# Success rate
sum(rate(rag_requests_total{status="success"}[5m])) 
/ 
sum(rate(rag_requests_total[5m]))
```

### Response Time
```promql
# Average response time
rate(rag_request_duration_seconds_sum[5m]) 
/ 
rate(rag_request_duration_seconds_count[5m])

# 95th percentile
histogram_quantile(0.95, rag_request_duration_seconds_bucket)
```

### Cache Performance
```promql
# Cache hit rate
rate(rag_cache_hits_total[5m]) 
/ 
(rate(rag_cache_hits_total[5m]) + rate(rag_cache_misses_total[5m]))
```

## Docker Volumes

**Persistent data:**

- `georgian_rag_postgres_data` - PostgreSQL database
- `georgian_rag_prometheus_data` - Metrics history
- `georgian_rag_grafana_data` - Dashboards and settings
- `georgian_rag_alertmanager_data` - Alert state

## Maintenance

### Backup PostgreSQL
```bash
docker exec georgian_rag_postgres pg_dump \
  -U raguser georgian_rag > backup_$(date +%Y%m%d).sql
```

### Restore PostgreSQL
```bash
cat backup_20260107.sql | docker exec -i georgian_rag_postgres \
  psql -U raguser georgian_rag
```

### Clean Old Data
```bash
# PostgreSQL: Delete old logs (> 30 days)
docker exec -it georgian_rag_postgres psql -U raguser -d georgian_rag -c \
  "DELETE FROM request_logs WHERE timestamp < NOW() - INTERVAL '30 days';"

# Prometheus: Adjust retention in prometheus.yml
# --storage.tsdb.retention.time=15d
```

## Troubleshooting

### Prometheus can't scrape FastAPI

**Check:**
1. FastAPI running: `curl http://localhost:8000/metrics`
2. Network: `docker network inspect georgian_rag_network`
3. Prometheus targets: http://localhost:9090/targets

### Telegram alerts not working

**Check:**
1. Bot token correct in `alertmanager.yml`
2. Chat ID correct
3. Alertmanager logs: `docker logs georgian_rag_alertmanager`
4. Test bot: `curl "https://api.telegram.org/bot{TOKEN}/sendMessage?chat_id={CHAT_ID}&text=Test"`

### Grafana can't connect to PostgreSQL

**Check:**
1. PostgreSQL running: `docker ps | grep postgres`
2. Data source config: Grafana → Configuration → Data Sources
3. Connection string: `postgres:5432` (Docker internal network)

## Production Recommendations

**Security:**
- Change default Grafana password
- Use secrets management (not plain text)
- Enable TLS/SSL
- Restrict network access

**Scaling:**
- Separate monitoring stack to dedicated server
- Use Prometheus federation for multiple instances
- Consider managed services (Grafana Cloud, Datadog)

**Alerting:**
- Add more receivers (Slack, email, PagerDuty)
- Tune alert thresholds based on traffic
- Set up on-call rotations

## Integration

**Used by:**
- `fastapi_dashboard.py` - Exports `/metrics` endpoint
- `utils/prometheus_exporter.py` - Metric definitions
- `utils/postgres_logger.py` - Database logging

## Notes

- Monitoring stack runs independently of FastAPI
- Can be deployed separately
- Metrics collected every 15 seconds
- Alerts evaluated every 15 seconds
- PostgreSQL logs every request
- Grafana auto-refresh: 5s intervals available
