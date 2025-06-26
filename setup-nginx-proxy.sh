#!/bin/bash

# B2B Sales Backend - Nginx Reverse Proxy Setup Script
# This script sets up nginx as a reverse proxy for the backend and elasticsearch services

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_error "This script should not be run as root for security reasons."
        print_status "Please run as a regular user with sudo privileges."
        exit 1
    fi
}

# Install nginx if not present
install_nginx() {
    if ! command -v nginx &> /dev/null; then
        print_status "Installing nginx..."
        sudo apt update
        sudo apt install -y nginx
        print_status "Nginx installed successfully"
    else
        print_status "Nginx is already installed"
    fi
}

# Setup nginx configuration
setup_nginx_config() {
    print_status "Setting up nginx configuration..."
    
    # Stop default nginx if running
    sudo systemctl stop nginx 2>/dev/null || true
    
    # Create nginx directories with proper permissions
    print_status "Creating nginx directories..."
    sudo mkdir -p /var/log/nginx
    sudo chown www-data:www-data /var/log/nginx
    sudo chmod 755 /var/log/nginx
    
    # Backup original nginx config
    if [ -f /etc/nginx/nginx.conf ]; then
        sudo cp /etc/nginx/nginx.conf /etc/nginx/nginx.conf.backup.$(date +%Y%m%d_%H%M%S)
        print_status "Backed up original nginx configuration"
    fi
    
    # Test our custom configuration with sudo
    if sudo nginx -t -c $(pwd)/nginx.conf; then
        print_status "Nginx configuration test passed"
    else
        print_error "Nginx configuration test failed"
        exit 1
    fi
}

# Setup systemd service
setup_systemd_service() {
    print_status "Setting up systemd service..."
    
    # Copy service file to systemd directory
    sudo cp b2b-nginx.service /etc/systemd/system/
    
    # Reload systemd daemon
    sudo systemctl daemon-reload
    
    # Enable the service
    sudo systemctl enable b2b-nginx.service
    
    print_status "Systemd service configured"
}

# Start services
start_services() {
    print_status "Starting services..."
    
    # Start docker compose services first
    print_status "Starting Docker Compose services..."
    docker compose up -d
    
    # Wait for services to be ready
    print_status "Waiting for backend service to be ready..."
    timeout=60
    counter=0
    while [ $counter -lt $timeout ]; do
        if curl -s http://localhost:3001/health > /dev/null 2>&1; then
            print_status "Backend service is ready"
            break
        fi
        sleep 2
        counter=$((counter + 2))
    done
    
    if [ $counter -ge $timeout ]; then
        print_warning "Backend service health check timed out, but proceeding..."
    fi
    
    # Check elasticsearch
    print_status "Checking Elasticsearch service..."
    timeout=60
    counter=0
    while [ $counter -lt $timeout ]; do
        if curl -s http://localhost:9200/_cluster/health > /dev/null 2>&1; then
            print_status "Elasticsearch service is ready"
            break
        fi
        sleep 2
        counter=$((counter + 2))
    done
    
    if [ $counter -ge $timeout ]; then
        print_warning "Elasticsearch service health check timed out, but proceeding..."
    fi
    
    # Start nginx service
    print_status "Starting nginx reverse proxy..."
    sudo systemctl start b2b-nginx.service
    
    # Check if nginx is running
    if sudo systemctl is-active --quiet b2b-nginx.service; then
        print_status "Nginx reverse proxy started successfully"
    else
        print_error "Failed to start nginx reverse proxy"
        sudo systemctl status b2b-nginx.service
        exit 1
    fi
}

# Display service status
show_status() {
    print_status "Service Status:"
    echo "===================="
    
    echo -n "Docker Compose Services: "
    if docker compose ps | grep -q "Up"; then
        echo -e "${GREEN}Running${NC}"
    else
        echo -e "${RED}Not Running${NC}"
    fi
    
    echo -n "Nginx Reverse Proxy: "
    if sudo systemctl is-active --quiet b2b-nginx.service; then
        echo -e "${GREEN}Running${NC}"
    else
        echo -e "${RED}Not Running${NC}"
    fi
    
    echo ""
    print_status "Access URLs:"
    echo "Backend API: http://48.210.58.7/api/"
    echo "Health Check: http://48.210.58.7/health"
    echo "Elasticsearch: http://48.210.58.7/elasticsearch/"
    echo ""
    print_status "Your services are now accessible from the internet!"
}

# Main function
main() {
    print_status "B2B Sales Backend - Nginx Reverse Proxy Setup"
    print_status "=============================================="
    
    check_root
    install_nginx
    setup_nginx_config
    setup_systemd_service
    start_services
    show_status
    
    print_status "Setup completed successfully!"
    print_status "You can manage the services using the following commands:"
    echo "  - Start all services: sudo systemctl start b2b-nginx.service && docker compose up -d"
    echo "  - Stop all services: sudo systemctl stop b2b-nginx.service && docker compose down"
    echo "  - Restart nginx: sudo systemctl restart b2b-nginx.service"
    echo "  - View nginx logs: sudo journalctl -u b2b-nginx.service -f"
    echo "  - View nginx status: sudo systemctl status b2b-nginx.service"
}

# Handle script arguments
case "${1:-}" in
    "install")
        main
        ;;
    "start")
        print_status "Starting services..."
        docker compose up -d
        sudo systemctl start b2b-nginx.service
        show_status
        ;;
    "stop")
        print_status "Stopping services..."
        sudo systemctl stop b2b-nginx.service
        docker compose down
        print_status "Services stopped"
        ;;
    "restart")
        print_status "Restarting services..."
        sudo systemctl restart b2b-nginx.service
        docker compose restart
        show_status
        ;;
    "status")
        show_status
        ;;
    "logs")
        print_status "Showing nginx logs (press Ctrl+C to exit)..."
        sudo journalctl -u b2b-nginx.service -f
        ;;
    *)
        echo "Usage: $0 {install|start|stop|restart|status|logs}"
        echo ""
        echo "Commands:"
        echo "  install  - Install and configure nginx reverse proxy"
        echo "  start    - Start all services"
        echo "  stop     - Stop all services"
        echo "  restart  - Restart all services"
        echo "  status   - Show service status"
        echo "  logs     - Show nginx logs"
        exit 1
        ;;
esac 