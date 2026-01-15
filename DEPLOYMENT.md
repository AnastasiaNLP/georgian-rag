#  Georgian RAG System - Deployment Guide

Complete deployment guide for production environments.

---

##  Table of Contents

- [Prerequisites](#prerequisites)
- [Environment Setup](#environment-setup)
- [Docker Deployment](#docker-deployment)
- [Monitoring Setup](#monitoring-setup)
- [Production Checklist](#production-checklist)
- [Troubleshooting](#troubleshooting)
- [Scaling](#scaling)
- [Security](#security)
- [Backup & Recovery](#backup--recovery)

---

##  Prerequisites

### Required Services

**1. Qdrant Cloud Account**
- Sign up: https://cloud.qdrant.io
- Create cluster
- Note: URL and API key

**2. Anthropic API Key**
- Sign up: https://console.anthropic.com
- Get API key
- Note: Check rate limits

**3. Server Requirements**

**Minimum:**
- 4 GB RAM
- 20 GB disk space
- Ubuntu 20.04+ / Debian 11+

**Recommended:**
- 4 CPU cores
- 50 GB SSD
- Ubuntu 22.04 LTS

**4. Optional Services**
- Google Cloud Translation API (recommended)
- Groq API (LLM fallback)
- Telegram Bot (alerts)

---

##  Environment Setup

### 1. Install Docker

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify installation
docker --version
```

### 2. Install Docker Compose

```bash
# Install Docker Compose
sudo apt install docker-compose-plugin -y

# Verify
docker compose version
```

### 3. Clone Repository

```bash
# Clone
git clone https://github.com/AnastasiaNLP/georgian-rag.git
cd georgian-rag

# Check structure
ls -la
```

### 4. Configure Environment

```bash
# Copy template
cp .env.example .env

# Edit with your keys
nano .env
```

**Required Variables:**
```bash
# LLM
ANTHROPIC_API_KEY=sk-ant-your-key-here

# Vector Database
QDRANT_URL=https://your-cluster.qdrant.io:6333
QDRANT_API_KEY=your-qdrant-key
COLLECTION_NAME=georgian_attractions

# API Configuration
API_PORT=8000
API_HOST=0.0.0.0
```

**Optional Variables:**
```bash
# Translation
GOOGLE_APPLICATION_CREDENTIALS=/path/to/credentials.json
GOOGLE_CLOUD_PROJECT=your-project-id

# Groq Fallback
GROQ_API_KEY=gsk_your-groq-key

# Database
POSTGRES_USER=raguser
POSTGRES_PASSWORD=your-secure-password
POSTGRES_DB=ragdb

# Telegram Alerts
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_ID=your-chat-id
```

---

##  Docker Deployment

### Option 1: Docker Compose (Recommended)

**Full stack with monitoring:**

```bash
# Build and start all services
docker-compose up -d

# Check logs
docker-compose logs -f georgian-rag-api

# Check status
docker-compose ps
```

**Services started:**
- `georgian-rag-api` (Port 8000)
- `postgres` (Port 5432)
- `prometheus` (Port 9090)
- `grafana` (Port 3000)
- `alertmanager` (Port 9093)

### Option 2: API Only (Lightweight)

```bash
# Build image
docker build -t georgian-rag:latest .

# Run container
docker run -d \
  --name georgian-rag \
  -p 8000:8000 \
  --env-file .env \
  --restart unless-stopped \
  georgian-rag:latest

# Check logs
docker logs -f georgian-rag
```

### Verify Deployment

```bash
# Health check
curl http://localhost:8000/health

# Expected response:
# {
#   "status": "healthy",
#   "components": {
#     "rag_pipeline": true,
#     "qdrant": true
#   }
# }

# Test query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Best places in Tbilisi",
    "language": "en",
    "top_k": 3
  }'
```

---

##  Monitoring Setup

### 1. Access Grafana

```bash
# Open in browser
http://your-server-ip:3000

# Login:
# Username: admin
# Password: admin

# Change password on first login
```

### 2. Import Dashboard

**Option A: Pre-configured (if available)**
```
1. Go to Dashboards → Import
2. Upload: monitoring/grafana/dashboards/main.json
3. Select Prometheus datasource
4. Click Import
```

**Option B: Manual setup**
```
1. Add Prometheus datasource:
   - URL: http://prometheus:9090
   - Access: Server
   - Click "Save & Test"

2. Create panels:
   - Query Performance
   - Cache Statistics
   - Language Distribution
   - Recent Queries
```

### 3. Configure Telegram Alerts (Optional)

**Create Telegram Bot:**
```bash
1. Message @BotFather on Telegram
2. Send: /newbot
3. Follow instructions
4. Copy token

5. Get your chat ID:
   - Message your bot
   - Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   - Copy "chat":{"id": YOUR_CHAT_ID}
```

**Update .env:**
```bash
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_CHAT_ID=123456789
```

**Restart Alertmanager:**
```bash
docker-compose restart alertmanager
```

### 4. Test Alerts

```bash
# Stop service to trigger alert
docker-compose stop georgian-rag-api

# Wait 3-5 minutes
# You should receive Telegram notification

# Start service
docker-compose start georgian-rag-api

# You should receive recovery notification
```

---

##  Production Checklist

### Before Going Live

- [ ] **Environment Variables**
  - [ ] All required keys added to `.env`
  - [ ] `.env` added to `.gitignore`
  - [ ] Secure passwords set
  
- [ ] **Security**
  - [ ] Firewall configured (ports 8000, 3000, 9090)
  - [ ] HTTPS/SSL certificate (if public)
  - [ ] API rate limiting enabled
  - [ ] Database credentials secure
  
- [ ] **Monitoring**
  - [ ] Grafana accessible
  - [ ] Prometheus collecting metrics
  - [ ] Alerts configured
  - [ ] Telegram notifications working
  
- [ ] **Testing**
  - [ ] Health endpoint responding
  - [ ] Test queries in all languages
  - [ ] Cache warming completed
  - [ ] Load testing passed
  
- [ ] **Backup**
  - [ ] PostgreSQL backup configured
  - [ ] `.env` backed up securely
  - [ ] Docker volumes backed up
  
- [ ] **Documentation**
  - [ ] Team access documented
  - [ ] Runbooks created
  - [ ] Contact info updated

---

##  Troubleshooting

### Issue: Service won't start

**Check logs:**
```bash
docker-compose logs georgian-rag-api
```

**Common causes:**
- Missing API keys in `.env`
- Port 8000 already in use
- Insufficient memory

**Solutions:**
```bash
# Check .env file
cat .env | grep API_KEY

# Check port
sudo lsof -i :8000

# Check memory
free -h

# Restart with fresh build
docker-compose down
docker-compose up -d --build
```

### Issue: Qdrant connection failed

**Check:**
```bash
# Test Qdrant connection
curl -X GET "$QDRANT_URL/collections" \
  -H "api-key: $QDRANT_API_KEY"
```

**Solutions:**
- Verify QDRANT_URL format: `https://xxx.qdrant.io:6333`
- Check API key is correct
- Ensure Qdrant cluster is active

### Issue: Slow responses (>30s)

**Check:**
```bash
# Check system resources
docker stats

# Check model cache
docker exec georgian-rag-api ls -lh /home/raguser/.cache/

# Check logs for errors
docker-compose logs --tail=100 georgian-rag-api
```

**Solutions:**
- First request downloads model (~500MB) - takes 5-10 min
- Subsequent requests should be 10-15s
- If still slow, check CPU/RAM allocation

### Issue: Cache not working

**Check:**
```bash
# Check metrics
curl http://localhost:8000/metrics | grep cache

# Expected: cache_hit_total increasing
```

**Solutions:**
```bash
# Restart service
docker-compose restart georgian-rag-api

# Clear cache
docker-compose exec georgian-rag-api rm -rf /tmp/cache/*
```

### Issue: Grafana not showing data

**Check Prometheus:**
```bash
# Open Prometheus
http://localhost:9090

# Check targets: Status → Targets
# georgian_rag_api should be UP
```

**Solutions:**
- Restart Prometheus: `docker-compose restart prometheus`
- Check network: `docker network ls`
- Verify datasource in Grafana

---

##  Scaling

### Horizontal Scaling (Multiple Instances)

**1. Update docker-compose.yml:**
```yaml
services:
  georgian-rag-api:
    deploy:
      replicas: 3
    ports:
      - "8000-8002:8000"
```

**2. Add Load Balancer:**
```yaml
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - georgian-rag-api
```

**3. nginx.conf:**
```nginx
upstream georgian_rag {
    server georgian-rag-api-1:8000;
    server georgian-rag-api-2:8000;
    server georgian-rag-api-3:8000;
}

server {
    listen 80;
    location / {
        proxy_pass http://georgian_rag;
    }
}
```

### Vertical Scaling (More Resources)

**Increase container resources:**
```yaml
services:
  georgian-rag-api:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
```

### Caching Optimization

**Add Redis for distributed caching:**
```yaml
services:
  redis:
    image: redis:alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
```

**Update .env:**
```bash
REDIS_URL=redis://redis:6379
```

---

## Security

### 1. Firewall Configuration

```bash
# Allow only necessary ports
sudo ufw allow 22/tcp    # SSH
sudo ufw allow 80/tcp    # HTTP
sudo ufw allow 443/tcp   # HTTPS
sudo ufw allow 8000/tcp  # API (if needed externally)

# Enable firewall
sudo ufw enable
```

### 2. HTTPS/SSL (Production)

**Using Let's Encrypt:**
```bash
# Install Certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo certbot renew --dry-run
```

**Update nginx:**
```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    
    location / {
        proxy_pass http://georgian-rag-api:8000;
    }
}
```

### 3. API Rate Limiting

**In nginx:**
```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

location /query {
    limit_req zone=api_limit burst=20;
    proxy_pass http://georgian-rag-api:8000;
}
```

### 4. Environment Security

```bash
# Secure .env file
chmod 600 .env

# Never commit .env to git
echo ".env" >> .gitignore

# Use secrets management (production)
# - AWS Secrets Manager
# - HashiCorp Vault
# - Azure Key Vault
```

---

##  Backup & Recovery

### 1. PostgreSQL Backup

**Automated daily backups:**
```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose exec -T postgres pg_dump -U raguser ragdb > backup_$DATE.sql
# Keep last 7 days
find . -name "backup_*.sql" -mtime +7 -delete
EOF

chmod +x backup.sh

# Add to crontab (daily at 2 AM)
crontab -e
# Add: 0 2 * * * /path/to/georgian-rag/backup.sh
```

### 2. Volume Backup

```bash
# Backup all Docker volumes
docker run --rm \
  -v georgian_rag_postgres_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/volumes_backup.tar.gz /data
```

### 3. Restore from Backup

```bash
# PostgreSQL restore
cat backup_20260114.sql | docker-compose exec -T postgres psql -U raguser ragdb

# Volume restore
docker run --rm \
  -v georgian_rag_postgres_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/volumes_backup.tar.gz -C /
```

---

##  Support & Maintenance

### Regular Maintenance Tasks

**Weekly:**
- [ ] Check disk space: `df -h`
- [ ] Review error logs
- [ ] Check Grafana dashboards
- [ ] Verify backups

**Monthly:**
- [ ] Update dependencies: `docker-compose pull`
- [ ] Security updates: `sudo apt update && sudo apt upgrade`
- [ ] Review and optimize cache settings
- [ ] Analyze query patterns

**Quarterly:**
- [ ] Review and update monitoring alerts
- [ ] Performance testing
- [ ] Security audit
- [ ] Documentation updates

### Getting Help

- **GitHub Issues**: https://github.com/AnastasiaNLP/georgian-rag/issues
- **Telegram**: [@nastassia_timoh](https://t.me/nastassia_timoh)
- **Email**: Via LinkedIn

---

##  Additional Resources

- [Quick Start Guide](QUICKSTART.md)
- [Setup Guide](SETUP_GUIDE.md)
- [API Documentation](http://localhost:8000/docs)
- [Grafana Dashboards](http://localhost:3000)

---

<div align="center">

**Georgian RAG System** - Production Deployment Guide

Made with ❤️ by Anastasia Timoshevskaya

[⬆ Back to README](README.md)

</div>