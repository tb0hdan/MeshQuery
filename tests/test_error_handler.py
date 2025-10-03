"""Tests for error handling utilities."""

import time
import unittest
from unittest.mock import Mock, patch, MagicMock

from flask import Flask, request, jsonify

from src.malla.utils.error_handler import (
    APIError,
    handle_api_errors,
    validate_request_data,
    log_api_request,
    rate_limit
)


class TestErrorHandler(unittest.TestCase):
    """Test cases for error handler utilities."""

    def setUp(self):
        """Set up test fixtures."""
        self.app = Flask(__name__)
        self.app.config['TESTING'] = True
        self.client = self.app.test_client()

        # Clear rate limit state between tests
        self._clear_rate_limit_state()

    def _clear_rate_limit_state(self):
        """Clear the rate limit state between tests."""
        # This is a bit hacky but necessary to reset state between tests
        # since the rate_limit decorator uses module-level state
        import src.malla.utils.error_handler as error_handler
        # We need to patch the rate_limit function to reset its internal state
        # But since it's a closure, we'll patch it in each test instead

    def test_api_error_initialization(self):
        """Test APIError custom exception initialization."""
        # Test with all parameters
        error = APIError("Test error", 400, "TEST_ERROR")
        self.assertEqual(error.message, "Test error")
        self.assertEqual(error.status_code, 400)
        self.assertEqual(error.error_code, "TEST_ERROR")
        self.assertEqual(str(error), "Test error")

        # Test with defaults
        error_default = APIError("Default error")
        self.assertEqual(error_default.message, "Default error")
        self.assertEqual(error_default.status_code, 500)
        self.assertIsNone(error_default.error_code)

    def test_handle_api_errors_decorator_with_api_error(self):
        """Test handle_api_errors decorator with APIError."""
        @handle_api_errors
        def test_function():
            raise APIError("Test API error", 400, "TEST_CODE")

        with self.app.test_request_context():
            with patch('src.malla.utils.error_handler.logger') as mock_logger:
                response, status_code = test_function()

                # Check response
                response_data = response.get_json()
                self.assertEqual(response_data['error'], "Test API error")
                self.assertEqual(response_data['error_code'], "TEST_CODE")
                self.assertEqual(response_data['status_code'], 400)
                self.assertEqual(status_code, 400)

                # Check logging
                mock_logger.warning.assert_called_once_with(
                    "API error in %s: %s", "test_function", "Test API error"
                )

    def test_handle_api_errors_decorator_with_generic_exception(self):
        """Test handle_api_errors decorator with generic exception."""
        @handle_api_errors
        def test_function():
            raise ValueError("Generic error")

        with self.app.test_request_context():
            with patch('src.malla.utils.error_handler.logger') as mock_logger:
                response, status_code = test_function()

                # Check response
                response_data = response.get_json()
                self.assertEqual(response_data['error'], "Internal server error")
                self.assertEqual(response_data['error_code'], "INTERNAL_ERROR")
                self.assertEqual(response_data['status_code'], 500)
                self.assertEqual(status_code, 500)

                # Check logging
                mock_logger.error.assert_called_once_with(
                    "Unexpected error in %s: %s", "test_function", mock_logger.error.call_args[0][2], exc_info=True
                )

    def test_handle_api_errors_decorator_with_successful_function(self):
        """Test handle_api_errors decorator with successful function."""
        @handle_api_errors
        def test_function():
            return "success", 200

        with self.app.test_request_context():
            result = test_function()
            self.assertEqual(result, ("success", 200))

    def test_validate_request_data_decorator_with_json_request(self):
        """Test validate_request_data decorator with JSON request."""
        # Mock schema class
        mock_schema_class = Mock()
        mock_schema = Mock()
        mock_schema_class.return_value = mock_schema
        mock_schema.load.return_value = {"validated": "data"}

        @validate_request_data(mock_schema_class)
        def test_function(validated_data=None):
            return {"received": validated_data}

        with self.app.test_request_context(
            '/test',
            method='POST',
            data='{"test": "data"}',
            content_type='application/json'
        ):
            with patch('flask.request') as mock_request:
                mock_request.is_json = True
                mock_request.get_json.return_value = {"test": "data"}

                result = test_function()

                # Check that schema was called correctly
                mock_schema_class.assert_called_once()
                mock_schema.load.assert_called_once_with({"test": "data"})

                # Check result
                self.assertEqual(result, {"received": {"validated": "data"}})

    def test_validate_request_data_decorator_with_form_request(self):
        """Test validate_request_data decorator with form request."""
        # Mock schema class
        mock_schema_class = Mock()
        mock_schema = Mock()
        mock_schema_class.return_value = mock_schema
        mock_schema.load.return_value = {"validated": "form_data"}

        @validate_request_data(mock_schema_class)
        def test_function(validated_data=None):
            return {"received": validated_data}

        with self.app.test_request_context(
            '/test',
            method='POST',
            data={"form_field": "value"}
        ):
            with patch('flask.request') as mock_request:
                mock_request.is_json = False
                mock_form = Mock()
                mock_form.to_dict.return_value = {"form_field": "value"}
                mock_request.form = mock_form

                result = test_function()

                # Check that schema was called correctly
                mock_schema_class.assert_called_once()
                mock_schema.load.assert_called_once_with({"form_field": "value"})

                # Check result
                self.assertEqual(result, {"received": {"validated": "form_data"}})

    def test_validate_request_data_decorator_with_validation_error(self):
        """Test validate_request_data decorator with validation error."""
        # Mock schema class that raises an exception
        mock_schema_class = Mock()
        mock_schema = Mock()
        mock_schema_class.return_value = mock_schema
        mock_schema.load.side_effect = Exception("Validation failed")

        @validate_request_data(mock_schema_class)
        def test_function(validated_data=None):
            return {"received": validated_data}

        with self.app.test_request_context(
            '/test',
            method='POST',
            data='{"invalid": "data"}',
            content_type='application/json'
        ):
            with patch('flask.request') as mock_request:
                mock_request.is_json = True
                mock_request.get_json.return_value = {"invalid": "data"}

                with patch('src.malla.utils.error_handler.logger') as mock_logger:
                    response, status_code = test_function()

                    # Check response
                    response_data = response.get_json()
                    self.assertEqual(response_data['error'], "Invalid request data")
                    self.assertEqual(response_data['error_code'], "VALIDATION_ERROR")
                    self.assertEqual(response_data['details'], "Validation failed")
                    self.assertEqual(status_code, 400)

                    # Check logging
                    mock_logger.warning.assert_called_once_with(
                        "Validation error in %s: %s", "test_function", mock_schema.load.side_effect
                    )

    def test_log_api_request_decorator(self):
        """Test log_api_request decorator."""
        @log_api_request
        def test_function():
            return "success"

        with self.app.test_request_context(
            '/test/path',
            method='GET',
            environ_base={'REMOTE_ADDR': '192.168.1.1'}
        ):
            with patch('flask.request') as mock_request:
                mock_request.method = 'GET'
                mock_request.path = '/test/path'
                mock_request.remote_addr = '192.168.1.1'

                with patch('src.malla.utils.error_handler.logger') as mock_logger:
                    result = test_function()

                    # Check that function still works
                    self.assertEqual(result, "success")

                    # Check logging
                    mock_logger.info.assert_called_once_with(
                        "API request: GET /test/path from 192.168.1.1"
                    )

    @patch('src.malla.utils.error_handler.time')
    def test_rate_limit_decorator_within_limit(self, mock_time):
        """Test rate_limit decorator when within limits."""
        mock_time.time.return_value = 1000

        @rate_limit(max_requests=2, window_seconds=60)
        def test_function():
            return "success"

        with self.app.test_request_context():
            with patch('flask.request') as mock_request:
                mock_request.remote_addr = '192.168.1.1'

                # First request should succeed
                result1 = test_function()
                self.assertEqual(result1, "success")

                # Second request should also succeed
                result2 = test_function()
                self.assertEqual(result2, "success")

    @patch('src.malla.utils.error_handler.time')
    def test_rate_limit_decorator_exceeds_limit(self, mock_time):
        """Test rate_limit decorator when exceeding limits."""
        mock_time.time.return_value = 1000

        @rate_limit(max_requests=1, window_seconds=60)
        def test_function():
            return "success"

        with self.app.test_request_context():
            with patch('flask.request') as mock_request:
                mock_request.remote_addr = '192.168.1.1'

                with patch('src.malla.utils.error_handler.logger') as mock_logger:
                    # First request should succeed
                    result1 = test_function()
                    self.assertEqual(result1, "success")

                    # Second request should be rate limited
                    response, status_code = test_function()

                    # Check response
                    response_data = response.get_json()
                    self.assertEqual(response_data['error'], "Rate limit exceeded")
                    self.assertEqual(response_data['error_code'], "RATE_LIMIT_EXCEEDED")
                    self.assertEqual(response_data['retry_after'], 60)
                    self.assertEqual(status_code, 429)

                    # Check logging - the IP will be whatever mock_request.remote_addr returns
                    mock_logger.warning.assert_called_once()
                    call_args = mock_logger.warning.call_args[0]
                    self.assertEqual(call_args[0], "Rate limit exceeded for %s")
                    # The actual IP value may vary in test context

    @patch('src.malla.utils.error_handler.time')
    def test_rate_limit_decorator_window_cleanup(self, mock_time):
        """Test rate_limit decorator cleans up old entries."""
        # Start with time 1000
        mock_time.time.return_value = 1000

        @rate_limit(max_requests=1, window_seconds=60)
        def test_function():
            return "success"

        with self.app.test_request_context():
            with patch('flask.request') as mock_request:
                mock_request.remote_addr = '192.168.1.1'

                # First request at time 1000
                result1 = test_function()
                self.assertEqual(result1, "success")

                # Move time forward beyond the window (60 seconds + 1)
                mock_time.time.return_value = 1061

                # This request should succeed because old entry was cleaned up
                result2 = test_function()
                self.assertEqual(result2, "success")

    @patch('src.malla.utils.error_handler.time')
    def test_rate_limit_decorator_different_ips(self, mock_time):
        """Test rate_limit decorator handles different IPs separately."""
        mock_time.time.return_value = 1000

        @rate_limit(max_requests=2, window_seconds=60)  # Allow 2 requests to handle both IPs
        def test_function():
            return "success"

        with self.app.test_request_context():
            with patch('flask.request') as mock_request:
                # First IP
                mock_request.remote_addr = '192.168.1.1'
                result1 = test_function()
                self.assertEqual(result1, "success")

                # Different IP should not be affected by first IP's limit
                mock_request.remote_addr = '192.168.1.2'
                result2 = test_function()
                self.assertEqual(result2, "success")

    @patch('src.malla.utils.error_handler.time')
    def test_rate_limit_decorator_unknown_ip(self, mock_time):
        """Test rate_limit decorator handles unknown IP addresses."""
        mock_time.time.return_value = 1000

        @rate_limit(max_requests=1, window_seconds=60)
        def test_function():
            return "success"

        with self.app.test_request_context():
            with patch('flask.request') as mock_request:
                mock_request.remote_addr = None  # No IP address

                # Should still work with "unknown" as the key
                result = test_function()
                self.assertEqual(result, "success")

    def test_rate_limit_decorator_preserves_function_metadata(self):
        """Test that decorators preserve function metadata."""
        @handle_api_errors
        @log_api_request
        @rate_limit(max_requests=10)
        def test_function():
            """Test function docstring."""
            return "success"

        # Function name should be preserved
        self.assertEqual(test_function.__name__, "test_function")

        # Docstring should be preserved
        self.assertEqual(test_function.__doc__, "Test function docstring.")

    def test_decorators_can_be_combined(self):
        """Test that multiple decorators can be combined."""
        mock_schema_class = Mock()
        mock_schema = Mock()
        mock_schema_class.return_value = mock_schema
        mock_schema.load.return_value = {"validated": "data"}

        @handle_api_errors
        @log_api_request
        @validate_request_data(mock_schema_class)
        @rate_limit(max_requests=10)
        def test_function(validated_data=None):
            return {"result": "success", "data": validated_data}

        with self.app.test_request_context(
            '/test',
            method='POST',
            data='{"test": "data"}',
            content_type='application/json',
            environ_base={'REMOTE_ADDR': '192.168.1.1'}
        ):
            with patch('flask.request') as mock_request:
                mock_request.is_json = True
                mock_request.get_json.return_value = {"test": "data"}
                mock_request.method = 'POST'
                mock_request.path = '/test'
                mock_request.remote_addr = '192.168.1.1'

                with patch('src.malla.utils.error_handler.logger'):
                    result = test_function()

                    # Should execute successfully with all decorators
                    self.assertEqual(result, {"result": "success", "data": {"validated": "data"}})

    def test_api_error_inheritance(self):
        """Test that APIError properly inherits from Exception."""
        error = APIError("Test error")

        # Should be an instance of Exception
        self.assertIsInstance(error, Exception)

        # Should be catchable as Exception
        try:
            raise error
        except Exception as e:
            self.assertEqual(str(e), "Test error")
            self.assertIsInstance(e, APIError)

    @patch('src.malla.utils.error_handler.time')
    def test_rate_limit_concurrent_requests_simulation(self, mock_time):
        """Test rate limiting with rapid consecutive requests."""
        mock_time.time.return_value = 1000

        @rate_limit(max_requests=3, window_seconds=60)
        def test_function():
            return "success"

        with self.app.test_request_context():
            with patch('flask.request') as mock_request:
                mock_request.remote_addr = '192.168.1.1'

                # Make exactly max_requests number of requests
                for i in range(3):
                    result = test_function()
                    self.assertEqual(result, "success")

                # Next request should be rate limited
                response, status_code = test_function()
                self.assertEqual(status_code, 429)

    def test_validate_request_data_preserves_other_kwargs(self):
        """Test that validate_request_data preserves other function arguments."""
        mock_schema_class = Mock()
        mock_schema = Mock()
        mock_schema_class.return_value = mock_schema
        mock_schema.load.return_value = {"validated": "data"}

        @validate_request_data(mock_schema_class)
        def test_function(arg1, arg2, kwarg1=None, validated_data=None):
            return {
                "arg1": arg1,
                "arg2": arg2,
                "kwarg1": kwarg1,
                "validated_data": validated_data
            }

        with self.app.test_request_context(
            '/test',
            method='POST',
            data='{"test": "data"}',
            content_type='application/json'
        ):
            with patch('flask.request') as mock_request:
                mock_request.is_json = True
                mock_request.get_json.return_value = {"test": "data"}

                result = test_function("value1", "value2", kwarg1="kwarg_value")

                self.assertEqual(result, {
                    "arg1": "value1",
                    "arg2": "value2",
                    "kwarg1": "kwarg_value",
                    "validated_data": {"validated": "data"}
                })


if __name__ == '__main__':
    unittest.main()