# B2B Sales AI Assistant - Multi-User Setup Guide

## 🎯 **Overview**

Your B2B Sales AI Assistant now supports **multiple users** with:

- **User Authentication** (JWT tokens)
- **Organization-based Multi-tenancy** 
- **Role-based Access Control**
- **Data Isolation** between organizations
- **Rate Limiting** per user
- **API Usage Tracking**

## 🏗️ **Architecture Overview**

```
User Authentication → Organization Isolation → Data Access Control
     ↓                      ↓                        ↓
JWT Tokens              Multi-tenancy            Role-based permissions
Rate limiting           Data separation          Lead/conversation isolation
```

### **User Roles**
- **Admin**: Full system access, can manage users and organizations
- **Sales Manager**: Can view all leads within organization
- **Sales Agent**: Can manage assigned leads
- **Viewer**: Read-only access to organization data

### **Organization Isolation**
- Each user belongs to an organization
- Users can only access data within their organization
- Leads, conversations, and quotes are organization-scoped

## 🚀 **Quick Start**

### **1. Install Dependencies**

```bash
# Install authentication dependencies
pip install python-jose[cryptography] passlib[bcrypt] bcrypt
```

### **2. Run Initial Setup**

```bash
# Run the setup script to create initial admin user and organization
python scripts/setup_initial_data.py
```

This creates:
- Default organization
- Admin user (`admin@example.com` / `admin123`)
- Demo users for testing

### **3. Start the Application**

```bash
python main.py
```

### **4. Test Authentication**

```bash
# Login as admin
curl -X POST "http://localhost:3001/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@example.com", "password": "admin123"}'
```

## 🔐 **Authentication Endpoints**

### **User Registration**
```bash
POST /api/auth/register
{
  "email": "user@company.com",
  "password": "secure_password",
  "first_name": "John",
  "last_name": "Doe",
  "organization_id": "org-uuid",
  "role": "sales_agent"
}
```

### **User Login**
```bash
POST /api/auth/login
{
  "email": "user@company.com",
  "password": "secure_password"
}
```

### **Get Current User**
```bash
GET /api/auth/me
Authorization: Bearer <token>
```

### **Update Profile**
```bash
PUT /api/auth/me
Authorization: Bearer <token>
{
  "first_name": "Jane",
  "preferences": {"theme": "dark"}
}
```

### **View Usage Stats**
```bash
GET /api/auth/usage
Authorization: Bearer <token>
```

## 🏢 **Organization Management**

### **Create Organization (Admin Only)**
```bash
POST /api/auth/organizations
Authorization: Bearer <admin_token>
{
  "name": "Acme Corp",
  "domain": "acme.com",
  "org_type": "enterprise",
  "max_users": 10,
  "max_leads": 5000
}
```

### **List Organizations**
```bash
GET /api/auth/organizations
Authorization: Bearer <admin_token>
```

### **List Organization Users**
```bash
GET /api/auth/organizations/{org_id}/users
Authorization: Bearer <token>
```

## 🛡️ **Data Isolation Examples**

### **Before (Single User)**
```python
# All users could access any lead
leads = db.query(DBLead).all()
```

### **After (Multi-User)**
```python
# Users only see leads from their organization
leads = db.query(DBLead).filter(
    DBLead.organization_id == current_user.organization_id
).all()
```

## 🔄 **Updated API Endpoints**

All main endpoints now require authentication and enforce organization isolation:

### **Chat Endpoints**
```bash
# All require: Authorization: Bearer <token>
POST /api/chat                    # Create chat with lead isolation
POST /api/chat/send               # Send message with user tracking
GET  /api/chat/history/{lead_id}  # Get history (org-scoped)
POST /api/chat/search             # Search messages (org-scoped)
```

### **Lead Endpoints**
```bash
# All require: Authorization: Bearer <token>
GET  /api/leads                   # Get organization leads only
POST /api/leads                   # Create lead in user's org
GET  /api/leads/{id}              # Get lead (access control)
```

### **Quote Endpoints**
```bash
# All require: Authorization: Bearer <token>
POST /api/generate-quote-from-conversation/{lead_id}  # With access control
```

## 📊 **Rate Limiting & Usage Tracking**

### **Default Limits**
- **API Calls**: 1,000 per day per user
- **AI Tokens**: 50,000 per month per user
- **Organization**: 1,000 leads, 5 users

### **Usage Monitoring**
```bash
GET /api/auth/usage
{
  "daily_api_calls": 45,
  "daily_ai_tokens": 1250,
  "monthly_api_calls": 890,
  "monthly_ai_tokens": 25000,
  "api_limit": 1000,
  "token_limit": 50000,
  "api_usage_percentage": 4.5,
  "token_usage_percentage": 50.0
}
```

## 🎛️ **Configuration Options**

