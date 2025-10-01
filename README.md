# Malla - Docker-Enhanced Meshtastic Network Analyzer

This is a Docker-enhanced continuation of the original [Malla project](https://github.com/zenitraM/malla) - a comprehensive web analyzer for Meshtastic networks based on MQTT data.

### 🔧 What's Working
- ✅ Complete database schema initialization
- ✅ Real-time MQTT data capture and processing
- ✅ Web interface with full functionality
- ✅ PostgreSQL database with optimized queries
- ✅ Network topology visualization
- ✅ Longest links analysis
- ✅ Node tracking and statistics
- ✅ Packet analysis and filtering

## 🚀 Quick Start with Docker

This enhanced version provides a complete Docker-based deployment with PostgreSQL database, MQTT broker, and all necessary services orchestrated together.

### Prerequisites

- Docker and Docker Compose installed
- Git (to clone this repository)

### One-Command Setup

```bash
# Clone the repository
git clone https://github.com/n30nex/malla.git
cd malla

# Start all services (PostgreSQL, MQTT, Web UI, Data Capture)
docker-compose up --build
```

That's it! The system will:
- Set up a PostgreSQL database
- Start an MQTT broker
- Begin capturing Meshtastic data
- Launch the web interface

**Access the web interface at:** http://localhost:8080

## 🏗️ Architecture

This Docker setup includes:

- **PostgreSQL Database** - Stores all mesh network data
- **MQTT Broker** - Eclipse Mosquitto for message handling
- **Data Capture Service** - Captures and processes Meshtastic packets
- **Web Interface** - Flask-based UI for network analysis

## 📋 Services Overview

| Service | Port | Description |
|---------|------|-------------|
| Web UI | 8080 | Main web interface |
| PostgreSQL | 5432 | Database (internal) |
| MQTT Broker | 1883 | Message broker (internal) |

## ⚙️ Configuration

### Environment Variables

Copy the example environment file and customize:

```bash
cp env.example .env
```

Key configuration options in `.env`:

```bash
# MQTT Configuration (Required)
MALLA_MQTT_BROker_ADDRESS=mqtt.mt.gt
MALLA_MQTT_USERNAME=meshdev
MALLA_MQTT_PASSWORD=large4cats

# Database Configuration
POSTGRES_PASSWORD=yourpassword

# Web Interface
MALLA_NAME=My Malla Instance
MALLA_WEB_PORT=8080
```

### YAML Configuration

You can also use `config.yaml` for more detailed configuration:

```bash
cp config.sample.yaml config.yaml
# Edit config.yaml with your settings
```

## 🛠️ Development

### Local Development

For development without Docker:

```bash
# Install dependencies
pip install -e .

# Set up local database
export MALLA_DATABASE_HOST=localhost
export MALLA_DATABASE_PORT=5432
export MALLA_DATABASE_NAME=malla
export MALLA_DATABASE_USER=malla
export MALLA_DATABASE_PASSWORD=yourpassword

# Start services
python -m malla.mqtt_capture  # Terminal 1
python -m malla.web_ui        # Terminal 2
```

### Database Management

The system automatically initializes the database schema on first run. For manual database operations:

```bash
# Access PostgreSQL container
docker-compose exec postgres psql -U malla -d malla

# View database schema
\dt
```

## 📊 Features

### Network Analysis
- **Real-time Network Visualization** - Interactive mesh topology ✅ **WORKING**
- **Node Tracking** - Monitor device locations and status
- **Packet Analysis** - Deep dive into mesh communications
- **Traceroute Analysis** - Network path visualization
- **Performance Metrics** - SNR, distance, and connectivity stats
- **Longest Links Analysis** ✅ **WORKING**

### Data Management
- **PostgreSQL Backend** - Robust, scalable data storage
- **Optimized Queries** - Fast analysis of large datasets
- **Data Persistence** - Automatic data retention and cleanup
- **Export Capabilities** - Download network data

### User Interface
- **Modern Web UI** - Responsive, mobile-friendly interface
- **Interactive Maps** - Visualize network topology
- **Real-time Updates** - Live data streaming
- **Advanced Filtering** - Powerful search and filter options

## 🔧 Advanced Configuration

### Custom MQTT Broker

To use your own MQTT broker instead of the included one:

```yaml
# In docker-compose.yml, comment out the mqtt service
# and update environment variables:
environment:
  MALLA_MQTT_BROKER_ADDRESS: your.broker.address
  MALLA_MQTT_PORT: 1883
  MALLA_MQTT_USERNAME: your_username
  MALLA_MQTT_PASSWORD: your_password
```

### Production Deployment

For production use:

1. **Change default passwords** in `.env`
2. **Use external database** for better performance
3. **Configure reverse proxy** (nginx/Apache)
4. **Set up SSL/TLS** for secure connections
5. **Configure logging** for monitoring

### Scaling

The system supports horizontal scaling:

- **Multiple capture services** for high-throughput networks
- **Database clustering** for large datasets
- **Load balancing** for web interface
- **Message queue** for async processing

## 📈 Performance

### Optimizations Included

- **Tier B Pipeline** - Write-optimized data processing
- **Materialized Views** - Pre-computed analytics
- **Database Indexing** - Optimized query performance
- **Connection Pooling** - Efficient database connections
- **Caching** - Reduced computation overhead

### Monitoring

Check system health:

```bash
# View service logs
docker-compose logs -f

# Check database status
docker-compose exec postgres pg_isready -U malla

# Monitor resource usage
docker stats
```

## 🤝 Contributing

This project extends the original [Malla](https://github.com/zenitraM/malla) with Docker enhancements. **All major issues have been resolved!** The system is now fully functional.

### Recent Fixes Applied

1. **Database Schema Issues** - Fixed PostgreSQL immutable function errors
2. **Table Creation** - All required tables now create successfully
3. **Query Optimization** - Improved database performance and indexing
4. **Service Integration** - All services now work together seamlessly

### Areas for Future Enhancement

1. **Performance Tuning** - Further optimize database queries for large datasets
2. **UI Improvements** - Enhanced user interface and visualization features
3. **Monitoring** - Add health checks and monitoring capabilities
4. **Documentation** - Expand user guides and API documentation

### Development Setup

```bash
# Clone and setup
git clone https://github.com/n30nex/malla.git
cd malla

# Start development environment
docker-compose up --build

# Check service status
docker-compose ps

# View logs
docker-compose logs -f

# Access database
docker-compose exec postgres psql -U malla -d malla

# Run tests
docker-compose exec malla-web python -m pytest
```

## 🔧 Troubleshooting

### Common Issues and Solutions

#### Database Connection Issues
```bash
# Check if PostgreSQL is running
docker-compose ps postgres

# View database logs
docker-compose logs postgres

# Test database connection
docker-compose exec postgres pg_isready -U malla
```

#### Web Interface Not Loading
```bash
# Check web service status
docker-compose ps malla-web

# View web service logs
docker-compose logs malla-web

# Test web interface
curl http://localhost:8080
```

#### MQTT Data Not Capturing
```bash
# Check capture service
docker-compose logs malla-capture

# Verify MQTT broker connection
docker-compose logs mosquitto
```

#### Reset Everything
```bash
# Stop all services
docker-compose down

# Remove volumes (WARNING: This deletes all data)
docker-compose down -v

# Rebuild and restart
docker-compose up --build
```

### Performance Optimization

For better performance with large datasets:

```bash
# Increase PostgreSQL memory
# Add to docker-compose.yml under postgres service:
environment:
  POSTGRES_SHARED_BUFFERS: 256MB
  POSTGRES_EFFECTIVE_CACHE_SIZE: 1GB

# Monitor resource usage
docker stats
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Original Malla Project** - [zenitraM/malla](https://github.com/zenitraM/malla)
- **Meshtastic Community** - For the amazing mesh networking platform
- **Contributors** - All those who have helped improve this project


- **Issues** - Report bugs and request features
- **Discussions** - Community support and questions
- **Documentation** - Check the original [Malla documentation](https://github.com/zenitraM/malla#readme)


---

