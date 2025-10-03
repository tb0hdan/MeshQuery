"""Tests for node service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.malla.services.node_service import NodeService, NodeNotFoundError


class TestNodeService:
    """Test cases for NodeService class."""

    @patch('src.malla.services.node_service.convert_node_id')
    @patch('src.malla.services.node_service.NodeRepository.get_node_details')
    @patch('src.malla.services.node_service.TracerouteService.get_node_traceroute_stats')
    @patch('src.malla.services.node_service.LocationService.get_node_location_history')
    @patch('src.malla.services.node_service.LocationService.get_node_neighbors')
    def test_get_node_info_success(self, mock_neighbors, mock_history, mock_stats, mock_details, mock_convert):
        """Test successful node info retrieval."""
        # Setup mocks
        mock_convert.return_value = 123456789
        mock_details.return_value = {
            "node": {
                "node_id": 123456789,
                "long_name": "Test Node",
                "short_name": "TEST"
            }
        }
        mock_stats.return_value = {"total_traceroutes": 5}
        mock_history.return_value = [{"timestamp": 1234567890.0}]
        mock_neighbors.return_value = [{"node_id": 987654321}]

        # Test
        result = NodeService.get_node_info("!075bcd15")

        # Assertions
        mock_convert.assert_called_once_with("!075bcd15")
        mock_details.assert_called_once_with(123456789)
        mock_stats.assert_called_once_with(123456789)
        mock_history.assert_called_once_with(123456789, limit=10)
        mock_neighbors.assert_called_once_with(123456789, max_distance_km=10.0)

        assert result["node"]["node_id"] == 123456789
        assert result["traceroute_stats"]["total_traceroutes"] == 5
        assert len(result["location_history"]) == 1
        assert len(result["neighbors"]) == 1

    @patch('src.malla.services.node_service.convert_node_id')
    @patch('src.malla.services.node_service.NodeRepository.get_node_details')
    def test_get_node_info_not_found(self, mock_details, mock_convert):
        """Test node not found error."""
        mock_convert.return_value = 123456789
        mock_details.return_value = None

        with pytest.raises(NodeNotFoundError, match="Node not found"):
            NodeService.get_node_info("!075bcd15")

    @patch('src.malla.services.node_service.convert_node_id')
    def test_get_node_info_invalid_id(self, mock_convert):
        """Test invalid node ID handling."""
        mock_convert.side_effect = ValueError("Invalid node ID")

        with pytest.raises(ValueError):
            NodeService.get_node_info("invalid")

    @patch('src.malla.services.node_service.convert_node_id')
    @patch('src.malla.services.node_service.LocationService.get_node_location_history')
    def test_get_node_location_history(self, mock_history, mock_convert):
        """Test node location history retrieval."""
        mock_convert.return_value = 123456789
        mock_history.return_value = [
            {"timestamp": 1234567890.0, "latitude": 40.7128, "longitude": -74.0060}
        ]

        result = NodeService.get_node_location_history("!075bcd15", limit=50)

        mock_convert.assert_called_once_with("!075bcd15")
        mock_history.assert_called_once_with(123456789, limit=50)
        assert result["node_id"] == 123456789
        assert len(result["location_history"]) == 1

    @patch('src.malla.services.node_service.convert_node_id')
    @patch('src.malla.services.node_service.LocationService.get_node_neighbors')
    def test_get_node_neighbors(self, mock_neighbors, mock_convert):
        """Test node neighbors retrieval."""
        mock_convert.return_value = 123456789
        mock_neighbors.return_value = [
            {"node_id": 987654321, "distance_km": 5.2},
            {"node_id": 111222333, "distance_km": 8.7}
        ]

        result = NodeService.get_node_neighbors("!075bcd15", max_distance=15.0)

        mock_convert.assert_called_once_with("!075bcd15")
        mock_neighbors.assert_called_once_with(123456789, max_distance_km=15.0)
        assert result["node_id"] == 123456789
        assert result["max_distance_km"] == 15.0
        assert result["neighbor_count"] == 2
        assert len(result["neighbors"]) == 2

    @patch('src.malla.services.node_service.convert_node_id')
    @patch('src.malla.database.get_db_connection')
    def test_get_traceroute_related_nodes(self, mock_db_conn, mock_convert):
        """Test traceroute related nodes retrieval."""
        mock_convert.return_value = 123456789

        # Mock database connection and cursor
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock packet data
        mock_cursor.fetchall.side_effect = [
            [  # First query - packets
                (
                    "packet1", 1234567890.0, 123456789, 987654321, "gateway1",
                    3, 3, b"mock_payload"
                )
            ],
            [  # Second query - node info
                (987654321, "Related Node", "REL", "!3ade68b1")
            ]
        ]

        # Mock TraceroutePacket
        with patch('src.malla.models.traceroute.TraceroutePacket') as mock_tr_packet:
            mock_tr_instance = Mock()
            mock_tr_packet.return_value = mock_tr_instance
            mock_tr_instance.get_rf_hops.return_value = [
                Mock(from_node_id=123456789, to_node_id=987654321)
            ]

            result = NodeService.get_traceroute_related_nodes("!075bcd15")

        assert result["node_id"] == 123456789
        assert result["total_count"] == 1
        assert len(result["related_nodes"]) == 1
        assert result["related_nodes"][0]["node_id"] == 987654321
        assert result["related_nodes"][0]["traceroute_count"] == 1

    @patch('src.malla.services.node_service.convert_node_id')
    @patch('src.malla.database.get_db_connection')
    def test_get_traceroute_related_nodes_empty(self, mock_db_conn, mock_convert):
        """Test traceroute related nodes with no results."""
        mock_convert.return_value = 123456789

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []  # No packets

        result = NodeService.get_traceroute_related_nodes("!075bcd15")

        assert result["node_id"] == 123456789
        assert result["total_count"] == 0
        assert len(result["related_nodes"]) == 0

    @patch('src.malla.services.node_service.convert_node_id')
    @patch('src.malla.database.get_db_connection')
    @patch('src.malla.services.node_service.logger')
    def test_get_traceroute_related_nodes_packet_error(self, mock_logger, mock_db_conn, mock_convert):
        """Test traceroute related nodes with packet processing error."""
        mock_convert.return_value = 123456789

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_db_conn.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock packet data
        mock_cursor.fetchall.side_effect = [
            [  # Packets query
                (
                    "packet1", 1234567890.0, 123456789, 987654321, "gateway1",
                    3, 3, b"invalid_payload"
                )
            ],
            []  # No node info needed due to error
        ]

        # Mock TraceroutePacket to raise exception
        with patch('src.malla.models.traceroute.TraceroutePacket') as mock_tr_packet:
            mock_tr_packet.side_effect = Exception("Parse error")

            result = NodeService.get_traceroute_related_nodes("!075bcd15")

        # Should log warning and continue
        mock_logger.warning.assert_called_once()
        assert result["node_id"] == 123456789
        assert result["total_count"] == 0
        assert len(result["related_nodes"]) == 0


class TestNodeNotFoundError:
    """Test cases for NodeNotFoundError exception."""

    def test_node_not_found_error_inheritance(self):
        """Test that NodeNotFoundError inherits from Exception."""
        error = NodeNotFoundError("Test message")
        assert isinstance(error, Exception)
        assert str(error) == "Test message"

    def test_node_not_found_error_no_message(self):
        """Test NodeNotFoundError without message."""
        error = NodeNotFoundError()
        assert isinstance(error, Exception)