### **Environment Variables**
```bash
# Authentication
SECRET_KEY=your-secure-secret-key-here
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# User Registration
ENABLE_USER_REGISTRATION=true
DEFAULT_ORG_MAX_USERS=5
DEFAULT_USER_API_RATE_LIMIT=1000

# Rate Limiting
ENABLE_RATE_LIMITING=true
RATE_LIMIT_PER_MINUTE=60
```

### **Multi-User Settings in config.py**
```python
# Authentication & Security
secret_key: str = "your-secret-key"
access_token_expire_minutes: int = 30

# Multi-user & Organization Settings
enable_user_registration: bool = True
default_organization_max_users: int = 5
default_user_api_rate_limit: int = 1000
```

## 🔧 **Admin Operations**

### **User Management**
```bash
# List all users (admin only)
GET /api/auth/admin/users

# Update any user (admin only)
PUT /api/auth/admin/users/{user_id}

# Deactivate user (admin only)
DELETE /api/auth/admin/users/{user_id}
```

### **System Statistics**
```bash
GET /api/auth/admin/stats
{
  "users": {"total": 25, "active": 23},
  "organizations": {"total": 5},
  "leads": {"total": 1250},
  "messages": {"total": 15000}
}
```

## 🧪 **Testing Multi-User Features**

### **1. Create Test Users**
```python
# Run setup script or use the demo users:
# sales1@example.com / demo123 (Sales Agent)
# manager@example.com / demo123 (Sales Manager)
# viewer@example.com / demo123 (Viewer)
```

### **2. Test Data Isolation**
```bash
# Login as different users and verify they only see their organization's data
curl -X GET "http://localhost:3001/api/leads" \
  -H "Authorization: Bearer <user1_token>"

curl -X GET "http://localhost:3001/api/leads" \
  -H "Authorization: Bearer <user2_token>"
```

### **3. Test Rate Limiting**
```bash
# Make multiple rapid requests to test rate limiting
for i in {1..100}; do
  curl -X GET "http://localhost:3001/api/leads" \
    -H "Authorization: Bearer <token>"
done
```

## 🚨 **Security Considerations**

### **Production Checklist**
- [ ] Change default admin password
- [ ] Set secure `SECRET_KEY` environment variable
- [ ] Use HTTPS in production
- [ ] Set appropriate CORS origins
- [ ] Configure proper rate limits
- [ ] Set up monitoring and logging
- [ ] Regular security updates

### **Password Security**
```python
# Passwords are hashed with bcrypt
# Minimum 8 characters required
# JWT tokens expire after 30 minutes
```

### **API Security**
```python
# All endpoints protected with JWT authentication
# Organization-level data isolation
# Role-based access control
# API rate limiting per user
```

## 🐛 **Troubleshooting**

### **Common Issues**

**1. "User not found" error**
```bash
# Run setup script to create initial users
python scripts/setup_initial_data.py
```

**2. "Access denied" for leads**
```bash
# Ensure user belongs to same organization as the lead
# Check user's organization_id matches lead's organization_id
```

**3. Rate limit exceeded**
```bash
# Wait for rate limit reset or increase user limits
PUT /api/auth/admin/users/{user_id}
{"api_rate_limit": 2000}
```

**4. Token expired**
```bash
# Login again to get new token
POST /api/auth/login
```

### **Debug Endpoints**
```bash
# Check user information
GET /api/auth/me

# Check database status
GET /api/debug/database

# Check system performance
GET /api/admin/system-performance
```

## 📈 **Scaling Considerations**

### **For 10+ Users**
- Increase database connection pool
- Set up Redis for session storage
- Implement caching layers
- Monitor API usage patterns

### **For Multiple Organizations**
- Consider database partitioning
- Implement organization-specific settings
- Set up monitoring per organization
- Plan for resource allocation

### **For High Volume**
- Use load balancers
- Implement queue systems for AI requests
- Set up metrics and alerting
- Consider microservices architecture

## 🎉 **What's New**

### **Multi-User Features Added**
✅ **User Authentication** with JWT tokens  
✅ **Organization-based Multi-tenancy**  
✅ **Role-based Access Control**  
✅ **Data Isolation** between organizations  
✅ **Rate Limiting** per user  
✅ **API Usage Tracking**  
✅ **Admin Management Interface**  
✅ **User Profile Management**  
✅ **Session Management**  

### **Backward Compatibility**
- Existing data structure preserved
- API endpoints maintain same interface
- Added authentication layer without breaking changes
- Gradual migration path for existing users

---

## 🆘 **Need Help?**

1. **Check logs**: `logs/main.log`
2. **Run diagnostics**: `GET /api/debug/database`
3. **Test authentication**: Use provided demo users
4. **Contact support**: Check documentation or create an issue

Your B2B Sales AI Assistant is now ready for **multiple users** with **enterprise-grade security**! 🚀 