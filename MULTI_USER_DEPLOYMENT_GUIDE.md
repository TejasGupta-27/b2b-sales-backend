# Multi-User Deployment Guide

This guide will help you deploy your B2B Sales Backend to handle multiple concurrent users effectively.

## 🚀 Quick Start

### 1. Production Deployment (Multi-User)

```bash
# Build and start with gunicorn (4 workers)
docker-compose up --build -d

# Check logs
docker-compose logs -f b2b-sales-backend

# Monitor performance
python scripts/monitor_performance.py --load-test 10
```

### 2. Development Deployment (Single Worker)

```bash
# Build and start with uvicorn (single worker, hot reload)
docker-compose -f docker-compose.dev.yml up --build -d

# Check logs
docker-compose -f docker-compose.dev.yml logs -f b2b-sales-backend
```

## 📊 Performance Improvements

### Before (Single Worker)
- ❌ 1 process handling all requests
- ❌ Limited to ~1 concurrent user effectively
- ❌ No process-level concurrency
- ❌ Database connection pool: 20 connections

### After (Multi-Worker)
- ✅ 4 worker processes handling requests
- ✅ Can handle 10+ concurrent users
- ✅ Full CPU utilization
- ✅ Dynamic database connection pool (based on CPU cores)
- ✅ Resource limits and monitoring

## 🔧 Configuration Details

### Gunicorn Configuration
```bash
gunicorn main:app \
  --bind 0.0.0.0:3001 \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --timeout 120 \
  --keep-alive 5 \
  --max-requests 1000 \
  --max-requests-jitter 100
```

**Parameters Explained:**
- `--workers 4`: 4 worker processes (recommended: CPU cores × 2)
- `--worker-class uvicorn.workers.UvicornWorker`: Use uvicorn worker for async support
- `--timeout 120`: 2-minute request timeout
- `--max-requests 1000`: Restart workers after 1000 requests (memory leak prevention)
- `--max-requests-jitter 100`: Add randomness to prevent all workers restarting simultaneously

### Database Connection Pool
```python
# Dynamic pool sizing based on CPU cores
cpu_count = multiprocessing.cpu_count()
optimal_pool_size = min(cpu_count * 2, 50)  # Cap at 50 connections
optimal_max_overflow = min(optimal_pool_size * 1.5, 75)  # Cap at 75 overflow
```

### Resource Limits
```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # 2 CPU cores max
      memory: 4G       # 4GB RAM max
    reservations:
      cpus: '1.0'      # 1 CPU core minimum
      memory: 2G       # 2GB RAM minimum
```

## 📈 Monitoring and Testing

### 1. Performance Monitoring
```bash
# Continuous monitoring
python scripts/monitor_performance.py

# Single performance check
python scripts/monitor_performance.py --single-check

# Load test with 10 users
python scripts/monitor_performance.py --load-test 10
```

### 2. Health Checks
```bash
# Application health
curl http://localhost:3001/health

# Performance stats
curl http://localhost:3001/api/admin/performance

# Database connection pool
curl http://localhost:3001/api/debug/database
```

### 3. Expected Performance Metrics

**Target Metrics:**
- ✅ Response Time: < 1 second (cached), < 3 seconds (uncached)
- ✅ Success Rate: > 95% under normal load
- ✅ Database Connections: < 80% of pool capacity
- ✅ Memory Usage: < 3GB under load
- ✅ CPU Usage: < 80% under load

## 🔍 Troubleshooting

### Common Issues

#### 1. High Memory Usage
```bash
# Check memory usage
docker stats

# Restart with more memory
docker-compose down
docker-compose up -d
```

#### 2. Database Connection Errors
```bash
# Check database pool
curl http://localhost:3001/api/debug/database

# Restart database
docker-compose restart postgres
```

#### 3. Slow Response Times
```bash
# Check performance stats
curl http://localhost:3001/api/admin/performance

# Check Elasticsearch
curl http://localhost:3001/api/debug/elasticsearch
```

### Performance Tuning

#### 1. Adjust Worker Count
```bash
# For more users (8 workers)
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:3001", "--workers", "8", "--worker-class", "uvicorn.workers.UvicornWorker"]

# For fewer users (2 workers)
CMD ["gunicorn", "main:app", "--bind", "0.0.0.0:3001", "--workers", "2", "--worker-class", "uvicorn.workers.UvicornWorker"]
```

#### 2. Increase Resource Limits
```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'      # 4 CPU cores
      memory: 8G       # 8GB RAM
```

#### 3. Database Optimization
```sql
-- Increase PostgreSQL connections
ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '512MB';
ALTER SYSTEM SET effective_cache_size = '2GB';
```

## 🚀 Production Deployment Checklist

### Before Deployment
- [ ] Set `DEBUG=false` in environment
- [ ] Configure proper CORS origins
- [ ] Set up monitoring and logging
- [ ] Test with load testing script
- [ ] Verify database connection pool settings

### After Deployment
- [ ] Monitor application health
- [ ] Check resource usage
- [ ] Verify all endpoints work
- [ ] Test with multiple concurrent users
- [ ] Set up alerts for performance issues

## 📊 Load Testing Results

### Test Scenarios

#### 5 Concurrent Users
- Expected Response Time: < 2 seconds
- Expected Success Rate: > 98%
- Expected Memory Usage: < 2GB

#### 10 Concurrent Users
- Expected Response Time: < 3 seconds
- Expected Success Rate: > 95%
- Expected Memory Usage: < 3GB

#### 20 Concurrent Users
- Expected Response Time: < 5 seconds
- Expected Success Rate: > 90%
- Expected Memory Usage: < 4GB

## 🔧 Advanced Configuration

### Custom Gunicorn Configuration
Create `gunicorn.conf.py`:
```python
# Gunicorn configuration file
bind = "0.0.0.0:3001"
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 100
preload_app = True
```

### Environment-Specific Settings
```bash
# Development
export WORKERS=1
export DEBUG=true
export DB_ECHO_SQL=true

# Production
export WORKERS=4
export DEBUG=false
export DB_ECHO_SQL=false
```

## 📈 Scaling Recommendations

### For 50+ Users
1. Increase workers to 8-12
2. Add load balancer (nginx)
3. Use multiple application instances
4. Implement Redis for session storage
5. Consider database read replicas

### For 100+ Users
1. Deploy to multiple servers
2. Use container orchestration (Kubernetes)
3. Implement horizontal scaling
4. Add CDN for static assets
5. Use managed database service

## 🆘 Support

If you encounter issues:

1. Check the logs: `docker-compose logs -f b2b-sales-backend`
2. Monitor performance: `python scripts/monitor_performance.py`
3. Verify health: `curl http://localhost:3001/health`
4. Check resource usage: `docker stats`

For persistent issues, consider:
- Increasing resource limits
- Reducing worker count
- Optimizing database queries
- Adding caching layers 