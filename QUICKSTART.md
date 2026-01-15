# Quick Start Guide

Get Georgian RAG running in 5 minutes!

## Prerequisites

- Docker & Docker Compose installed
- API keys ready (Anthropic, Qdrant, Groq)
- 8GB RAM minimum
- 10GB disk space

## 1. Clone & Setup
````bash
# Clone repository
git clone https://github.com/yourusername/georgian-rag.git
cd georgian-rag

# Copy environment template
cp .env.example .env
````

## 2. Configure Environment

Edit `.env` file with your API keys:
````bash
# Required
QDRANT_URL=https://your-cluster.cloud.qdrant.io:6333
QDRANT_API_KEY=your_key
ANTHROPIC_API_KEY=sk-ant-your_key
GROQ_API_KEY=gsk_your_key

# Optional but recommended
UPSTASH_REDIS_URL=https://your-redis.upstash.io
UPSTASH_REDIS_TOKEN=your_token
````

## 3. Start Services
````bash
# Start all services
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f georgian-rag-api
````

## 4. Test API
````bash
# Health check
curl http://localhost:8000/health

# Test query
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the best places in Tbilisi?",
    "target_language": "en",
    "top_k": 5
  }'
````

## 5. Access Services

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090
- **Alertmanager**: http://localhost:9093

## Daily Commands

### Start/Stop
````bash
# Start
docker-compose up -d

# Stop
docker-compose down

# Restart
docker-compose restart georgian-rag-api
````

### Logs
````bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f georgian-rag-api

# Last 100 lines
docker-compose logs --tail 100 georgian-rag-api
````

### Status
````bash
# Service status
docker-compose ps

# Resource usage
docker stats
````

## Testing

### Query Examples

**English:**
````bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Best museums in Georgia", "target_language": "en"}'
````

**Russian:**
````bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Что посмотреть в Батуми?", "target_language": "ru"}'
````

**German:**
````bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Sehenswürdigkeiten in Tiflis", "target_language": "de"}'
````

## Monitoring

### Grafana Dashboard

1. Open http://localhost:3000
2. Login: admin/admin
3. Dashboard: "geo_rag_v1"

**Metrics shown:**
- Total requests
- Average response time
- Success rate
- Cache hit rate
- Requests by language
- Recent queries
- Error distribution

### Prometheus Metrics

Open http://localhost:9090 to query metrics:
````promql
# Request rate
rate(rag_requests_total[5m])

# Average response time
rate(rag_request_duration_seconds_sum[5m]) / rate(rag_request_duration_seconds_count[5m])

# Cache hit rate
rate(rag_cache_hits_total[5m]) / (rate(rag_cache_hits_total[5m]) + rate(rag_cache_misses_total[5m]))
````

## Maintenance

### Update System
````bash
# Pull latest changes
git pull

# Rebuild images
docker-compose build

# Restart services
docker-compose up -d
````

### Backup Data
````bash
# PostgreSQL backup
docker exec georgian_rag_postgres pg_dump -U raguser georgian_rag > backup_$(date +%Y%m%d).sql

# Restore
cat backup_20260110.sql | docker exec -i georgian_rag_postgres psql -U raguser georgian_rag
````

### Clear Caches
````bash
# Clear Redis cache
curl -X POST http://localhost:8000/cache/clear

# Restart API (clears in-memory cache)
docker-compose restart georgian-rag-api
````

### Clean Docker
````bash
# Remove stopped containers
docker-compose down

# Remove volumes (WARNING: deletes all data!)
docker-compose down -v

# Clean system
docker system prune -a
````

## Troubleshooting

### API Not Starting
````bash
# Check logs
docker-compose logs georgian-rag-api

# Common issues:
# - Missing .env file → Copy .env.example to .env
# - Invalid API keys → Check keys in .env
# - Port already in use → Change API_PORT in .env
````

### Slow Responses
````bash
# Check if cache is working
curl http://localhost:8000/cache/stats

# Warm up cache
# Run common queries multiple times

# Check resource usage
docker stats
````

### Telegram Alerts Not Working
````bash
# Test bot token
curl "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/getMe"

# Check Alertmanager logs
docker-compose logs alertmanager

# Verify config
cat monitoring/alertmanager.yml
````

## Performance Tips

1. **Enable Redis caching** - Set UPSTASH_REDIS_URL in .env
2. **Warm up cache** - Run popular queries after startup
3. **Monitor metrics** - Use Grafana dashboard
4. **Adjust resources** - Increase Docker memory limit if needed
5. **Use SSD** - Better I/O for vector search

## Security Best Practices

1. **Change default passwords** - Grafana, PostgreSQL
2. **Use secrets management** - Don't commit .env to Git
3. **Enable firewall** - Restrict ports 3000, 9090, 9093 to internal network
4. **Regular updates** - Pull latest images monthly
5. **Monitor alerts** - Set up Telegram notifications

## Getting Help

- **Documentation**: See README.md and DEPLOYMENT.md
- **Issues**: https://github.com/yourusername/georgian-rag/issues
- **Logs**: Check docker-compose logs
- **Health**: http://localhost:8000/health

## Next Steps

1. **Customize**: Adjust settings in .env
2. **Scale**: See DEPLOYMENT.md for production setup
3. **Monitor**: Set up Telegram alerts
4. **Optimize**: Tune cache settings and model parameters

Happy querying! 