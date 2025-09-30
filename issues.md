# MeshQuery Issues Analysis

## Current Problems Identified

### 1. Longest Links Page Issues
- **Single RF Hops**: Working correctly
- **Complete Paths**: Not working - likely due to missing traceroute data or incorrect data processing

### 2. Network Graph Live Animations Issues
- **Root Cause**: Database schema mismatch
- **Specific Error**: `column "hop_count" does not exist` in `packet_history` table
- **Impact**: Live stream route fails to fetch packet data, breaking animations

### 3. Database Schema Problems
- **Missing Columns**: The `hop_count` column referenced in stream_routes.py doesn't exist
- **Schema Mismatch**: Code expects columns that aren't in the actual database schema
- **Data Processing**: Incomplete data flow from MQTT capture to web UI

### 4. Stream Route Issues
- **File**: `src/malla/routes/stream_routes.py`
- **Problem**: Query references non-existent `hop_count` column
- **Impact**: Live animations completely broken
- **Error Pattern**: Continuous warnings every 250ms

### 5. MQTT Capture Issues
- **Connection Stability**: Frequent disconnections from MQTT broker
- **Data Processing**: May not be properly storing all required fields
- **Schema Alignment**: Captured data may not match expected database schema

## Technical Analysis

### Database Schema Issues
1. **Missing hop_count column** in packet_history table
2. **Incomplete schema** for traceroute data processing
3. **Data type mismatches** between capture and display

### Code Architecture Issues
1. **Stream route** assumes database schema that doesn't exist
2. **Longest links analysis** may have incomplete traceroute processing
3. **Live animations** depend on stream route that's failing

### Data Flow Problems
1. **MQTT → Database**: May not be capturing all required fields
2. **Database → Stream**: Schema mismatch preventing data retrieval
3. **Stream → UI**: No data reaching frontend for animations

## Impact Assessment
- **High**: Live animations completely non-functional
- **Medium**: Longest links complete paths not working
- **Low**: Single RF hops working correctly

## Files Requiring Investigation
- `src/malla/routes/stream_routes.py` - Stream route with schema issues
- `src/malla/database/schema_tier_b.py` - Database schema definition
- `src/malla/services/traceroute_service.py` - Longest links processing
- `src/malla/mqtt_capture.py` - Data capture and storage
- Database schema files and migration scripts

## Next Steps Required
1. Analyze complete database schema requirements
2. Fix stream route database queries
3. Ensure MQTT capture stores all required fields
4. Fix longest links complete paths processing
5. Test end-to-end data flow
