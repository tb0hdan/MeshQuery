"""Tests for optimized PacketRepository implementation."""

import unittest
from unittest.mock import Mock, patch, MagicMock
import time
from datetime import datetime

from src.malla.database.packet_repository_optimized import PacketRepositoryOptimized


class TestPacketRepositoryOptimized(unittest.TestCase):
    """Test cases for PacketRepositoryOptimized."""

    def setUp(self):
        """Set up test fixtures."""
        self.repo = PacketRepositoryOptimized()

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    def test_get_packets_basic(self, mock_get_db):
        """Test basic packet retrieval functionality."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock fetchone for count
        mock_cursor.fetchone.return_value = [10]

        # Mock fetchall for packets
        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'timestamp': 1609459200.0,
                'from_node_id': 123,
                'to_node_id': 456,
                'portnum': 1,
                'portnum_name': 'TEXT_MESSAGE_APP',
                'gateway_id': 'gateway1',
                'channel_id': 'channel1',
                'mesh_packet_id': 'mesh123',
                'rssi': -80.5,
                'snr': 5.2,
                'hop_limit': 3,
                'hop_start': 5,
                'payload_length': 50,
                'processed_successfully': 1,
                'via_mqtt': 0,
                'want_ack': 1,
                'priority': 1,
                'delayed': 0,
                'channel_index': 0,
                'rx_time': 1609459200.5,
                'pki_encrypted': 0,
                'next_hop': None,
                'relay_node': None,
                'tx_after': None,
                'timestamp_str': '2021-01-01 00:00:00',
                'hop_count': 2
            }
        ]

        result = self.repo.get_packets()

        self.assertIn('packets', result)
        self.assertIn('total_count', result)
        self.assertIn('has_more', result)
        self.assertIn('is_grouped', result)
        self.assertEqual(result['total_count'], 10)
        self.assertEqual(len(result['packets']), 1)
        self.assertFalse(result['is_grouped'])

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    def test_get_packets_with_filters(self, mock_get_db):
        """Test packet retrieval with various filters."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = [5]
        mock_cursor.fetchall.return_value = []

        filters = {
            'start_time': 1609459200.0,
            'end_time': 1609545600.0,
            'from_node': 123,
            'to_node': 456,
            'portnum': 'TEXT_MESSAGE_APP',
            'min_rssi': -100,
            'max_rssi': -50,
            'gateway_id': 'gateway1',
            'hop_count': 2,
            'exclude_from': 999,
            'exclude_to': 888
        }

        result = self.repo.get_packets(filters=filters)

        # Verify the query was called with proper parameters
        mock_cursor.execute.assert_called()
        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        # Check that filters are applied in the WHERE clause
        self.assertIn('timestamp >=', query)
        self.assertIn('timestamp <=', query)
        self.assertIn('from_node_id =', query)
        self.assertIn('to_node_id =', query)
        self.assertIn('portnum_name =', query)
        self.assertIn('rssi >=', query)
        self.assertIn('rssi <=', query)
        self.assertIn('gateway_id =', query)
        self.assertIn('(hop_start - hop_limit) =', query)
        self.assertIn('from_node_id IS NULL OR from_node_id !=', query)
        self.assertIn('to_node_id IS NULL OR to_node_id !=', query)

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    def test_get_packets_with_search(self, mock_get_db):
        """Test packet retrieval with search functionality."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = [3]
        mock_cursor.fetchall.return_value = []

        result = self.repo.get_packets(search='gateway1')

        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]
        params = call_args[0][1]

        # Check search condition is applied
        self.assertIn('portnum_name LIKE', query)
        self.assertIn('gateway_id LIKE', query)
        self.assertIn('channel_id LIKE', query)
        self.assertIn('CAST(from_node_id AS TEXT) LIKE', query)
        self.assertIn('CAST(to_node_id AS TEXT) LIKE', query)

        # Check search parameters (5 instances of the search term)
        search_params = [p for p in params if isinstance(p, str) and 'gateway1' in p]
        self.assertEqual(len(search_params), 5)

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    @patch('src.malla.database.packet_repository_optimized.time')
    def test_get_packets_grouped_basic(self, mock_time, mock_get_db):
        """Test grouped packet retrieval functionality."""
        mock_time.time.return_value = 1609545600.0  # Fixed timestamp for test

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock packet data for grouping
        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'timestamp': 1609459200.0,
                'from_node_id': 123,
                'to_node_id': 456,
                'portnum': 1,
                'portnum_name': 'TEXT_MESSAGE_APP',
                'gateway_id': 'gateway1',
                'mesh_packet_id': 'mesh123',
                'rssi': -80.5,
                'snr': 5.2,
                'hop_limit': 3,
                'hop_start': 5,
                'payload_length': 50,
                'processed_successfully': 1,
                'hop_count': 2
            },
            {
                'id': 2,
                'timestamp': 1609459260.0,  # Same packet, different gateway
                'from_node_id': 123,
                'to_node_id': 456,
                'portnum': 1,
                'portnum_name': 'TEXT_MESSAGE_APP',
                'gateway_id': 'gateway2',
                'mesh_packet_id': 'mesh123',
                'rssi': -75.0,
                'snr': 7.1,
                'hop_limit': 3,
                'hop_start': 5,
                'payload_length': 50,
                'processed_successfully': 1,
                'hop_count': 2
            }
        ]

        result = self.repo.get_packets(group_packets=True)

        self.assertIn('packets', result)
        self.assertIn('total_count', result)
        self.assertIn('is_grouped', result)
        self.assertTrue(result['is_grouped'])

        # Should have grouped the two packets into one
        self.assertEqual(len(result['packets']), 1)

        packet = result['packets'][0]
        self.assertEqual(packet['gateway_count'], 2)
        self.assertIn('gateway1', packet['gateway_list'])
        self.assertIn('gateway2', packet['gateway_list'])
        self.assertEqual(packet['min_rssi'], -80.5)
        self.assertEqual(packet['max_rssi'], -75.0)
        self.assertEqual(packet['reception_count'], 2)
        self.assertTrue(packet['is_grouped'])

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    def test_get_packets_grouped_with_time_filter(self, mock_get_db):
        """Test grouped packet retrieval with explicit time filters."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = []

        filters = {
            'start_time': 1609459200.0,
            'end_time': 1609545600.0
        }

        result = self.repo.get_packets(group_packets=True, filters=filters)

        # When explicit time filters are provided, should not add default time window
        call_args = mock_cursor.execute.call_args
        query = call_args[0][0]

        self.assertIn('mesh_packet_id IS NOT NULL', query)
        self.assertIn('timestamp >=', query)
        self.assertIn('timestamp <=', query)

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    @patch('src.malla.database.packet_repository_optimized.time')
    def test_get_packets_grouped_default_time_window(self, mock_time, mock_get_db):
        """Test grouped packet retrieval applies default time window when no filters."""
        mock_time.time.return_value = 1609545600.0  # Fixed timestamp

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = []

        result = self.repo.get_packets(group_packets=True)

        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]

        # Should add 7-day cutoff timestamp
        expected_cutoff = 1609545600.0 - (7 * 24 * 3600)
        self.assertIn(expected_cutoff, params)

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    def test_get_packets_grouped_aggregation_calculations(self, mock_get_db):
        """Test grouped packet aggregation calculations."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'timestamp': 1609459200.0,
                'from_node_id': 123,
                'to_node_id': 456,
                'portnum': 1,
                'portnum_name': 'TEXT_MESSAGE_APP',
                'gateway_id': 'gateway1',
                'mesh_packet_id': 'mesh123',
                'rssi': -80.0,
                'snr': 5.0,
                'hop_limit': 3,
                'hop_start': 5,
                'payload_length': 40,
                'processed_successfully': 1,
                'hop_count': 2
            },
            {
                'id': 2,
                'timestamp': 1609459260.0,
                'from_node_id': 123,
                'to_node_id': 456,
                'portnum': 1,
                'portnum_name': 'TEXT_MESSAGE_APP',
                'gateway_id': 'gateway2',
                'mesh_packet_id': 'mesh123',
                'rssi': -70.0,
                'snr': 8.0,
                'hop_limit': 2,
                'hop_start': 5,
                'payload_length': 60,
                'processed_successfully': 1,
                'hop_count': 3
            }
        ]

        result = self.repo.get_packets(group_packets=True)

        packet = result['packets'][0]

        # Test aggregation calculations
        self.assertEqual(packet['min_rssi'], -80.0)
        self.assertEqual(packet['max_rssi'], -70.0)
        self.assertEqual(packet['min_snr'], 5.0)
        self.assertEqual(packet['max_snr'], 8.0)
        self.assertEqual(packet['min_hops'], 2)
        self.assertEqual(packet['max_hops'], 3)
        self.assertEqual(packet['avg_payload_length'], 50.0)  # (40 + 60) / 2

        # Test formatted ranges
        self.assertEqual(packet['rssi_range'], '-80.0 to -70.0 dBm')
        self.assertEqual(packet['snr_range'], '5.00 to 8.00 dB')
        self.assertEqual(packet['hop_range'], '2-3')

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    def test_get_packets_grouped_single_values(self, mock_get_db):
        """Test grouped packet formatting when min/max values are the same."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'timestamp': 1609459200.0,
                'from_node_id': 123,
                'to_node_id': 456,
                'portnum': 1,
                'portnum_name': 'TEXT_MESSAGE_APP',
                'gateway_id': 'gateway1',
                'mesh_packet_id': 'mesh123',
                'rssi': -80.0,
                'snr': 5.0,
                'hop_limit': 3,
                'hop_start': 5,
                'payload_length': 50,
                'processed_successfully': 1,
                'hop_count': 2
            }
        ]

        result = self.repo.get_packets(group_packets=True)

        packet = result['packets'][0]

        # When min == max, should show single value
        self.assertEqual(packet['rssi_range'], '-80.0 dBm')
        self.assertEqual(packet['snr_range'], '5.00 dB')
        self.assertEqual(packet['hop_range'], '2')

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    def test_get_packets_grouped_none_values(self, mock_get_db):
        """Test grouped packet handling of None values."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'timestamp': 1609459200.0,
                'from_node_id': 123,
                'to_node_id': 456,
                'portnum': 1,
                'portnum_name': 'TEXT_MESSAGE_APP',
                'gateway_id': None,
                'mesh_packet_id': 'mesh123',
                'rssi': None,
                'snr': None,
                'hop_limit': None,
                'hop_start': None,
                'payload_length': None,
                'processed_successfully': 1,
                'hop_count': None
            }
        ]

        result = self.repo.get_packets(group_packets=True)

        packet = result['packets'][0]

        # Should handle None values gracefully
        self.assertEqual(packet['gateway_count'], 0)
        self.assertEqual(packet['gateway_list'], '')
        self.assertIsNone(packet['min_rssi'])
        self.assertIsNone(packet['max_rssi'])
        self.assertIsNone(packet['min_snr'])
        self.assertIsNone(packet['max_snr'])
        self.assertIsNone(packet['min_hops'])
        self.assertIsNone(packet['max_hops'])
        self.assertIsNone(packet['avg_payload_length'])
        self.assertIsNone(packet['rssi_range'])
        self.assertIsNone(packet['snr_range'])
        self.assertIsNone(packet['hop_range'])

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    def test_get_packets_pagination(self, mock_get_db):
        """Test pagination functionality."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = [100]
        mock_cursor.fetchall.return_value = []

        result = self.repo.get_packets(limit=20, offset=40)

        call_args = mock_cursor.execute.call_args_list[-1]  # Get the main query call
        query = call_args[0][0]
        params = call_args[0][1]

        # Check LIMIT and OFFSET are applied
        self.assertIn('LIMIT', query)
        self.assertIn('OFFSET', query)
        self.assertIn(20, params)  # limit
        self.assertIn(40, params)  # offset

        # Check has_more calculation
        self.assertTrue(result['has_more'])  # 100 total > 40 + 20

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    def test_get_packets_ordering(self, mock_get_db):
        """Test ordering functionality."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = [10]
        mock_cursor.fetchall.return_value = []

        result = self.repo.get_packets(order_by='rssi', order_dir='asc')

        call_args = mock_cursor.execute.call_args_list[-1]
        query = call_args[0][0]

        self.assertIn('ORDER BY rssi ASC', query)

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    def test_get_packets_error_handling(self, mock_get_db):
        """Test error handling in get_packets."""
        mock_get_db.side_effect = Exception("Database connection failed")

        with self.assertRaises(Exception) as context:
            self.repo.get_packets()

        self.assertEqual(str(context.exception), "Database connection failed")

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    def test_get_packets_grouped_fetch_multiplier(self, mock_get_db):
        """Test grouped packets fetch multiplier logic."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = []

        # Test with small limit
        result = self.repo.get_packets(group_packets=True, limit=5)
        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]
        # fetch_multiplier = max(10, 5 // 5) = max(10, 1) = 10
        # fetch_limit = min(5 * 10, 10000) = min(50, 10000) = 50
        self.assertIn(50, params)

        # Test with large limit
        result = self.repo.get_packets(group_packets=True, limit=500)
        call_args = mock_cursor.execute.call_args
        params = call_args[0][1]
        # fetch_multiplier = max(10, 500 // 5) = max(10, 100) = 100
        # fetch_limit = min(500 * 100, 10000) = min(50000, 10000) = 10000
        self.assertIn(10000, params)

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    def test_get_packets_timestamp_formatting(self, mock_get_db):
        """Test timestamp formatting in ungrouped packets."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchone.return_value = [1]
        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'timestamp': 1609459200.0,
                'from_node_id': 123,
                'to_node_id': 456,
                'portnum': 1,
                'portnum_name': 'TEXT_MESSAGE_APP',
                'gateway_id': 'gateway1',
                'channel_id': 'channel1',
                'mesh_packet_id': 'mesh123',
                'rssi': -80.5,
                'snr': 5.2,
                'hop_limit': 3,
                'hop_start': 5,
                'payload_length': 50,
                'processed_successfully': 1,
                'via_mqtt': 0,
                'want_ack': 1,
                'priority': 1,
                'delayed': 0,
                'channel_index': 0,
                'rx_time': 1609459200.5,
                'pki_encrypted': 0,
                'next_hop': None,
                'relay_node': None,
                'tx_after': None,
                'timestamp_str': None,  # Test case where timestamp_str is None
                'hop_count': None  # Test hop count calculation
            }
        ]

        result = self.repo.get_packets()

        packet = result['packets'][0]

        # Should format timestamp when timestamp_str is None (timezone may vary)
        self.assertIsNotNone(packet['timestamp_str'])
        # Check the pattern matches expected format (could be 2020-12-31 or 2021-01-01 depending on timezone)
        self.assertRegex(packet['timestamp_str'], r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')

        # Should calculate hop count when None
        self.assertEqual(packet['hop_count'], 2)  # 5 - 3 = 2

        # Should add success and is_grouped flags
        self.assertEqual(packet['success'], 1)
        self.assertFalse(packet['is_grouped'])

    @patch('src.malla.database.packet_repository_optimized.get_db_connection')
    def test_get_packets_grouped_sort_order(self, mock_get_db):
        """Test sorting in grouped packet mode."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_get_db.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = [
            {
                'id': 1,
                'timestamp': 1609459300.0,  # Later timestamp
                'from_node_id': 123,
                'to_node_id': 456,
                'portnum': 1,
                'portnum_name': 'TEXT_MESSAGE_APP',
                'gateway_id': 'gateway1',
                'mesh_packet_id': 'mesh124',
                'rssi': -80.0,
                'snr': 5.0,
                'hop_limit': 3,
                'hop_start': 5,
                'payload_length': 50,
                'processed_successfully': 1,
                'hop_count': 2
            },
            {
                'id': 2,
                'timestamp': 1609459200.0,  # Earlier timestamp
                'from_node_id': 123,
                'to_node_id': 456,
                'portnum': 1,
                'portnum_name': 'TEXT_MESSAGE_APP',
                'gateway_id': 'gateway2',
                'mesh_packet_id': 'mesh123',
                'rssi': -70.0,
                'snr': 8.0,
                'hop_limit': 2,
                'hop_start': 5,
                'payload_length': 60,
                'processed_successfully': 1,
                'hop_count': 3
            }
        ]

        # Test descending order (default)
        result = self.repo.get_packets(group_packets=True, order_dir='desc')

        self.assertEqual(len(result['packets']), 2)
        # Should be sorted by timestamp desc: mesh124 (later) before mesh123 (earlier)
        self.assertEqual(result['packets'][0]['mesh_packet_id'], 'mesh124')
        self.assertEqual(result['packets'][1]['mesh_packet_id'], 'mesh123')

        # Test ascending order
        result = self.repo.get_packets(group_packets=True, order_dir='asc')

        # Should be sorted by timestamp asc: mesh123 (earlier) before mesh124 (later)
        self.assertEqual(result['packets'][0]['mesh_packet_id'], 'mesh123')
        self.assertEqual(result['packets'][1]['mesh_packet_id'], 'mesh124')


if __name__ == '__main__':
    unittest.main()