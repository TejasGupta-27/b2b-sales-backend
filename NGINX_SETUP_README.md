# Nginx Reverse Proxy Setup for B2B Sales Backend

This guide helps you set up nginx as a reverse proxy for your B2B Sales Backend and Elasticsearch services on Azure VM.

## Overview

The nginx reverse proxy will:
- Route API requests to your backend service (port 3001)
- Route Elasticsearch requests to your Elasticsearch service (port 9200)
- Provide a single entry point for all services
- Handle SSL termination (if configured)

## Quick Setup

### 1. Prepare Configuration

First, update the `nginx.conf` file with your Azure VM's domain or IP address:

```bash
# Edit nginx.conf
nano nginx.conf

# Replace this line:
server_name your-azure-vm-domain.com;  # Replace with your actual domain or IP

# With your actual domain or IP, for example:
server_name 20.123.45.67;  # Your Azure VM public IP
# OR
server_name myapp.azurewebsites.net;  # Your Azure domain
```

### 2. Run the Setup Script

Make the setup script executable and run it:

```bash
# Make the script executable
chmod +x setup-nginx-proxy.sh

# Run the installation
./setup-nginx-proxy.sh install
```

### 3. Configure Azure VM Network Security Group

Ensure your Azure VM's Network Security Group allows:
- **Port 80** (HTTP) - for nginx reverse proxy
- **Port 443** (HTTPS) - if using SSL
- **Port 22** (SSH) - for remote access

## Manual Setup (Alternative)

If you prefer manual setup:

### 1. Install nginx

```bash
sudo apt update
sudo apt install -y nginx
```

### 2. Configure nginx

```bash
# Test the configuration
nginx -t -c $(pwd)/nginx.conf

# Setup systemd service
sudo cp b2b-nginx.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable b2b-nginx.service
```

### 3. Start services

```bash
# Start Docker Compose services
docker compose up -d

# Start nginx
sudo systemctl start b2b-nginx.service
```

## Service Management

Use the setup script for easy service management:

```bash
# Start all services
./setup-nginx-proxy.sh start

# Stop all services
./setup-nginx-proxy.sh stop

# Restart services
./setup-nginx-proxy.sh restart

# Check service status
./setup-nginx-proxy.sh status

# View nginx logs
./setup-nginx-proxy.sh logs
```

## Access URLs

After setup, your services will be available at:

- **Backend API**: `http://your-azure-vm-ip/api/`
- **Health Check**: `http://your-azure-vm-ip/health`
- **Elasticsearch**: `http://your-azure-vm-ip/elasticsearch/`

## SSL/HTTPS Configuration

To enable HTTPS:

1. Obtain SSL certificates (e.g., from Let's Encrypt)
2. Edit `nginx.conf` and uncomment the HTTPS server block
3. Update certificate paths in the configuration
4. Restart nginx

### Using Let's Encrypt (Recommended)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal (add to crontab)
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Troubleshooting

### Check Service Status

```bash
# Check Docker services
docker compose ps

# Check nginx service
sudo systemctl status b2b-nginx.service

# Check nginx configuration
nginx -t -c $(pwd)/nginx.conf
```

### View Logs

```bash
# Nginx logs
sudo journalctl -u b2b-nginx.service -f

# Docker logs
docker compose logs -f

# Backend service logs
docker compose logs -f b2b-sales-backend

# Elasticsearch logs
docker compose logs -f elasticsearch
```

### Common Issues

1. **Port 80 already in use**
   ```bash
   # Stop default nginx
   sudo systemctl stop nginx
   
   # Check what's using port 80
   sudo netstat -tlnp | grep :80
   ```

2. **Backend not responding**
   ```bash
   # Check if backend is running
   curl http://localhost:3001/health
   
   # Check Docker services
   docker compose ps
   ```

3. **Elasticsearch not responding**
   ```bash
   # Check elasticsearch
   curl http://localhost:9200/_cluster/health
   
   # Check elasticsearch logs
   docker compose logs elasticsearch
   ```

## Configuration Files

- `nginx.conf` - Main nginx configuration
- `b2b-nginx.service` - Systemd service file
- `setup-nginx-proxy.sh` - Setup and management script

## Security Considerations

1. **Firewall**: Configure Azure NSG to only allow necessary ports
2. **SSL**: Always use HTTPS in production
3. **Access Control**: Consider adding basic auth for elasticsearch endpoint
4. **Rate Limiting**: Add rate limiting to prevent abuse
5. **Log Monitoring**: Monitor nginx logs for suspicious activity

## Performance Tuning

For high-traffic scenarios, consider:

1. **Worker Processes**: Adjust `worker_processes` in nginx.conf
2. **Connection Limits**: Increase `worker_connections`
3. **Caching**: Add response caching for static content
4. **Compression**: Enable gzip compression
5. **Keep-Alive**: Optimize keep-alive settings

## Monitoring

Set up monitoring for:
- Service health checks
- Response times
- Error rates
- Resource usage

You can use tools like:
- Prometheus + Grafana
- Azure Monitor
- Custom health check scripts

## Support

If you encounter issues:
1. Check the troubleshooting section
2. Review service logs
3. Verify network connectivity
4. Check Azure VM configuration 