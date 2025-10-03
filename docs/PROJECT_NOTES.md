# Malla (MeshQuery) - Project Notes

## Project Overview

**Malla** is a comprehensive Docker-enhanced web analyzer for Meshtastic networks based on MQTT data. This is a continuation of the original [Malla project](https://github.com/zenitraM/malla) with significant improvements including Docker orchestration, PostgreSQL database support, and enhanced web interfaces.

### Core Functionality
- **Real-time MQTT data capture and processing** from Meshtastic networks
- **PostgreSQL database** with optimized queries and materialized views
- **Web interface** with network topology visualization
- **Network analysis tools** including traceroute, longest links, and node tracking
- **Geographic visualization** with interactive maps and heatmaps

## Directory Structure

```
MeshQuery/
├── CLAUDE.md                       # Claude instructions and project commands
├── config.sample.yaml             # Sample YAML configuration
├── docker-compose.yml             # Docker orchestration
├── Dockerfile                     # Container build instructions
├── docs/                          # Project documentation
│   ├── SETUP.md                   # Setup and deployment guide
│   └── TODO.md                    # Project TODOs and completed tasks
├── .env.example                   # Environment variables template
├── env.example                    # Alternative env template
├── .gitattributes                 # Git file attributes
├── .github/                       # GitHub Actions and workflows
│   └── workflows/
│       └── ci.yml
├── .gitignore                     # Git ignore patterns
├── LICENSE                        # MIT License
├── Makefile                       # Build, lint, and test commands
├── mosquitto/                     # MQTT broker configuration
│   └── mosquitto.conf
├── pyproject.toml                 # Python project configuration
├── README.md                      # Main project documentation
├── src/                          # Source code
│   ├── __init__.py
│   └── malla/                    # Main package
│       ├── __init__.py           # Package initialization
│       ├── config.py             # Configuration management
│       ├── db_init.py           # Database initialization
│       ├── mqtt_capture.py      # MQTT data capture service
│       ├── web_ui.py            # Flask web application
│       ├── wsgi.py              # WSGI entry point
│       ├── database/            # Database layer
│       │   ├── __init__.py
│       │   ├── adapter.py       # Database adapter
│       │   ├── connection.py    # Database connections
│       │   ├── connection_postgres.py  # PostgreSQL specific connection
│       │   ├── packet_repository_optimized.py  # Optimized packet queries
│       │   ├── repositories.py  # Data repositories
│       │   └── schema_tier_b.py # Tier B schema (problematic - needs refactor)
│       ├── models/              # Data models
│       │   ├── __init__.py
│       │   └── traceroute.py    # Traceroute data models
│       ├── routes/              # Flask route handlers
│       │   ├── __init__.py
│       │   ├── api_routes.py    # API endpoints
│       │   ├── gateway_routes.py  # Gateway analysis routes
│       │   ├── live_routes.py   # Live data routes
│       │   ├── main_routes.py   # Main web routes
│       │   ├── node_routes.py   # Node management routes
│       │   ├── packet_routes.py # Packet analysis routes
│       │   ├── stream_routes.py # Data streaming routes
│       │   └── traceroute_routes.py  # Traceroute routes
│       ├── scripts/             # Utility scripts
│       │   └── tier_b_manager.py  # Tier B management (problematic)
│       ├── services/            # Business logic services
│       │   ├── __init__.py
│       │   ├── analytics_service.py  # Analytics computations
│       │   ├── gateway_service.py    # Gateway analysis
│       │   ├── location_service.py   # Location/GPS services
│       │   ├── materialized_view_refresher.py  # DB view management
│       │   ├── meshtastic_service.py  # Meshtastic protocol handling
│       │   ├── node_service.py       # Node management
│       │   ├── tier_b_initializer.py # Tier B initialization (problematic)
│       │   └── traceroute_service.py # Traceroute analysis
│       └── utils/               # Utility modules
│           ├── __init__.py
│           ├── cache.py         # Caching utilities
│           ├── decryption.py    # Message decryption
│           ├── error_handler.py # Error handling
│           ├── formatting.py    # Data formatting
│           ├── geo_utils.py     # Geographic utilities
│           ├── node_utils.py    # Node utilities
│           ├── serialization_utils.py  # Data serialization
│           ├── traceroute_graph.py     # Traceroute graph algorithms
│           ├── traceroute_hop_extractor.py  # Hop extraction
│           ├── traceroute_utils.py     # Traceroute utilities
│           └── validation_schemas.py   # Data validation
└── tests/                       # Test suite
    ├── test_db_init.py         # Database initialization tests
    ├── test_decryption.py      # Decryption tests
    ├── test_error_handler.py   # Error handling tests
    ├── test_mqtt_capture.py    # MQTT capture tests
    ├── test_packet_repository_optimized.py  # Repository tests
    └── test_repositories.py    # General repository tests
```

## Technology Stack

### Backend
- **Python 3.12+** - Core language
- **Flask 3.0+** - Web framework
- **PostgreSQL** - Primary database (with SQLite fallback)
- **SQLAlchemy 2.0+** - ORM and database abstraction
- **Gunicorn + Gevent** - WSGI server for production
- **Paho MQTT 2.1+** - MQTT client library

### Frontend
- **Jinja2** - Template engine
- **Plotly 5.17+** - Interactive visualizations
- **JavaScript** - Client-side interactions
- **CSS/HTML** - UI styling and structure

### Infrastructure
- **Docker & Docker Compose** - Containerization
- **Eclipse Mosquitto** - MQTT broker
- **Nginx** (optional) - Reverse proxy

### Development Tools
- **PyTest 8.4+** - Testing framework
- **MyPy 1.18** - Static type checking
- **Pylint 3.3** - Code linting
- **Coverage 7.6+** - Test coverage
- **Ruff** - Code formatting and linting

## Key Features

### Working Features ✅
- **Complete database schema initialization**
- **Real-time MQTT data capture and processing**
- **Web interface with full functionality**
- **PostgreSQL database with optimized queries**
- **Network topology visualization**
- **Node tracking and statistics**
- **Packet analysis and filtering**
- **Pagination for nodes page** (server-side, configurable page sizes)
- **Enhanced map animations** (pulse/ripple effects)
- **MQTT packet filtering** (150km limit with SNR/RSSI validation)
- **Light/Dark theme toggle** (system preference detection)
- **Packet heatmap improvements** (zoom-responsive sizing)

### Known Issues/Areas for Improvement 🔧

#### High Priority Issues
1. **Tier B Pipeline Refactoring** - Major architectural issue
   - Complex "Tier B" system for hop extraction and link analysis
   - Creates performance bottlenecks and maintenance headaches
   - Should be refactored into simpler, more robust solution
   - Affects longest links page and gateway analysis

2. **Live Topography** - Needs significant work
   - Animations don't work correctly
   - Traceroute with hops visualization broken
   - Real-time updates not functioning properly

3. **API/Backend Database Handling** - Performance issues
   - PostgreSQL to WebUI is fast but API layer has problems
   - Inefficient database queries in some areas
   - Connection pooling and caching need optimization

#### Medium Priority Issues
4. **Schema and Migrations** - Technical debt
   - Database schema is messy and inconsistent
   - Migration system needs cleanup
   - Duplicate/redundant tables and fields

5. **Code Cleanup** - Maintenance
   - Duplicate/useless functions and pages
   - Dangling code from incomplete features
   - Inconsistent coding patterns

## Configuration

### Environment Variables
The application uses environment variables for configuration:

```bash
# MQTT Configuration (Required)
MALLA_MQTT_HOST=mqtt.mt.gt
MALLA_MQTT_USERNAME=meshdev
MALLA_MQTT_PASSWORD=large4cats

# Database Configuration
POSTGRES_PASSWORD=yourpassword
MALLA_DB_HOST=postgres
MALLA_DB_PORT=5432

# Web Interface
MALLA_NAME=My Malla Instance
MALLA_WEB_PORT=8080
```

### YAML Configuration
Alternative configuration via `config.yaml`:
- Copy `config.sample.yaml` to `config.yaml`
- Supports more detailed configuration options
- Environment variables take precedence

## Development Workflow

### Project Commands (via Makefile)
- **Lint**: `make lint` (pylint)
- **Type Check**: `make mypy`
- **Test**: `make test` (pytest with coverage)
- **All**: `make all` (runs lint, mypy, test)

### Development Setup
1. **Local Development**:
   ```bash
   pip install -e .
   python -m malla.web_ui
   ```

2. **Docker Development**:
   ```bash
   docker-compose up --build
   ```

3. **Testing**:
   ```bash
   pytest --cov src/
   ```

## Architecture Notes

### Data Flow
1. **MQTT Capture** (`mqtt_capture.py`) → receives Meshtastic packets
2. **Database Layer** → stores and indexes packet data
3. **Services** → process and analyze data
4. **Routes** → expose data via web API
5. **Templates** → render web interface

### Key Architectural Decisions
- **PostgreSQL Primary**: Better performance for complex queries
- **Materialized Views**: Pre-computed analytics for performance
- **Tier B Pipeline**: Separate processing for hop analysis (problematic)
- **Flask Blueprints**: Modular route organization
- **Docker Orchestration**: Simplified deployment

### Performance Optimizations
- **Write-optimized data processing**
- **Database indexing** on key fields
- **Connection pooling** for database connections
- **Caching** for frequently accessed data
- **Pagination** for large datasets

## Recent Changes Summary

Based on `docs/TODO.md`, significant recent improvements include:
- ✅ Server-side pagination implementation
- ✅ Enhanced map animations with better visibility
- ✅ MQTT packet filtering with distance/signal validation
- ✅ Fixed light/dark theme toggle
- ✅ Improved packet heatmap responsiveness
- ✅ Gateway comparison and hop analysis API fixes

## Future Development Priorities

1. **Refactor Tier B Pipeline** - Replace with simpler, more maintainable solution
2. **Fix Live Topography** - Implement proper real-time animations
3. **Database Performance** - Optimize API layer and query efficiency
4. **Schema Cleanup** - Consolidate and clean database design
5. **Code Cleanup** - Remove duplicate/unused code and features

## Dependencies

### Core Runtime Dependencies
- Flask ecosystem (Flask, Jinja2, Werkzeug)
- Database (PostgreSQL, SQLAlchemy, psycopg2-binary)
- MQTT (paho-mqtt)
- Meshtastic protocol (meshtastic, cryptography)
- Visualization (plotly)
- Utilities (PyYAML, tabulate, tenacity, psutil, marshmallow)

### Development Dependencies
- Testing (pytest, pytest-cov, coverage)
- Code Quality (mypy, pylint, ruff)
- Profiling (line-profiler, py-spy)
- Types (various `types-*` packages)

## Deployment

### Production Considerations
1. **Change default passwords** in environment files
2. **Use external database** for better performance and reliability
3. **Configure reverse proxy** (nginx/Apache) for SSL/TLS
4. **Set up monitoring** and logging
5. **Configure backup strategy** for database

### Scaling Options
- **Multiple capture services** for high-throughput networks
- **Database clustering** for large datasets
- **Load balancing** for web interface
- **Message queue** for async processing

---

**Last Updated**: October 2025
**Project Status**: Active Development
**Main Issues**: Tier B Pipeline refactoring, Live Topography fixes, Performance optimization
