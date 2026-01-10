# Jarvis Deployment Guide

Complete guide for deploying Jarvis to a new server or environment.

## Prerequisites

### System Requirements
- **OS**: Linux (Ubuntu 20.04+ recommended) or macOS
- **Python**: 3.10 or higher
- **MySQL**: 8.0 or higher
- **RAM**: Minimum 4GB (8GB+ recommended)
- **Storage**: 10GB+ free space

### External Services
- **Ollama**: Local LLM inference server
  - Requires GPU (recommended) or CPU fallback
  - Model: llama3.1:8b or qwen3:8b (default)
  - Minimum 8GB VRAM for GPU inference

## Step-by-Step Deployment

### 1. Clone Repository

```bash
# Clone to desired location
git clone <repository-url> jarvis
cd jarvis
```

### 2. Set Up Python Environment

```bash
# Create virtual environment
python3 -m venv venv

# Activate environment
source venv/bin/activate  # Linux/macOS
# OR
venv\Scripts\activate  # Windows

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

### 3. Install and Configure Ollama

```bash
# Install Ollama (Linux)
curl -fsSL https://ollama.com/install.sh | sh

# Start Ollama service
ollama serve &

# Pull the LLM model (this may take several minutes)
ollama pull llama3.1:8b

# Verify model is available
ollama list
```

**For remote Ollama server:**
- Update `config/config.yaml` with remote host IP
- Ensure firewall allows connection on port 11434

### 4. Set Up MySQL Database

```bash
# Install MySQL (if not already installed)
sudo apt-get update
sudo apt-get install mysql-server

# Start MySQL service
sudo systemctl start mysql
sudo systemctl enable mysql

# Create database and user
mysql -u root -p << EOF
CREATE DATABASE jarvis CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'jarvis_user'@'localhost' IDENTIFIED BY 'your_secure_password';
GRANT ALL PRIVILEGES ON jarvis.* TO 'jarvis_user'@'localhost';
FLUSH PRIVILEGES;
EOF
```

### 5. Initialize Databases

```bash
# Activate virtual environment if not already active
source venv/bin/activate

# Initialize memory system (episodic/semantic memories)
python scripts/init_memory_db.py

# Initialize procedural memory (learning system)
python scripts/init_procedural_memory_db.py

# Initialize API authentication (if using web API)
python scripts/init_api_db.py

# Add introspection fields (if not already included)
mysql -h localhost -u jarvis_user -p jarvis < scripts/add_introspection_fields.sql
```

**Verify database initialization:**
```bash
mysql -h localhost -u jarvis_user -p jarvis -e "SHOW TABLES;"
```

Expected tables:
- `memories`
- `memory_audit_log`
- `procedural_memory`
- `goals`
- `subtasks`
- `users` (if API enabled)
- `api_keys` (if API enabled)
- `conversation_sessions` (if API enabled)

### 6. Configure Application

```bash
# Copy configuration template
cp config/config.yaml config/config.yaml.local

# Edit configuration
nano config/config.yaml.local
```

**Key configuration settings:**

```yaml
# Ollama LLM Configuration
ollama:
  host: "localhost"  # or remote GPU server IP
  port: 11434
  model: "llama3.1:8b"
  timeout: 120

  # Specialized LLM timeouts (optional overrides)
  verifier_timeout: 60
  curator_timeout: 90
  decomposer_timeout: 180
  introspection_timeout: 180

# Memory System
memory:
  enabled: true
  vector_db_path: "data/vector_store"  # Will be created automatically

  # MySQL connection
  mysql_host: "localhost"
  mysql_database: "jarvis"
  mysql_user: "jarvis_user"
  mysql_password: "your_secure_password"

  # Memory retrieval settings
  k: 5  # Number of memories to retrieve
  decay_rate: 0.05  # Recency decay rate

  # Procedural memory (learning)
  procedural_enabled: true
  procedural_adaptive: true  # Adaptive confidence thresholds
  procedural_auto_decay: true  # Auto-decay unused heuristics

  # Memory verification
  verification_enabled: true
  verification_threshold: 0.6  # Confidence threshold for verification

# Goal Management
goals:
  enabled: true
  auto_detect: true  # Automatically detect multi-step tasks
  auto_execute_goals: false  # Set to true for fully autonomous execution

# Conversation Summarization
summarization:
  enabled: true
  max_tokens: 8000  # Maximum context window
  trigger_threshold: 0.7  # Summarize when 70% full
  preserve_recent: 5  # Keep last N messages unsummarized

# API Server (optional)
api:
  host: "0.0.0.0"
  port: 8000
  session_timeout: 3600  # 1 hour
  max_sessions: 10

# Tool execution
tools:
  sandbox_mode: false  # Set true for restricted execution
  max_retries: 3
  timeout: 30  # Default tool timeout in seconds
