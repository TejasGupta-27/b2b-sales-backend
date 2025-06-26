# B2B Sales Backend - Integrated Grafana Admin Interface

## 🚀 Quick Start

The B2B Sales Backend now includes **integrated Grafana monitoring and admin interface** that starts automatically with the application.

### Start the Application
```bash
docker-compose up -d
```

That's it! All services including Grafana admin interface start automatically.

## 📱 Access URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| **Main Application** | http://localhost:3001 | - |
| **Grafana Admin Interface** | http://localhost:3000 | admin/admin123 |
| **Prometheus** | http://localhost:9090 | - |
| **Kibana** | http://localhost:5601 | - |
| **Adminer (DB)** | http://localhost:8080 | - |

## 🎛️ Grafana Admin Interface Features

### **Performance Monitoring**
- Real-time request rate tracking
- Response time monitoring (95th percentile)
- Success rate metrics
- Active leads count
- Application memory and CPU usage
- AI token usage tracking

### **Admin Management**
- **Prompt Management** - View and manage all AI prompts
- **Configuration Management** - System and conversational settings
- **Live Log Viewing** - Real-time log monitoring with filtering
- **Data Source Status** - Elasticsearch, ChromaDB, and file system health
- **System Metrics** - Database stats, file counts, performance data

### **Available Dashboards**
1. **B2B Sales Backend Dashboard** - Performance metrics and monitoring
2. **B2B Sales Backend - Admin Dashboard** - Complete admin interface

## 🔧 Service Startup Order

The application uses health checks to ensure proper startup order:

1. **PostgreSQL** → Database ready
2. **Elasticsearch** → Search engine ready  
3. **B2B Sales Backend** → Main application ready
4. **Prometheus** → Metrics collection ready
5. **Grafana** → Admin interface ready
6. **Kibana** → Elasticsearch management ready
7. **Adminer** → Database management ready

## 📊 Monitoring Setup

### **Automatic Configuration**
- Grafana automatically loads both dashboards
- Prometheus scrapes metrics every 10 seconds
- All data is persisted in Docker volumes
- Health checks ensure services start in correct order

### **Data Sources**
- **Prometheus** - Performance metrics and system data
- **B2B Sales Backend** - Custom admin data (prompts, logs, config)

## 🔐 Default Credentials

- **Grafana**: admin/admin123
- **PostgreSQL**: postgres/postgres
- **Elasticsearch**: No authentication (development mode)

## 💡 Usage Tips

### **Admin Dashboard Navigation**
1. Login to Grafana at http://localhost:3000
2. Navigate to "B2B Sales Backend - Admin Dashboard"
3. Use the table panels to view:
   - **Prompt Management** - All AI prompts by category
   - **Recent Logs** - Live application logs
   - **Data Source Status** - System health
   - **System Metrics** - Performance data

### **Performance Dashboard**
- Monitor real-time application performance
- Track request rates and response times
- View system resource usage
- Monitor AI token consumption

## 🔧 Management Commands

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop all services
docker-compose down

# Restart specific service
docker-compose restart grafana

# Update and rebuild
docker-compose up -d --build
```

## 🚨 Troubleshooting

### **Grafana Not Loading**
- Check if all services are healthy: `docker-compose ps`
- View Grafana logs: `docker-compose logs grafana`
- Ensure Prometheus is running before Grafana

### **No Data in Dashboards**
- Verify Prometheus can reach the application: http://localhost:3001/metrics
- Check Prometheus targets: http://localhost:9090/targets
- Ensure the B2B Sales Backend is healthy

### **Admin Data Not Showing**
- Check if the JSON data source is configured in Grafana
- Verify the application endpoints are responding: http://localhost:3001/api/admin/grafana/prompts
- Check application logs for errors

## 📈 What's Monitored

### **Application Metrics**
- Request count and rate
- Response times
- Error rates
- Active leads
- Database connections

### **System Metrics**
- Memory usage
- CPU usage
- File system stats
- Process information

### **Business Metrics**
- AI token usage
- Elasticsearch data counts
- Database statistics
- Log activity

## 🔄 Integration Benefits

✅ **No Separate Scripts** - Everything starts with `docker-compose up -d`  
✅ **Automatic Health Checks** - Services start in correct order  
✅ **Persistent Data** - All configurations and metrics preserved  
✅ **Professional Interface** - Grafana provides enterprise-grade monitoring  
✅ **Real-time Updates** - All data updates automatically  
✅ **Integrated Admin** - No need for separate HTML admin portal  

The HTML admin portal at `/api/admin/` now shows a redirect message pointing users to the Grafana interface, effectively replacing the old admin system with a more powerful monitoring-based solution. 