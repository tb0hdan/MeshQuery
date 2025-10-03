"""Tests for traceroute service."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.malla.services.traceroute_service import TracerouteService


class TestTracerouteService:
    """Test cases for TracerouteService class."""

    @patch('src.malla.services.traceroute_service.TracerouteRepository.get_traceroute_packets')
    @patch('src.malla.services.traceroute_service.TraceroutePacket')
    def test_get_traceroutes_success(self, mock_tr_packet_class, mock_repository):
        """Test successful traceroute retrieval."""
        # Mock repository response
        mock_repository.return_value = {
            "packets": [
                {
                    "id": "packet1",
                    "timestamp": 1234567890.0,
                    "from_node_id": 123,
                    "to_node_id": 456,
                    "raw_payload": memoryview(b"test_payload")
                }
            ],
            "total_count": 1,
            "has_more": False
        }

        # Mock TraceroutePacket instance
        mock_tr_packet = Mock()
        mock_tr_packet_class.return_value = mock_tr_packet
        mock_tr_packet.has_return_path.return_value = True
        mock_tr_packet.is_complete.return_value = True
        mock_tr_packet.format_path_display.return_value = "Node1 -> Node2"
        mock_tr_packet.forward_path.total_hops = 2
        mock_tr_packet.get_rf_hops.return_value = [Mock(), Mock()]

        result = TracerouteService.get_traceroutes(
            page=1,
            per_page=50,
            gateway_id="test_gateway",
            from_node=123,
            to_node=456,
            search="test"
        )

        # Verify repository call
        mock_repository.assert_called_once_with(
            limit=50,
            offset=0,
            filters={"gateway_id": "test_gateway", "from_node": 123, "to_node": 456},
            search="test"
        )

        # Verify TraceroutePacket creation
        mock_tr_packet_class.assert_called_once_with(
            packet_data={
                "id": "packet1",
                "timestamp": 1234567890.0,
                "from_node_id": 123,
                "to_node_id": 456,
                "raw_payload": b"test_payload"  # Should be converted from memoryview
            },
            resolve_names=True
        )

        # Verify enhanced fields
        enhanced_tr = result["traceroutes"][0]
        assert enhanced_tr["has_return_path"] is True
        assert enhanced_tr["is_complete"] is True
        assert enhanced_tr["display_path"] == "Node1 -> Node2"
        assert enhanced_tr["total_hops"] == 2
        assert enhanced_tr["rf_hops"] == 2

    @patch('src.malla.services.traceroute_service.TracerouteRepository.get_traceroute_packets')
    def test_get_traceroutes_no_filters(self, mock_repository):
        """Test traceroute retrieval without filters."""
        mock_repository.return_value = {
            "packets": [],
            "total_count": 0,
            "has_more": False
        }

        result = TracerouteService.get_traceroutes(page=2, per_page=25)

        mock_repository.assert_called_once_with(
            limit=25,
            offset=25,  # (page-1) * per_page = (2-1) * 25
            filters={},
            search=None
        )

        assert result["traceroutes"] == []

    @patch('src.malla.services.traceroute_service.TracerouteRepository.get_traceroute_packets')
    @patch('src.malla.services.traceroute_service.TraceroutePacket')
    def test_get_traceroutes_with_memoryview_payload(self, mock_tr_packet_class, mock_repository):
        """Test handling of memoryview payloads."""
        test_payload = b"binary_payload_data"
        mock_repository.return_value = {
            "packets": [
                {
                    "id": "packet1",
                    "raw_payload": memoryview(test_payload)
                }
            ],
            "total_count": 1,
            "has_more": False
        }

        mock_tr_packet = Mock()
        mock_tr_packet_class.return_value = mock_tr_packet
        mock_tr_packet.has_return_path.return_value = False
        mock_tr_packet.is_complete.return_value = False
        mock_tr_packet.format_path_display.return_value = ""
        mock_tr_packet.forward_path.total_hops = 0
        mock_tr_packet.get_rf_hops.return_value = []

        result = TracerouteService.get_traceroutes()

        # Verify payload was converted from memoryview to bytes
        call_args = mock_tr_packet_class.call_args[1]
        assert call_args["packet_data"]["raw_payload"] == test_payload
        assert isinstance(call_args["packet_data"]["raw_payload"], bytes)

    @patch('src.malla.services.traceroute_service.TracerouteRepository.get_traceroute_packets')
    @patch('src.malla.services.traceroute_service.TraceroutePacket')
    def test_get_traceroutes_with_bytes_payload(self, mock_tr_packet_class, mock_repository):
        """Test handling when payload is already bytes."""
        test_payload = b"binary_payload_data"
        mock_repository.return_value = {
            "packets": [
                {
                    "id": "packet1",
                    "raw_payload": test_payload  # Already bytes
                }
            ],
            "total_count": 1,
            "has_more": False
        }

        mock_tr_packet = Mock()
        mock_tr_packet_class.return_value = mock_tr_packet
        mock_tr_packet.has_return_path.return_value = False
        mock_tr_packet.is_complete.return_value = False
        mock_tr_packet.format_path_display.return_value = ""
        mock_tr_packet.forward_path.total_hops = 0
        mock_tr_packet.get_rf_hops.return_value = []

        result = TracerouteService.get_traceroutes()

        # Verify payload remains bytes
        call_args = mock_tr_packet_class.call_args[1]
        assert call_args["packet_data"]["raw_payload"] == test_payload
        assert isinstance(call_args["packet_data"]["raw_payload"], bytes)

    def test_get_traceroutes_pagination_calculation(self):
        """Test pagination offset calculation."""
        with patch('src.malla.services.traceroute_service.TracerouteRepository.get_traceroute_packets') as mock_repo:
            mock_repo.return_value = {"packets": [], "total_count": 0, "has_more": False}

            # Test various page/per_page combinations
            TracerouteService.get_traceroutes(page=1, per_page=10)
            mock_repo.assert_called_with(limit=10, offset=0, filters={}, search=None)

            TracerouteService.get_traceroutes(page=3, per_page=25)
            mock_repo.assert_called_with(limit=25, offset=50, filters={}, search=None)

            TracerouteService.get_traceroutes(page=5, per_page=100)
            mock_repo.assert_called_with(limit=100, offset=400, filters={}, search=None)

    @patch('src.malla.services.traceroute_service.logger')
    def test_get_traceroutes_logging(self, mock_logger):
        """Test that traceroute requests are properly logged."""
        with patch('src.malla.services.traceroute_service.TracerouteRepository.get_traceroute_packets') as mock_repo:
            mock_repo.return_value = {"packets": [], "total_count": 0, "has_more": False}

            TracerouteService.get_traceroutes(
                page=2,
                per_page=30,
                gateway_id="gw1",
                from_node=123,
                to_node=456,
                search="test_search"
            )

            # Verify logging was called
            mock_logger.info.assert_called_once()
            log_message = mock_logger.info.call_args[0][0]
            assert "page=2" in log_message
            assert "per_page=30" in log_message
            assert "gateway_id=gw1" in log_message
            assert "from_node=123" in log_message
            assert "to_node=456" in log_message
            assert "search=test_search" in log_message

    def test_get_traceroutes_filter_building(self):
        """Test that filters are built correctly."""
        with patch('src.malla.services.traceroute_service.TracerouteRepository.get_traceroute_packets') as mock_repo:
            mock_repo.return_value = {"packets": [], "total_count": 0, "has_more": False}

            # Test with all filters
            TracerouteService.get_traceroutes(
                gateway_id="gw1",
                from_node=123,
                to_node=456
            )

            expected_filters = {
                "gateway_id": "gw1",
                "from_node": 123,
                "to_node": 456
            }
            mock_repo.assert_called_with(
                limit=50, offset=0, filters=expected_filters, search=None
            )

            # Test with partial filters
            TracerouteService.get_traceroutes(from_node=789)
            expected_filters = {"from_node": 789}
            mock_repo.assert_called_with(
                limit=50, offset=0, filters=expected_filters, search=None
            )

    @patch('src.malla.services.traceroute_service.TracerouteRepository.get_traceroute_packets')
    @patch('src.malla.services.traceroute_service.TraceroutePacket')
    def test_get_traceroutes_packet_enhancement_error(self, mock_tr_packet_class, mock_repository):
        """Test handling of errors during packet enhancement."""
        mock_repository.return_value = {
            "packets": [{"id": "packet1", "raw_payload": b"test"}],
            "total_count": 1,
            "has_more": False
        }

        # Mock TraceroutePacket to raise an exception
        mock_tr_packet_class.side_effect = Exception("Parsing error")

        # Should raise the exception (no error handling in current implementation)
        with pytest.raises(Exception, match="Parsing error"):
            TracerouteService.get_traceroutes()

    @patch('src.malla.services.traceroute_service.TracerouteRepository.get_traceroute_packets')
    @patch('src.malla.services.traceroute_service.TraceroutePacket')
    def test_get_traceroutes_result_structure(self, mock_tr_packet_class, mock_repository):
        """Test that the result structure includes original repository data."""
        mock_repository.return_value = {
            "packets": [{"id": "packet1"}],
            "total_count": 100,
            "has_more": True,
            "additional_field": "test_value"
        }

        mock_tr_packet = Mock()
        mock_tr_packet_class.return_value = mock_tr_packet
        mock_tr_packet.has_return_path.return_value = False
        mock_tr_packet.is_complete.return_value = False
        mock_tr_packet.format_path_display.return_value = ""
        mock_tr_packet.forward_path.total_hops = 0
        mock_tr_packet.get_rf_hops.return_value = []

        result = TracerouteService.get_traceroutes()

        # Should have pagination fields and traceroutes
        assert result["total_count"] == 100
        assert result["page"] == 1
        assert result["per_page"] == 50
        assert result["total_pages"] == 2
        assert "traceroutes" in result
        assert len(result["traceroutes"]) == 1

    def test_get_traceroutes_default_parameters(self):
        """Test default parameter values."""
        with patch('src.malla.services.traceroute_service.TracerouteRepository.get_traceroute_packets') as mock_repo:
            mock_repo.return_value = {"packets": [], "total_count": 0, "has_more": False}

            TracerouteService.get_traceroutes()

            # Verify default values
            mock_repo.assert_called_once_with(
                limit=50,     # Default per_page
                offset=0,     # Default page=1 -> offset=0
                filters={},   # No filters by default
                search=None   # No search by default
            )