```

### 7. Create Required Directories

```bash
# Create data directories
mkdir -p data/vector_store
mkdir -p data/backups
mkdir -p logs

# Set permissions
chmod 755 data
chmod 755 logs
```

### 8. Test Installation

**Test CLI Interface:**
```bash
python main.py
```

Expected output:
```
[INFO] Memory system initialized
[INFO] Procedural memory loaded: X heuristics
[INFO] Goal management enabled
[INFO] Jarvis CLI ready

You: Hello, my name is Steve
Jarvis: Hello Steve! Nice to meet you...
```

**Test memory:**
```
You: Remember that I like coffee
Jarvis: I'll remember that you like coffee.

You: What do I like?
Jarvis: You like coffee.
```

**Exit CLI:**
```
You: /quit
```

### 9. Set Up API Server (Optional)

**Create API user:**
```bash
python scripts/manage_users.py create admin "Admin User" --role master
# Save the API key that is printed!
```

**Start API server:**
```bash
# Development mode (with auto-reload)
uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload

# Production mode
uvicorn api.server:app --host 0.0.0.0 --port 8000 --workers 4
```

**Test API:**
```bash
# Replace YOUR_API_KEY with the key from user creation
export API_KEY="your_api_key_here"

# Test authentication
curl -H "Authorization: Bearer $API_KEY" http://localhost:8000/api/v1/me

# Test chat
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, I am testing the API"}'
```

### 10. Set Up as System Service (Linux)

**Create systemd service file:**
```bash
sudo nano /etc/systemd/system/jarvis-api.service
```

**Service configuration:**
```ini
[Unit]
Description=Jarvis AI Assistant API
After=network.target mysql.service

[Service]
Type=simple
User=steve
Group=steve
WorkingDirectory=/home/steve/AI/jarvis
Environment="PATH=/home/steve/AI/jarvis/venv/bin"
ExecStart=/home/steve/AI/jarvis/venv/bin/uvicorn api.server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and start service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable jarvis-api
sudo systemctl start jarvis-api

# Check status
sudo systemctl status jarvis-api

# View logs
sudo journalctl -u jarvis-api -f
```

## Security Configuration

### 1. Database Security

**Change default password:**
```sql
ALTER USER 'jarvis_user'@'localhost' IDENTIFIED BY 'very_secure_password_here';
FLUSH PRIVILEGES;
```

**Restrict network access:**
```bash
# Edit MySQL config
sudo nano /etc/mysql/mysql.conf.d/mysqld.cnf

# Ensure bind-address is localhost if DB is local
bind-address = 127.0.0.1
```

### 2. API Security

**Use HTTPS in production:**
```bash
# Install nginx as reverse proxy
sudo apt-get install nginx certbot python3-certbot-nginx

# Configure nginx
sudo nano /etc/nginx/sites-available/jarvis
```

**Nginx configuration:**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }
}
```

**Get SSL certificate:**
```bash
sudo certbot --nginx -d your-domain.com
```

**Update CORS settings** in `api/server.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://your-frontend-domain.com"],  # Specific domains only
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
```

### 3. Firewall Configuration

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow ssh
sudo ufw allow http
sudo ufw allow https

# Block direct access to API port (use nginx instead)
# sudo ufw deny 8000

# Enable firewall
sudo ufw enable
```

### 4. API Key Management

**Rotate API keys regularly:**
```bash
# Revoke old key
python scripts/manage_users.py revoke username

# Generate new key
python scripts/manage_users.py regenerate username
```

**Set key expiration:**
```sql
UPDATE api_keys
SET expires_at = DATE_ADD(NOW(), INTERVAL 90 DAY)
WHERE user_id = X;
```

## Monitoring and Maintenance

### Log Files

**Application logs:**
```bash
# View recent logs
tail -f logs/jarvis.log

# Search for errors
grep ERROR logs/jarvis.log
```

**API access logs:**
```bash
# View API requests
tail -f logs/api.log
```

### Database Maintenance

**Backup database:**
```bash
# Create backup script
cat > backup_jarvis.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/steve/backups/jarvis"
mkdir -p "$BACKUP_DIR"
mysqldump -u jarvis_user -p'your_password' jarvis > "$BACKUP_DIR/jarvis_$(date +%Y%m%d_%H%M%S).sql"
# Keep only last 30 days
find "$BACKUP_DIR" -name "jarvis_*.sql" -mtime +30 -delete
EOF

chmod +x backup_jarvis.sh

# Set up daily cron job
crontab -e
# Add: 0 2 * * * /home/steve/backup_jarvis.sh
```

**Clean old data:**
```sql
-- Archive old goals (completed > 90 days ago)
DELETE FROM subtasks WHERE goal_id IN (
    SELECT id FROM goals WHERE status = 'completed'
    AND updated_at < DATE_SUB(NOW(), INTERVAL 90 DAY)
);

