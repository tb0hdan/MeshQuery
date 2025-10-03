"""Tests for analytics service."""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock
from src.malla.services.analytics_service import AnalyticsService


class TestAnalyticsService:
    """Test cases for AnalyticsService class."""

    def setup_method(self):
        """Clear cache before each test."""
        AnalyticsService._CACHE.clear()

    @patch('src.malla.services.analytics_service.time.time')
    @patch.object(AnalyticsService, '_get_packet_statistics')
    @patch.object(AnalyticsService, '_get_node_activity_statistics')
    @patch.object(AnalyticsService, '_get_signal_quality_statistics')
    @patch.object(AnalyticsService, '_get_temporal_patterns')
    @patch.object(AnalyticsService, '_get_top_active_nodes')
    @patch.object(AnalyticsService, '_get_packet_type_distribution')
    @patch.object(AnalyticsService, '_get_gateway_distribution')
    def test_get_analytics_data_success(self, mock_gateway, mock_packet_types, mock_top_nodes,
                                      mock_temporal, mock_signal, mock_node_activity,
                                      mock_packet_stats, mock_time):
        """Test successful analytics data retrieval."""
        mock_time.return_value = 1000.0

        # Setup mock returns
        mock_packet_stats.return_value = {"total_packets": 100}
        mock_node_activity.return_value = {"active_nodes": 50}
        mock_signal.return_value = {"avg_rssi": -85.0}
        mock_temporal.return_value = {"peak_hour": 14}
        mock_top_nodes.return_value = [{"node_id": 123}]
        mock_packet_types.return_value = [{"portnum_name": "TEXT_MESSAGE_APP"}]
        mock_gateway.return_value = [{"gateway_id": "gateway1"}]

        result = AnalyticsService.get_analytics_data(
            gateway_id="test_gateway",
            from_node=123,
            hop_count=2
        )

        # Verify all methods called with correct parameters
        filters = {"gateway_id": "test_gateway", "from_node": 123, "hop_count": 2}
        twenty_four_hours_ago = 1000.0 - 24 * 3600
        seven_days_ago = 1000.0 - 7 * 24 * 3600

        mock_packet_stats.assert_called_once_with(filters, twenty_four_hours_ago)
        mock_node_activity.assert_called_once_with(filters, twenty_four_hours_ago)
        mock_signal.assert_called_once_with(filters, twenty_four_hours_ago)
        mock_temporal.assert_called_once_with(filters, twenty_four_hours_ago)
        mock_top_nodes.assert_called_once_with(filters, seven_days_ago)
        mock_packet_types.assert_called_once_with(filters, twenty_four_hours_ago)
        mock_gateway.assert_called_once_with(filters, twenty_four_hours_ago)

        # Verify result structure
        assert "packet_statistics" in result
        assert "node_statistics" in result
        assert "signal_quality" in result
        assert "temporal_patterns" in result
        assert "top_nodes" in result
        assert "packet_types" in result
        assert "gateway_distribution" in result

    @patch('src.malla.services.analytics_service.time.time')
    def test_get_analytics_data_caching(self, mock_time):
        """Test that analytics data is cached properly."""
        mock_time.return_value = 1000.0

        # Mock all the private methods
        with patch.object(AnalyticsService, '_get_packet_statistics', return_value={"total": 1}), \
             patch.object(AnalyticsService, '_get_node_activity_statistics', return_value={"active": 1}), \
             patch.object(AnalyticsService, '_get_signal_quality_statistics', return_value={"rssi": -80}), \
             patch.object(AnalyticsService, '_get_temporal_patterns', return_value={"hour": 12}), \
             patch.object(AnalyticsService, '_get_top_active_nodes', return_value=[]), \
             patch.object(AnalyticsService, '_get_packet_type_distribution', return_value=[]), \
             patch.object(AnalyticsService, '_get_gateway_distribution', return_value=[]):

            # First call
            result1 = AnalyticsService.get_analytics_data(gateway_id="test")

            # Second call within cache window
            mock_time.return_value = 1030.0  # 30 seconds later
            result2 = AnalyticsService.get_analytics_data(gateway_id="test")

            # Should be same object (cached)
            assert result1 is result2

            # Third call outside cache window
            mock_time.return_value = 1100.0  # 100 seconds later (outside TTL)
            result3 = AnalyticsService.get_analytics_data(gateway_id="test")

            # Should be different object (cache miss)
            assert result1 is not result3

    def test_get_analytics_data_no_filters(self):
        """Test analytics data with no filters."""
        with patch.object(AnalyticsService, '_get_packet_statistics', return_value={"total": 1}), \
             patch.object(AnalyticsService, '_get_node_activity_statistics', return_value={"active": 1}), \
             patch.object(AnalyticsService, '_get_signal_quality_statistics', return_value={"rssi": -80}), \
             patch.object(AnalyticsService, '_get_temporal_patterns', return_value={"hour": 12}), \
             patch.object(AnalyticsService, '_get_top_active_nodes', return_value=[]), \
             patch.object(AnalyticsService, '_get_packet_type_distribution', return_value=[]), \
             patch.object(AnalyticsService, '_get_gateway_distribution', return_value=[]):

            result = AnalyticsService.get_analytics_data()
            assert isinstance(result, dict)

    @patch('src.malla.database.adapter.get_db_adapter')
    def test_get_packet_statistics(self, mock_get_db_adapter):
        """Test packet statistics calculation."""
        # Create a complete mock adapter that doesn't try to connect to database
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db

        # Mock all database adapter methods
        mock_db.execute.return_value = None
        mock_db.fetchone.return_value = {
            "total_packets": 1000,
            "successful_packets": 950,
            "avg_payload_size": 32.5
        }
        mock_db.close.return_value = None
        mock_db.ensure_open.return_value = None
        mock_db.get_connection.return_value = None
        mock_db.get_cursor.return_value = None

        filters = {"gateway_id": "test_gateway"}
        since_timestamp = 1000.0

        result = AnalyticsService._get_packet_statistics(filters, since_timestamp)

        # Verify execute and close were called
        mock_db.execute.assert_called_once()
        mock_db.close.assert_called_once()

        assert result["total_packets"] == 1000
        assert result["successful_packets"] == 950
        assert result["failed_packets"] == 50
        assert result["success_rate"] == 95.0
        assert result["average_payload_size"] == 32.5

    @patch('src.malla.database.adapter.get_db_adapter')
    def test_get_packet_statistics_zero_packets(self, mock_get_db_adapter):
        """Test packet statistics with zero packets."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db

        mock_db.execute.return_value = None
        mock_db.fetchone.return_value = {
            "total_packets": 0,
            "successful_packets": 0,
            "avg_payload_size": None
        }
        mock_db.close.return_value = None

        result = AnalyticsService._get_packet_statistics({}, 1000.0)

        mock_db.execute.assert_called_once()
        mock_db.close.assert_called_once()

        assert result["total_packets"] == 0
        assert result["success_rate"] == 0
        assert result["average_payload_size"] == 0

    @patch('src.malla.database.adapter.get_db_adapter')
    def test_get_node_activity_statistics(self, mock_get_db_adapter):
        """Test node activity statistics calculation."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db

        # Mock database methods
        mock_db.execute.return_value = None
        # Mock the two database calls
        mock_db.fetchone.side_effect = [
            {"total_nodes": 100},  # First call for total nodes
            {  # Second call for activity breakdown
                "active_nodes": 75,
                "very_active": 10,
                "moderately_active": 25,
                "lightly_active": 40
            }
        ]
        mock_db.close.return_value = None

        result = AnalyticsService._get_node_activity_statistics({}, 1000.0)

        # Verify database calls
        assert mock_db.execute.call_count == 2
        mock_db.close.assert_called_once()

        assert result["total_nodes"] == 100
        assert result["active_nodes"] == 75
        assert result["inactive_nodes"] == 25
        assert result["activity_rate"] == 75.0
        assert result["activity_distribution"]["very_active"] == 10
        assert result["activity_distribution"]["inactive"] == 25

    @patch('src.malla.services.analytics_service.get_db_adapter')
    def test_get_signal_quality_statistics(self, mock_get_db_adapter):
        """Test signal quality statistics calculation."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db
        mock_db.fetchone.return_value = {
            "avg_rssi": -85.5,
            "avg_snr": 8.2,
            "rssi_count": 1000,
            "snr_count": 950,
            "rssi_excellent": 100,
            "rssi_good": 300,
            "rssi_fair": 400,
            "rssi_poor": 200,
            "snr_excellent": 200,
            "snr_good": 300,
            "snr_fair": 250,
            "snr_poor": 200
        }

        result = AnalyticsService._get_signal_quality_statistics({}, 1000.0)

        assert result["avg_rssi"] == -85.5
        assert result["avg_snr"] == 8.2
        assert result["total_measurements"] == 1000
        assert result["rssi_distribution"]["excellent"] == 100
        assert result["snr_distribution"]["poor"] == 200

    @patch('src.malla.services.analytics_service.get_db_adapter')
    def test_get_signal_quality_statistics_no_data(self, mock_get_db_adapter):
        """Test signal quality statistics with no data."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db
        mock_db.fetchone.return_value = {
            "avg_rssi": None,
            "avg_snr": None,
            "rssi_count": 0,
            "snr_count": 0,
            "rssi_excellent": 0,
            "rssi_good": 0,
            "rssi_fair": 0,
            "rssi_poor": 0,
            "snr_excellent": 0,
            "snr_good": 0,
            "snr_fair": 0,
            "snr_poor": 0
        }

        result = AnalyticsService._get_signal_quality_statistics({}, 1000.0)

        assert result["avg_rssi"] is None
        assert result["avg_snr"] is None
        assert result["total_measurements"] == 0
        assert result["rssi_distribution"] == {}
        assert result["snr_distribution"] == {}

    @patch('src.malla.services.analytics_service.get_db_adapter')
    def test_get_temporal_patterns(self, mock_get_db_adapter):
        """Test temporal patterns calculation."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db
        mock_db.fetchall.return_value = [
            {"hour": 8, "total_packets": 100, "successful_packets": 95},
            {"hour": 14, "total_packets": 200, "successful_packets": 180},
            {"hour": 20, "total_packets": 50, "successful_packets": 45}
        ]

        result = AnalyticsService._get_temporal_patterns({}, 1000.0)

        assert len(result["hourly_breakdown"]) == 24
        assert result["peak_hour"] == 14  # Hour with most packets
        assert result["quiet_hour"] == 20   # Hour with least packets among reported hours

        # Check specific hour data
        hour_14_data = next(h for h in result["hourly_breakdown"] if h["hour"] == 14)
        assert hour_14_data["total_packets"] == 200
        assert hour_14_data["success_rate"] == 90.0

    @patch('src.malla.services.analytics_service.NodeRepository.get_nodes')
    def test_get_top_active_nodes(self, mock_get_nodes):
        """Test top active nodes retrieval."""
        mock_get_nodes.return_value = {
            "nodes": [
                {
                    "node_id": 123,
                    "long_name": "Active Node 1",
                    "short_name": "AN1",
                    "packet_count_24h": 500,
                    "avg_rssi": -75.0,
                    "avg_snr": 10.5,
                    "last_packet_time": 1234567890.0,
                    "hw_model": "HELTEC_V3"
                },
                {
                    "node_id": 456,
                    "long_name": None,
                    "short_name": "AN2",
                    "packet_count_24h": 300,
                    "avg_rssi": -82.0,
                    "avg_snr": 8.2,
                    "last_packet_time": 1234567800.0,
                    "hw_model": "TBEAM"
                },
                {
                    "node_id": 789,
                    "long_name": None,
                    "short_name": None,
                    "packet_count_24h": 0  # Inactive node
                }
            ]
        }

        result = AnalyticsService._get_top_active_nodes({}, 1000.0)

        # Should only return active nodes (packet_count_24h > 0)
        assert len(result) == 2
        assert result[0]["node_id"] == 123
        assert result[0]["display_name"] == "Active Node 1"
        assert result[1]["display_name"] == "AN2"

    @patch('src.malla.services.analytics_service.get_db_adapter')
    def test_get_packet_type_distribution(self, mock_get_db_adapter):
        """Test packet type distribution calculation."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db
        mock_db.fetchall.return_value = [
            {"portnum_name": "TEXT_MESSAGE_APP", "count": 500, "percentage": 50.0},
            {"portnum_name": "POSITION_APP", "count": 300, "percentage": 30.0},
            {"portnum_name": "NODEINFO_APP", "count": 200, "percentage": 20.0}
        ]

        result = AnalyticsService._get_packet_type_distribution({}, 1000.0)

        assert len(result) == 3
        assert result[0]["portnum_name"] == "TEXT_MESSAGE_APP"
        assert result[0]["count"] == 500
        assert result[0]["percentage"] == 50.0

    @patch('src.malla.services.analytics_service.get_db_adapter')
    def test_get_gateway_distribution(self, mock_get_db_adapter):
        """Test gateway distribution calculation."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db
        mock_db.fetchall.return_value = [
            {
                "gateway_id": "gateway1",
                "total_packets": 600,
                "successful_packets": 570,
                "success_rate": 95.0,
                "percentage_of_total": 60.0
            },
            {
                "gateway_id": "gateway2",
                "total_packets": 400,
                "successful_packets": 360,
                "success_rate": 90.0,
                "percentage_of_total": 40.0
            }
        ]

        result = AnalyticsService._get_gateway_distribution({}, 1000.0)

        assert len(result) == 2
        assert result[0]["gateway_id"] == "gateway1"
        assert result[0]["success_rate"] == 95.0
        assert result[1]["percentage_of_total"] == 40.0

    @patch('src.malla.services.analytics_service.logger')
    def test_get_analytics_data_error_handling(self, mock_logger):
        """Test error handling in get_analytics_data."""
        with patch.object(AnalyticsService, '_get_packet_statistics', side_effect=Exception("DB Error")):
            with pytest.raises(Exception, match="DB Error"):
                AnalyticsService.get_analytics_data()

            mock_logger.error.assert_called_once()

    def test_cache_key_generation(self):
        """Test that different parameters generate different cache keys."""
        # Clear cache
        AnalyticsService._CACHE.clear()

        with patch.object(AnalyticsService, '_get_packet_statistics', return_value={"total": 1}), \
             patch.object(AnalyticsService, '_get_node_activity_statistics', return_value={"active": 1}), \
             patch.object(AnalyticsService, '_get_signal_quality_statistics', return_value={"rssi": -80}), \
             patch.object(AnalyticsService, '_get_temporal_patterns', return_value={"hour": 12}), \
             patch.object(AnalyticsService, '_get_top_active_nodes', return_value=[]), \
             patch.object(AnalyticsService, '_get_packet_type_distribution', return_value=[]), \
             patch.object(AnalyticsService, '_get_gateway_distribution', return_value=[]):

            # Different parameters should create different cache entries
            AnalyticsService.get_analytics_data(gateway_id="gw1")
            AnalyticsService.get_analytics_data(gateway_id="gw2")
            AnalyticsService.get_analytics_data(from_node=123)

            # Should have 3 cache entries
            assert len(AnalyticsService._CACHE) == 3