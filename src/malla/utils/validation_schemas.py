"""
Marshmallow validation schemas for API endpoints.
"""

from typing import Any, Dict
from marshmallow import Schema, fields, validate, validates_schema, ValidationError


class PacketFilterSchema(Schema):
    """Schema for packet filtering parameters."""

    limit = fields.Int(
        validate=validate.Range(min=1, max=1000),
        load_default=100
    )
    page = fields.Int(
        validate=validate.Range(min=1),
        load_default=1
    )
    gateway_id = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True
    )
    from_node = fields.Int(
        validate=validate.Range(min=0),
        allow_none=True
    )
    to_node = fields.Int(
        validate=validate.Range(min=0),
        allow_none=True
    )
    portnum = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True
    )
    min_rssi = fields.Int(
        validate=validate.Range(min=-200, max=0),
        allow_none=True
    )
    max_rssi = fields.Int(
        validate=validate.Range(min=-200, max=0),
        allow_none=True
    )
    hop_count = fields.Int(
        validate=validate.Range(min=0, max=10),
        allow_none=True
    )
    start_time = fields.DateTime(
        allow_none=True
    )
    end_time = fields.DateTime(
        allow_none=True
    )

    @validates_schema
    def validate_time_range(self, data: Dict[str, Any], **kwargs: Any) -> None:
        """Validate that start_time is before end_time."""
        start_time = data.get('start_time')
        end_time = data.get('end_time')

        if start_time and end_time and start_time >= end_time:
            raise ValidationError("start_time must be before end_time")


class NodeFilterSchema(Schema):
    """Schema for node filtering parameters."""

    limit = fields.Int(
        validate=validate.Range(min=1, max=1000),
        load_default=100
    )
    page = fields.Int(
        validate=validate.Range(min=1),
        load_default=1
    )
    search = fields.Str(
        validate=validate.Length(max=100),
        allow_none=True
    )
    hw_model = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True
    )
    role = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True
    )
    primary_channel = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True
    )


class TracerouteFilterSchema(Schema):
    """Schema for traceroute filtering parameters."""

    limit = fields.Int(
        validate=validate.Range(min=1, max=1000),
        load_default=100
    )
    page = fields.Int(
        validate=validate.Range(min=1),
        load_default=1
    )
    gateway_id = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True
    )
    from_node = fields.Int(
        validate=validate.Range(min=0),
        allow_none=True
    )
    to_node = fields.Int(
        validate=validate.Range(min=0),
        allow_none=True
    )
    success_only = fields.Bool(
        allow_none=True
    )
    return_path_only = fields.Bool(
        allow_none=True
    )
    route_node = fields.Int(
        validate=validate.Range(min=0),
        allow_none=True
    )


class AnalyticsFilterSchema(Schema):
    """Schema for analytics filtering parameters."""

    gateway_id = fields.Str(
        validate=validate.Length(max=50),
        allow_none=True
    )
    from_node = fields.Int(
        validate=validate.Range(min=0),
        allow_none=True
    )
    hop_count = fields.Int(
        validate=validate.Range(min=0, max=10),
        allow_none=True
    )
    hours = fields.Int(
        validate=validate.Range(min=1, max=168),  # Max 7 days
        load_default=24
    )


class HealthCheckSchema(Schema):
    """Schema for health check parameters."""

    detailed = fields.Bool(
        load_default=False
    )
    timeout = fields.Int(
        validate=validate.Range(min=1, max=30),
        load_default=5
    )