DELETE FROM goals WHERE status = 'completed'
AND updated_at < DATE_SUB(NOW(), INTERVAL 90 DAY);

-- Clean old conversation sessions (> 30 days inactive)
DELETE FROM conversation_sessions
WHERE last_activity_at < DATE_SUB(NOW(), INTERVAL 30 DAY);
```

### Performance Monitoring

**Check memory usage:**
```bash
# Database size
mysql -u jarvis_user -p jarvis -e "
SELECT
    table_name AS 'Table',
    ROUND(((data_length + index_length) / 1024 / 1024), 2) AS 'Size (MB)'
FROM information_schema.TABLES
WHERE table_schema = 'jarvis'
ORDER BY (data_length + index_length) DESC;
"

# Vector store size
du -sh data/vector_store

# Application memory
ps aux | grep python | grep jarvis
```

**Monitor LLM inference:**
```bash
# Check Ollama status
curl http://localhost:11434/api/tags

# Monitor GPU usage (if available)
nvidia-smi
```

## Troubleshooting

### Common Issues

**1. "Cannot connect to MySQL"**
```bash
# Check MySQL is running
sudo systemctl status mysql

# Test connection
mysql -u jarvis_user -p -h localhost jarvis

# Check config has correct credentials
grep mysql config/config.yaml.local
```

**2. "Cannot connect to Ollama"**
```bash
# Check Ollama is running
ps aux | grep ollama

# Test connection
curl http://localhost:11434/api/tags

# Restart Ollama
pkill ollama
ollama serve &
```

**3. "Module not found" errors**
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

**4. "ChromaDB permission error"**
```bash
# Fix data directory permissions
chmod -R 755 data/vector_store
chown -R $USER:$USER data/
```

**5. API returns 401 Unauthorized**
```bash
# Verify API key format
# Should be: Authorization: Bearer <key>

# Check key is active in database
mysql -u jarvis_user -p jarvis -e "
SELECT ak.api_key, u.username, ak.is_active, ak.expires_at
FROM api_keys ak
JOIN users u ON ak.user_id = u.id
WHERE ak.api_key = 'your_key_here';
"
```

**6. Tests failing**
```bash
# Run individual test
python -m pytest tests/test_memory_system.py -v

# Check test database is initialized
python scripts/init_memory_db.py

# Verify Ollama is responding
curl http://localhost:11434/api/generate -d '{
  "model": "llama3.1:8b",
  "prompt": "Hello",
  "stream": false
}'
```

## Updating Jarvis

### Pull Latest Changes

```bash
# Activate environment
source venv/bin/activate

# Pull updates
git pull origin main

# Install any new dependencies
pip install -r requirements.txt

# Run database migrations (if any)
# Check scripts/ directory for new migration files
ls scripts/*.sql

# Restart services
sudo systemctl restart jarvis-api  # If using systemd
```

### Database Migrations

When updating, check for migration scripts:
```bash
# List migration scripts
ls scripts/*.sql

# Run migrations in order
mysql -u jarvis_user -p jarvis < scripts/add_introspection_fields.sql
# etc.
```

## Uninstalling

```bash
# Stop services
sudo systemctl stop jarvis-api
sudo systemctl disable jarvis-api

# Remove service file
sudo rm /etc/systemd/system/jarvis-api.service
sudo systemctl daemon-reload

# Drop database
mysql -u root -p -e "DROP DATABASE jarvis;"
mysql -u root -p -e "DROP USER 'jarvis_user'@'localhost';"

# Remove application
rm -rf /home/steve/AI/jarvis

# Remove Ollama (optional)
sudo systemctl stop ollama
sudo rm /usr/local/bin/ollama
sudo rm -rf ~/.ollama
```

## Production Checklist

Before deploying to production:

- [ ] Change all default passwords
- [ ] Enable HTTPS (SSL/TLS)
- [ ] Configure CORS properly (no wildcards)
- [ ] Set up database backups
- [ ] Configure log rotation
- [ ] Set up monitoring/alerting
- [ ] Test API key authentication
- [ ] Verify firewall rules
- [ ] Set up reverse proxy (nginx)
- [ ] Configure rate limiting
- [ ] Test disaster recovery process
- [ ] Document custom configuration
- [ ] Set API key expiration
- [ ] Enable audit logging
- [ ] Review role-based permissions
- [ ] Test with production-like load

## Support

For issues or questions:
- Check logs: `logs/jarvis.log`
- Review documentation: `docs/`
- Run demos: `examples/`
- Check database: SQL queries in `scripts/`

---

**Deployment completed!** You should now have a fully functional Jarvis instance.
