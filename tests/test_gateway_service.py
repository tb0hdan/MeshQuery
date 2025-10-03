"""Tests for gateway service."""

import pytest
import time
from unittest.mock import Mock, patch
from src.malla.services.gateway_service import GatewayService


class TestGatewayService:
    """Test cases for GatewayService class."""

    def setup_method(self):
        """Clear cache before each test."""
        GatewayService._cache.clear()

    @patch('src.malla.services.gateway_service.time.time')
    @patch('src.malla.services.gateway_service.get_db_adapter')
    def test_get_gateway_statistics_success(self, mock_get_db_adapter, mock_time):
        """Test successful gateway statistics retrieval."""
        mock_time.return_value = 1000.0

        # Mock database adapter
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db

        # Mock database query results - need both fetchone and fetchall
        mock_db.fetchone.side_effect = [
            {"total_gateways": 3},  # First fetchone for total gateways count
            {"nodes_with_gateways": 250}  # Second fetchone for nodes with gateway counts
        ]

        mock_db.fetchall.return_value = [  # Gateway distribution query
            {
                "gateway_id": "gateway1",
                "packet_count": 500,
                "unique_sources": 10,
                "avg_rssi": -80.5,
                "avg_snr": 5.2,
                "last_seen": 1000.0
            },
            {
                "gateway_id": "gateway2",
                "packet_count": 300,
                "unique_sources": 8,
                "avg_rssi": -85.0,
                "avg_snr": 3.8,
                "last_seen": 950.0
            },
            {
                "gateway_id": "Unknown",
                "packet_count": 100,
                "unique_sources": 5,
                "avg_rssi": -90.0,
                "avg_snr": 2.1,
                "last_seen": 900.0
            }
        ]

        result = GatewayService.get_gateway_statistics(hours=24)

        # Verify database calls
        assert mock_db.execute.call_count == 3  # 3 queries: total gateways, distribution, nodes with gateways
        assert mock_db.fetchone.call_count == 2  # 2 fetchone calls
        assert mock_db.fetchall.call_count == 1  # 1 fetchall call

        # Verify result structure
        assert result["total_gateways"] == 3
        assert len(result["gateway_distribution"]) == 3
        assert result["nodes_with_gateway_counts"] == 250

        # Verify gateway distribution data
        gw1_data = next(gw for gw in result["gateway_distribution"] if gw["gateway_id"] == "gateway1")
        assert gw1_data["packet_count"] == 500
        assert gw1_data["unique_sources"] == 10
        assert gw1_data["avg_rssi"] == -80.5

        # Verify diversity score calculation
        assert "gateway_diversity_score" in result
        assert 0 <= result["gateway_diversity_score"] <= 100

    @patch('src.malla.services.gateway_service.time.time')
    @patch('src.malla.services.gateway_service.get_db_adapter')
    def test_get_gateway_statistics_caching(self, mock_get_db_adapter, mock_time):
        """Test that gateway statistics are cached properly."""
        mock_time.return_value = 1000.0

        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db

        mock_db.fetchone.side_effect = [
            {"total_gateways": 1},      # First fetchone
            {"nodes_with_gateways": 50} # Second fetchone
        ]

        mock_db.fetchall.return_value = [  # Gateway distribution
            {
                "gateway_id": "gateway1",
                "packet_count": 100,
                "unique_sources": 5,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            }
        ]

        # First call
        result1 = GatewayService.get_gateway_statistics(hours=24)

        # Second call within cache window
        mock_time.return_value = 1100.0  # 100 seconds later (within TTL)
        result2 = GatewayService.get_gateway_statistics(hours=24)

        # Should be same object (cached)
        assert result1 is result2
        assert mock_db.execute.call_count == 3  # Only called once - 3 queries total

        # Third call outside cache window
        mock_time.return_value = 1400.0  # 400 seconds later (outside TTL)

        # Reset mocks for new call
        mock_db.fetchone.side_effect = [
            {"total_gateways": 1},      # First fetchone
            {"nodes_with_gateways": 75} # Second fetchone
        ]

        mock_db.fetchall.return_value = [  # Different gateway distribution
            {
                "gateway_id": "gateway2",
                "packet_count": 200,
                "unique_sources": 8,
                "avg_rssi": -85.0,
                "avg_snr": 4.0,
                "last_seen": 1400.0
            }
        ]
        result3 = GatewayService.get_gateway_statistics(hours=24)

        # Should be different object (cache miss)
        assert result1 is not result3
        assert mock_db.execute.call_count == 6  # Called again - 6 total (3 + 3)

    @patch('src.malla.services.gateway_service.get_db_adapter')
    def test_get_gateway_statistics_different_hours(self, mock_get_db_adapter):
        """Test that different hours parameter creates different cache entries."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db

        # Mock for first call (24h)
        call_count = 0
        def fetchone_side_effect(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"total_gateways": 1}
            elif call_count == 2:
                return {"nodes_with_gateways": 50}
            elif call_count == 3:
                return {"total_gateways": 1}
            else:
                return {"nodes_with_gateways": 60}

        mock_db.fetchone.side_effect = fetchone_side_effect

        fetchall_call_count = 0
        def fetchall_side_effect(*args):
            nonlocal fetchall_call_count
            fetchall_call_count += 1
            if fetchall_call_count == 1:
                return [{"gateway_id": "gateway1", "packet_count": 100, "unique_sources": 5, "avg_rssi": -80.0, "avg_snr": 5.0, "last_seen": 1000.0}]
            else:
                return [{"gateway_id": "gateway2", "packet_count": 150, "unique_sources": 8, "avg_rssi": -85.0, "avg_snr": 4.0, "last_seen": 1100.0}]

        mock_db.fetchall.side_effect = fetchall_side_effect

        # Different hours should create different cache entries
        result_24h = GatewayService.get_gateway_statistics(hours=24)
        result_48h = GatewayService.get_gateway_statistics(hours=48)

        assert result_24h is not result_48h
        assert mock_db.execute.call_count == 6  # Both calls executed (3 each)

        # Verify cache has both entries
        assert len(GatewayService._cache) == 2
        assert "gateway_stats_24h" in GatewayService._cache
        assert "gateway_stats_48h" in GatewayService._cache

    @patch('src.malla.services.gateway_service.get_db_adapter')
    def test_get_gateway_statistics_empty_result(self, mock_get_db_adapter):
        """Test gateway statistics with no data."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db

        mock_db.fetchone.side_effect = [
            {"total_gateways": 0},     # No gateways
            {"nodes_with_gateways": 0} # No nodes with gateway counts
        ]

        mock_db.fetchall.return_value = []  # No gateway distribution data

        result = GatewayService.get_gateway_statistics()

        assert result["total_gateways"] == 0
        assert result["gateway_distribution"] == []
        assert result["nodes_with_gateway_counts"] == 0
        assert result["gateway_diversity_score"] == 0

    @patch('src.malla.services.gateway_service.get_db_adapter')
    def test_get_gateway_statistics_diversity_score_calculation(self, mock_get_db_adapter):
        """Test gateway diversity score calculation."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db

        # Test with balanced distribution (high diversity)
        mock_db.fetchone.side_effect = [
            {"total_gateways": 4},     # 4 gateways
            {"nodes_with_gateways": 100} # 100 nodes with gateway counts
        ]

        mock_db.fetchall.return_value = [
            {
                "gateway_id": "gateway1",
                "packet_count": 250,
                "unique_sources": 25,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            },
            {
                "gateway_id": "gateway2",
                "packet_count": 250,
                "unique_sources": 25,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            },
            {
                "gateway_id": "gateway3",
                "packet_count": 250,
                "unique_sources": 25,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            },
            {
                "gateway_id": "gateway4",
                "packet_count": 250,
                "unique_sources": 25,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            }
        ]

        result = GatewayService.get_gateway_statistics()
        high_diversity_score = result["gateway_diversity_score"]

        # Clear cache for next test
        GatewayService._cache.clear()

        # Test with unbalanced distribution (low diversity)
        mock_db.fetchone.side_effect = [
            {"total_gateways": 4},     # 4 gateways
            {"nodes_with_gateways": 100} # 100 nodes with gateway counts
        ]

        mock_db.fetchall.return_value = [
            {
                "gateway_id": "gateway1",
                "packet_count": 950,
                "unique_sources": 95,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            },
            {
                "gateway_id": "gateway2",
                "packet_count": 30,
                "unique_sources": 3,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            },
            {
                "gateway_id": "gateway3",
                "packet_count": 15,
                "unique_sources": 2,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            },
            {
                "gateway_id": "gateway4",
                "packet_count": 5,
                "unique_sources": 1,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            }
        ]

        result = GatewayService.get_gateway_statistics()
        low_diversity_score = result["gateway_diversity_score"]

        # High diversity should have higher score
        assert high_diversity_score > low_diversity_score

    @patch('src.malla.services.gateway_service.get_db_adapter')
    def test_get_gateway_statistics_percentage_calculation(self, mock_get_db_adapter):
        """Test percentage of total calculation."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db

        mock_db.fetchone.side_effect = [
            {"total_gateways": 3},     # 3 gateways
            {"nodes_with_gateways": 50} # 50 nodes with gateway counts
        ]

        mock_db.fetchall.return_value = [
            {
                "gateway_id": "gateway1",
                "packet_count": 600,
                "unique_sources": 30,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            },
            {
                "gateway_id": "gateway2",
                "packet_count": 300,
                "unique_sources": 15,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            },
            {
                "gateway_id": "gateway3",
                "packet_count": 100,
                "unique_sources": 5,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            }
        ]

        result = GatewayService.get_gateway_statistics()

        # Find gateways in result
        gw1 = next(gw for gw in result["gateway_distribution"] if gw["gateway_id"] == "gateway1")
        gw2 = next(gw for gw in result["gateway_distribution"] if gw["gateway_id"] == "gateway2")
        gw3 = next(gw for gw in result["gateway_distribution"] if gw["gateway_id"] == "gateway3")

        # Check percentages (with some tolerance for floating point)
        assert abs(gw1["percentage_of_total"] - 60.0) < 0.1
        assert abs(gw2["percentage_of_total"] - 30.0) < 0.1
        assert abs(gw3["percentage_of_total"] - 10.0) < 0.1

        # Total should add up to 100%
        total_percentage = sum(gw["percentage_of_total"] for gw in result["gateway_distribution"])
        assert abs(total_percentage - 100.0) < 0.1

    @patch('src.malla.services.gateway_service.get_db_adapter')
    @patch('src.malla.services.gateway_service.logger')
    def test_get_gateway_statistics_logging(self, mock_logger, mock_get_db_adapter):
        """Test logging in gateway statistics."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db

        mock_db.fetchone.side_effect = [
            {"total_gateways": 1},     # 1 gateway
            {"nodes_with_gateways": 50} # 50 nodes with gateway counts
        ]

        mock_db.fetchall.return_value = [
            {
                "gateway_id": "gateway1",
                "packet_count": 100,
                "unique_sources": 5,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            }
        ]

        # First call (should log computation)
        GatewayService.get_gateway_statistics(hours=12)

        # Should log computation
        mock_logger.info.assert_called()
        log_message = mock_logger.info.call_args[0][0]
        assert "Gateway statistics computed" in log_message or "Computing gateway statistics" in log_message
        assert "12h" in log_message or "cached" in log_message

        # Second call (should log cache hit)
        mock_logger.reset_mock()
        GatewayService.get_gateway_statistics(hours=12)

        mock_logger.debug.assert_called()
        debug_message = mock_logger.debug.call_args[0][0]
        assert "Returning cached gateway statistics" in debug_message

    @patch('src.malla.services.gateway_service.get_db_adapter')
    def test_get_gateway_statistics_database_error(self, mock_get_db_adapter):
        """Test error handling when database query fails."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db
        mock_db.execute.side_effect = Exception("Database error")

        # Should raise the database exception
        with pytest.raises(Exception, match="Database error"):
            GatewayService.get_gateway_statistics()

    @patch('src.malla.services.gateway_service.get_db_adapter')
    def test_get_gateway_statistics_single_gateway(self, mock_get_db_adapter):
        """Test gateway statistics with single gateway (edge case)."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db

        mock_db.fetchone.side_effect = [
            {"total_gateways": 1},     # 1 gateway
            {"nodes_with_gateways": 100} # 100 nodes with gateway counts
        ]

        mock_db.fetchall.return_value = [
            {
                "gateway_id": "gateway1",
                "packet_count": 1000,
                "unique_sources": 100,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            }
        ]

        result = GatewayService.get_gateway_statistics()

        assert result["total_gateways"] == 1
        assert len(result["gateway_distribution"]) == 1
        assert result["gateway_distribution"][0]["percentage_of_total"] == 100.0
        # Single gateway should have high diversity score (100% even distribution for 1 gateway)
        assert result["gateway_diversity_score"] == 100

    @patch('src.malla.services.gateway_service.get_db_adapter')
    def test_get_gateway_statistics_sql_query_parameters(self, mock_get_db_adapter):
        """Test that SQL queries use correct parameters."""
        mock_db = Mock()
        mock_get_db_adapter.return_value = mock_db

        mock_db.fetchone.side_effect = [
            {"total_gateways": 1},     # 1 gateway
            {"nodes_with_gateways": 50} # 50 nodes with gateway counts
        ]

        mock_db.fetchall.return_value = [
            {
                "gateway_id": "gateway1",
                "packet_count": 100,
                "unique_sources": 10,
                "avg_rssi": -80.0,
                "avg_snr": 5.0,
                "last_seen": 1000.0
            }
        ]

        GatewayService.get_gateway_statistics(hours=48)

        # Verify SQL queries were called with correct time parameter
        execute_calls = mock_db.execute.call_args_list

        # 3 queries should be called with the same time parameter
        assert len(execute_calls) == 3

        # Check that time parameters are passed (should be start and end timestamps)
        for call in execute_calls:
            sql_query, params = call[0]
            assert len(params) == 2  # Should have start and end time parameters
            assert isinstance(params[0], float)  # Should be a timestamp
            assert isinstance(params[1], float)  # Should be a timestamp

    def test_get_gateway_statistics_default_hours(self):
        """Test default hours parameter."""
        with patch('src.malla.services.gateway_service.get_db_adapter') as mock_get_db_adapter:
            mock_db = Mock()
            mock_get_db_adapter.return_value = mock_db
            mock_db.fetchone.side_effect = [
                {"total_gateways": 1},     # 1 gateway
                {"nodes_with_gateways": 50} # 50 nodes with gateway counts
            ]

            mock_db.fetchall.return_value = [
                {
                    "gateway_id": "gateway1",
                    "packet_count": 100,
                    "unique_sources": 10,
                    "avg_rssi": -80.0,
                    "avg_snr": 5.0,
                    "last_seen": 1000.0
                }
            ]

            GatewayService.get_gateway_statistics()  # No hours parameter

            # Should use default of 24 hours
            assert "gateway_stats_24h" in GatewayService._cache