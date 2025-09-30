"""
Marshmallow validation schemas for API endpoints.
"""

from marshmallow import Schema, fields, validate, validates_schema, ValidationError


class PacketFilterSchema(Schema):
    """Schema for packet filtering parameters."""

    limit = fields.Int(
        validate=validate.Range(min=1, max=1000),
        missing=100,
        description="Number of packets to return"
    )
    page = fields.Int(
        validate=validate.Range(min=1),
        missing=1,
        description="Page number"
    )
    gateway_id = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True,
        description="Gateway ID filter"
    )
    from_node = fields.Int(
        validate=validate.Range(min=0),
        allow_none=True,
        description="Source node ID"
    )
    to_node = fields.Int(
        validate=validate.Range(min=0),
        allow_none=True,
        description="Destination node ID"
    )
    portnum = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True,
        description="Port number filter"
    )
    min_rssi = fields.Int(
        validate=validate.Range(min=-200, max=0),
        allow_none=True,
        description="Minimum RSSI value"
    )
    max_rssi = fields.Int(
        validate=validate.Range(min=-200, max=0),
        allow_none=True,
        description="Maximum RSSI value"
    )
    hop_count = fields.Int(
        validate=validate.Range(min=0, max=10),
        allow_none=True,
        description="Hop count filter"
    )
    start_time = fields.DateTime(
        allow_none=True,
        description="Start time filter"
    )
    end_time = fields.DateTime(
        allow_none=True,
        description="End time filter"
    )

    @validates_schema
    def validate_time_range(self, data, **kwargs):
        """Validate that start_time is before end_time."""
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        if start_time and end_time and start_time >= end_time:
            raise ValidationError("start_time must be before end_time")


class NodeFilterSchema(Schema):
    """Schema for node filtering parameters."""

    limit = fields.Int(
        validate=validate.Range(min=1, max=1000),
        missing=100,
        description="Number of nodes to return"
    )
    page = fields.Int(
        validate=validate.Range(min=1),
        missing=1,
        description="Page number"
    )
    search = fields.Str(
        validate=validate.Length(max=100),
        allow_none=True,
        description="Search term"
    )
    hw_model = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True,
        description="Hardware model filter"
    )
    role = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True,
        description="Node role filter"
    )
    primary_channel = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True,
        description="Primary channel filter"
    )


class TracerouteFilterSchema(Schema):
    """Schema for traceroute filtering parameters."""

    limit = fields.Int(
        validate=validate.Range(min=1, max=1000),
        missing=100,
        description="Number of traceroutes to return"
    )
    page = fields.Int(
        validate=validate.Range(min=1),
        missing=1,
        description="Page number"
    )
    gateway_id = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True,
        description="Gateway ID filter"
    )
    from_node = fields.Int(
        validate=validate.Range(min=0),
        allow_none=True,
        description="Source node ID"
    )
    to_node = fields.Int(
        validate=validate.Range(min=0),
        allow_none=True,
        description="Destination node ID"
    )
    success_only = fields.Bool(
        allow_none=True,
        description="Filter for successful traceroutes only"
    )
    return_path_only = fields.Bool(
        allow_none=True,
        description="Filter for traceroutes with return path only"
    )
    route_node = fields.Int(
        validate=validate.Range(min=0),
        allow_none=True,
        description="Filter by route node ID"
    )


class AnalyticsFilterSchema(Schema):
    """Schema for analytics filtering parameters."""

    gateway_id = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True,
        description="Gateway ID filter"
    )
    from_node = fields.Int(
        validate=validate.Range(min=0),
        allow_none=True,
        description="Source node ID"
    )
    hop_count = fields.Int(
        validate=validate.Range(min=0, max=10),
        allow_none=True,
        description="Hop count filter"
    )
    hours = fields.Int(
        validate=validate.Range(min=1, max=168),  # Max 7 days
        missing=24,
        description="Time range in hours"
    )


class HealthCheckSchema(Schema):
    """Schema for health check parameters."""

    detailed = fields.Bool(
        missing=False,
        description="Include detailed health information"
    )
    timeout = fields.Int(
        validate=validate.Range(min=1, max=30),
        missing=5,
        description="Health check timeout in seconds"
    )
