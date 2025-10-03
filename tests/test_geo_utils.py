"""Tests for geo_utils module."""

import pytest
import math
from src.malla.utils.geo_utils import calculate_distance, calculate_bearing


class TestCalculateDistance:
    """Test cases for calculate_distance function."""

    def test_same_point(self):
        """Test distance between same point is zero."""
        distance = calculate_distance(40.7128, -74.0060, 40.7128, -74.0060)
        assert distance == 0.0

    def test_known_distances(self):
        """Test known distances between major cities."""
        # NYC to LA (approximately 3944 km)
        nyc_lat, nyc_lon = 40.7128, -74.0060
        la_lat, la_lon = 34.0522, -118.2437
        distance = calculate_distance(nyc_lat, nyc_lon, la_lat, la_lon)
        assert 3900 < distance < 4000  # Allow some tolerance

        # London to Paris (approximately 344 km)
        london_lat, london_lon = 51.5074, -0.1278
        paris_lat, paris_lon = 48.8566, 2.3522
        distance = calculate_distance(london_lat, london_lon, paris_lat, paris_lon)
        assert 340 < distance < 350

    def test_antipodal_points(self):
        """Test distance between antipodal points (opposite sides of Earth)."""
        # Approximately half Earth's circumference (about 20,003 km)
        distance = calculate_distance(0, 0, 0, 180)
        assert 19900 < distance < 20100

    def test_edge_cases(self):
        """Test edge cases with extreme coordinates."""
        # North pole to South pole
        distance = calculate_distance(90, 0, -90, 0)
        assert 19900 < distance < 20100

        # Points on equator
        distance = calculate_distance(0, 0, 0, 90)
        assert 9900 < distance < 10100

    def test_negative_coordinates(self):
        """Test with negative coordinates."""
        distance = calculate_distance(-40.7128, -74.0060, -34.0522, -118.2437)
        assert distance > 0


class TestCalculateBearing:
    """Test cases for calculate_bearing function."""

    def test_same_point(self):
        """Test bearing from same point returns 0."""
        bearing = calculate_bearing(40.7128, -74.0060, 40.7128, -74.0060)
        assert bearing == 0.0

    def test_cardinal_directions(self):
        """Test bearings for cardinal directions."""
        # Due North
        bearing = calculate_bearing(0, 0, 1, 0)
        assert abs(bearing - 0) < 1  # Should be close to 0 degrees

        # Due East
        bearing = calculate_bearing(0, 0, 0, 1)
        assert abs(bearing - 90) < 1  # Should be close to 90 degrees

        # Due South
        bearing = calculate_bearing(1, 0, 0, 0)
        assert abs(bearing - 180) < 1  # Should be close to 180 degrees

        # Due West
        bearing = calculate_bearing(0, 1, 0, 0)
        assert abs(bearing - 270) < 1  # Should be close to 270 degrees

    def test_bearing_range(self):
        """Test that bearing is always in 0-360 range."""
        bearing = calculate_bearing(-40, -100, 40, 100)
        assert 0 <= bearing < 360

    def test_known_bearings(self):
        """Test known bearings between cities."""
        # NYC to LA should be roughly west/southwest (around 270-280 degrees)
        bearing = calculate_bearing(40.7128, -74.0060, 34.0522, -118.2437)
        assert 260 < bearing < 290

    def test_across_dateline(self):
        """Test bearing calculation across international date line."""
        # From just west of dateline to just east
        bearing = calculate_bearing(0, 179, 0, -179)
        assert 80 < bearing < 100  # Should be roughly east

    def test_polar_regions(self):
        """Test bearings near poles."""
        bearing = calculate_bearing(89, 0, 89, 90)
        assert 0 <= bearing < 360