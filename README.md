# Malla - Docker-Enhanced Meshtastic Network Analyzer

This is a Docker-enhanced continuation of the original [Malla project](https://github.com/n30nex/malla) - a comprehensive web analyzer for Meshtastic networks based on MQTT data.

## ⚠️ Current Status: PostgreSQL Migration Issues

**Entire system migrated from SQLite to PostgreSQL. Some issues remain, need help! The new Live Topology and the Longest Links pages do not work. This is a mess of AI spaghetti please send help!**

The system is currently capturing data successfully, but several key features are broken due to the database migration. We need assistance with:
- Live Topology visualization
- Longest Links analysis
- Database query optimization
- UI component fixes

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
MALLA_MQTT_BROker_ADDRESS=mqtt.meshtastic.org
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
- **Real-time Network Visualization** - Interactive mesh topology ⚠️ **BROKEN - Needs Help**
- **Node Tracking** - Monitor device locations and status
- **Packet Analysis** - Deep dive into mesh communications
- **Traceroute Analysis** - Network path visualization
- **Performance Metrics** - SNR, distance, and connectivity stats
- **Longest Links Analysis** ⚠️ **BROKEN - Needs Help**

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

## 🤝 Contributing - URGENT HELP NEEDED!

This project extends the original [Malla](https://github.com/n30nex/malla) with Docker enhancements. **We desperately need help fixing the PostgreSQL migration issues!**

### Known Issues Requiring Help

1. **Live Topology Page** - Not displaying network visualization
2. **Longest Links Page** - Database queries failing
3. **PostgreSQL Query Optimization** - Some queries are slow or broken
4. **UI Components** - Several frontend components not working with new backend

### Development Setup

```bash
# Clone and setup
git clone https://github.com/n30nex/malla.git
cd malla

# Start development environment
docker-compose up --build

# Check logs for errors
docker-compose logs malla-web
docker-compose logs malla-capture

# Run tests (may fail due to migration issues)
docker-compose exec malla-web python -m pytest
```

### How to Help

1. **Database Issues**: Check PostgreSQL queries in `src/malla/database/`
2. **Frontend Issues**: Look at `src/malla/templates/` and `src/malla/static/`
3. **API Issues**: Review `src/malla/routes/` for broken endpoints
4. **Logs**: Check container logs for specific error messages

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Original Malla Project** - [zenitraM/malla](https://github.com/zenitraM/malla)
- **Meshtastic Community** - For the amazing mesh networking platform
- **Contributors** - All those who have helped improve this project

## 📞 Support

- **Issues** - Report bugs and request features
- **Discussions** - Community support and questions
- **Documentation** - Check the original [Malla documentation](https://github.com/zenitraM/malla#readme)

## 🔗 Related Projects

- [Meshtastic](https://meshtastic.org/) - The mesh networking platform
- [Original Malla](https://github.com/zenitraM/malla) - The base project
- [Meshtastic MQTT](https://meshtastic.org/docs/software/mqtt) - MQTT integration guide

---

**⚠️ WARNING: This system has PostgreSQL migration issues!**

While the system captures data successfully, several key features are broken. We need help fixing:
- Live Topology visualization
- Longest Links analysis
- Database query optimization
- UI component issues

**Ready to help fix the issues?** Start with `docker-compose up --build` and check the logs for errors!
