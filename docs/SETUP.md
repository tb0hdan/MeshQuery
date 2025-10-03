# Setup Instructions

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd MeshQuery
   ```

2. **Start the application:**
   ```bash
   docker compose up --build
   ```

3. **Access the web interface:**
   Open your browser and go to: http://localhost:8080

## Configuration

### Environment Variables

Create a `.env` file in the project root with your MQTT broker settings:

```env
# MQTT Configuration
MALLA_MQTT_HOST=your-mqtt-broker.com
MALLA_MQTT_PORT=1883
MALLA_MQTT_USERNAME=your-username
MALLA_MQTT_PASSWORD=your-password
MALLA_MQTT_TOPIC=msh/2/#

# Database Configuration (optional - defaults work for Docker)
MALLA_DB_HOST=postgres
MALLA_DB_PORT=5432
MALLA_DB_NAME=malla
MALLA_DB_USER=malla
MALLA_DB_PASSWORD=malla

# Web Interface Configuration (optional)
MALLA_HOST=0.0.0.0
MALLA_PORT=8080
MALLA_DEBUG=false
```

### Sample Configuration

Copy `config.sample.yaml` to `config.yaml` and customize as needed:

```bash
cp config.sample.yaml config.yaml
```

## Features

- **Dashboard**: Network overview and statistics
- **Packets**: Raw packet analysis and filtering
- **Nodes**: Node management and details
- **Traceroutes**: Network path analysis
- **Map**: Geographic visualization
- **Network Graph**: Interactive network topology with live animations
- **Longest Links**: Analysis of network connections
- **Tools**: Additional analysis tools

## Troubleshooting

### Common Issues

1. **Port 8080 already in use:**
   - Change the port in `docker-compose.yml` or stop the conflicting service

2. **Database connection errors:**
   - Ensure PostgreSQL container is running: `docker compose ps`
   - Check database logs: `docker compose logs postgres`

3. **MQTT connection issues:**
   - Verify your MQTT broker settings in `.env`
   - Check MQTT broker logs: `docker compose logs malla-capture`

### Logs

View logs for specific services:
```bash
# All services
docker compose logs

# Specific service
docker compose logs malla-web
docker compose logs malla-capture
docker compose logs postgres
```

### Reset Database

To start fresh with a clean database:
```bash
docker compose down -v
docker compose up --build
```

## Development

### Local Development

For development with live code changes:

1. Install Python dependencies:
   ```bash
   pip install -e .
   ```

2. Set up environment variables in `.env`

3. Run the application:
   ```bash
   python -m malla.web_ui
   ```

### Building Custom Images

```bash
# Build specific service
docker compose build malla-web

# Build all services
docker compose build
```

## Support

For issues and questions:
- Check the logs first: `docker compose logs`
- Review the configuration files
- Ensure all required environment variables are set
