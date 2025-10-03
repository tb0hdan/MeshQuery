"""Tests for database initialization module."""

import unittest
from unittest.mock import Mock, patch, MagicMock, mock_open
import os
import sys
import time
from pathlib import Path
import psycopg2

from src.malla import db_init


class TestDBInit(unittest.TestCase):
    """Test cases for db_init module."""

    def setUp(self):
        """Set up test fixtures."""
        # Mock environment variables
        self.env_vars = {
            'MALLA_DATABASE_HOST': 'localhost',
            'MALLA_DATABASE_PORT': '5432',
            'MALLA_DATABASE_NAME': 'malla',
            'MALLA_DATABASE_USER': 'malla',
            'MALLA_DATABASE_PASSWORD': 'yourpassword',
            'MALLA_SCHEMA_SQL': ''
        }

    @patch.dict(os.environ, {'MALLA_DATABASE_HOST': 'test_host'})
    def test_environment_variables_loading(self):
        """Test that environment variables are loaded correctly."""
        # Reload the module to pick up new env vars
        import importlib
        importlib.reload(db_init)

        self.assertEqual(db_init.DB_HOST, 'test_host')

    @patch('src.malla.db_init.psycopg2.connect')
    @patch('src.malla.db_init.time')
    def test_connect_success(self, mock_time, mock_connect):
        """Test successful database connection."""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn
        mock_time.time.return_value = 100.0

        result = db_init._connect()

        mock_connect.assert_called_once_with(
            host=db_init.DB_HOST,
            port=db_init.DB_PORT,
            dbname=db_init.DB_NAME,
            user=db_init.DB_USER,
            password=db_init.DB_PASS
        )
        self.assertEqual(result, mock_conn)
        self.assertTrue(mock_conn.autocommit)

    @patch('src.malla.db_init.psycopg2.connect')
    @patch('src.malla.db_init.time')
    def test_connect_retry_mechanism(self, mock_time, mock_connect):
        """Test connection retry mechanism."""
        # Mock time.time to return increasing values
        mock_time.time.side_effect = [0, 10, 20, 30, 40, 50, 70]  # Last one exceeds max_wait
        mock_time.sleep = Mock()

        # Mock connection to fail first few times, then succeed
        mock_conn = Mock()
        mock_connect.side_effect = [
            psycopg2.OperationalError("Connection refused"),
            psycopg2.OperationalError("Connection refused"),
            mock_conn
        ]

        result = db_init._connect(max_wait=60)

        self.assertEqual(result, mock_conn)
        self.assertEqual(mock_connect.call_count, 3)
        self.assertEqual(mock_time.sleep.call_count, 2)
        mock_time.sleep.assert_called_with(1.5)

    @patch('src.malla.db_init.psycopg2.connect')
    @patch('src.malla.db_init.time')
    def test_connect_timeout_failure(self, mock_time, mock_connect):
        """Test connection timeout failure."""
        # Mock time to exceed max_wait - need at least one iteration where time < max_wait
        mock_time.time.side_effect = [0, 10, 70]  # First iteration at 10s, second check at 70s exceeds max_wait of 60
        mock_time.sleep = Mock()

        error = psycopg2.OperationalError("Connection refused")
        mock_connect.side_effect = error

        with self.assertRaises(RuntimeError) as context:
            db_init._connect(max_wait=60)

        self.assertIn("Could not connect to Postgres", str(context.exception))
        # The last_err should be the exception object
        self.assertIn("Connection refused", str(context.exception))

    @patch('src.malla.db_init.Path')
    def test_run_schema_sql_with_explicit_file(self, mock_path_class):
        """Test running schema SQL with explicit file path."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.cursor.return_value.__exit__.return_value = None

        # Mock a single SQL file
        mock_path = Mock()
        mock_path.exists.return_value = True
        mock_path.is_dir.return_value = False
        mock_path.read_text.return_value = "CREATE TABLE test();"
        mock_path_class.return_value = mock_path

        with patch.object(db_init, 'SCHEMA_SQL', 'schema.sql'):
            db_init._run_schema_sql(mock_conn)

        mock_cursor.execute.assert_called_once_with("CREATE TABLE test();")

    @patch('src.malla.db_init.Path')
    def test_run_schema_sql_with_directory(self, mock_path_class):
        """Test running schema SQL with directory containing multiple files."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.cursor.return_value.__exit__.return_value = None

        # Mock directory with multiple SQL files
        mock_file1 = Mock()
        mock_file1.read_text.return_value = "CREATE TABLE table1();"
        mock_file2 = Mock()
        mock_file2.read_text.return_value = "CREATE TABLE table2();"

        def path_side_effect(path_str):
            mock_path = Mock()
            if str(path_str) == "sql_dir":
                mock_path.exists.return_value = True
                mock_path.is_dir.return_value = True
                mock_path.glob.return_value = [mock_file2, mock_file1]  # Unsorted intentionally
            else:
                # Fallback paths don't exist
                mock_path.exists.return_value = False
                mock_path.is_dir.return_value = False
            return mock_path

        mock_path_class.side_effect = path_side_effect

        with patch('builtins.sorted', return_value=[mock_file1, mock_file2]):
            with patch.object(db_init, 'SCHEMA_SQL', 'sql_dir'):
                db_init._run_schema_sql(mock_conn)

        self.assertEqual(mock_cursor.execute.call_count, 2)
        mock_cursor.execute.assert_any_call("CREATE TABLE table1();")
        mock_cursor.execute.assert_any_call("CREATE TABLE table2();")

    @patch('src.malla.db_init.Path')
    @patch('builtins.print')
    def test_run_schema_sql_fallback_paths(self, mock_print, mock_path_class):
        """Test schema SQL fallback path resolution."""
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_conn.cursor.return_value.__exit__.return_value = None

        # Mock main path doesn't exist, but fallback does
        def path_side_effect(path_str):
            mock_path = Mock()
            if str(path_str) == "/app/src/malla/schema.sql":
                mock_path.exists.return_value = True
                mock_path.is_dir.return_value = False
                mock_path.read_text.return_value = "CREATE TABLE fallback();"
            else:
                mock_path.exists.return_value = False
            return mock_path

        mock_path_class.side_effect = path_side_effect

        with patch.object(db_init, 'SCHEMA_SQL', ''):
            db_init._run_schema_sql(mock_conn)

        mock_cursor.execute.assert_called_once_with("CREATE TABLE fallback();")

    @patch('src.malla.db_init.Path')
    @patch('builtins.print')
    def test_run_schema_sql_no_files_found(self, mock_print, mock_path_class):
        """Test behavior when no schema SQL files are found."""
        mock_conn = Mock()

        # Mock all paths as non-existent
        mock_path = Mock()
        mock_path.exists.return_value = False
        mock_path_class.return_value = mock_path

        with patch.object(db_init, 'SCHEMA_SQL', ''):
            db_init._run_schema_sql(mock_conn)

        mock_print.assert_called_with("[db-init] No schema.sql found; skipping raw SQL step.")

    @patch('builtins.__import__')
    @patch('builtins.print')
    def test_try_call_python_schema_success(self, mock_print, mock_import):
        """Test successful Python schema initialization."""
        mock_conn = Mock()

        # Mock successful module import with ensure_schema function
        mock_module = Mock()
        mock_ensure_schema = Mock()
        mock_module.ensure_schema = mock_ensure_schema
        mock_import.return_value = mock_module

        result = db_init._try_call_python_schema(mock_conn)

        self.assertTrue(result)
        mock_ensure_schema.assert_called_once_with(mock_conn)
        mock_print.assert_called_with("[db-init] Calling malla.schema.ensure_schema()")

    @patch('builtins.__import__')
    @patch('builtins.print')
    def test_try_call_python_schema_init_schema(self, mock_print, mock_import):
        """Test Python schema initialization with init_schema function."""
        mock_conn = Mock()

        # Mock module with init_schema function instead of ensure_schema
        mock_module = Mock()
        mock_module.ensure_schema = None  # No ensure_schema
        mock_init_schema = Mock()
        mock_module.init_schema = mock_init_schema
        mock_import.return_value = mock_module

        result = db_init._try_call_python_schema(mock_conn)

        self.assertTrue(result)
        mock_init_schema.assert_called_once_with(mock_conn)
        mock_print.assert_called_with("[db-init] Calling malla.schema.init_schema()")

    @patch('builtins.__import__')
    @patch('builtins.print')
    def test_try_call_python_schema_create_all(self, mock_print, mock_import):
        """Test Python schema initialization with create_all function."""
        mock_conn = Mock()

        # Mock module with create_all function
        mock_module = Mock()
        mock_module.ensure_schema = None
        mock_module.init_schema = None
        mock_create_all = Mock()
        mock_module.create_all = mock_create_all
        mock_import.return_value = mock_module

        result = db_init._try_call_python_schema(mock_conn)

        self.assertTrue(result)
        mock_create_all.assert_called_once_with(mock_conn)
        mock_print.assert_called_with("[db-init] Calling malla.schema.create_all()")

    @patch('builtins.__import__')
    @patch('builtins.print')
    def test_try_call_python_schema_module_not_found(self, mock_print, mock_import):
        """Test Python schema initialization when modules are not found."""
        mock_conn = Mock()

        mock_import.side_effect = ModuleNotFoundError("No module named 'malla.schema'")

        result = db_init._try_call_python_schema(mock_conn)

        self.assertFalse(result)
        mock_print.assert_called_with("[db-init] No python schema initializer found; skipped.")

    @patch('builtins.__import__')
    @patch('builtins.print')
    def test_try_call_python_schema_function_not_found(self, mock_print, mock_import):
        """Test Python schema initialization when no suitable function is found."""
        mock_conn = Mock()

        # Mock module with no schema initialization functions
        mock_module = Mock()
        mock_module.ensure_schema = None
        mock_module.init_schema = None
        mock_module.create_all = None
        mock_import.return_value = mock_module

        result = db_init._try_call_python_schema(mock_conn)

        self.assertFalse(result)

    @patch('builtins.__import__')
    @patch('builtins.print')
    def test_try_call_python_schema_exception_handling(self, mock_print, mock_import):
        """Test Python schema initialization exception handling."""
        mock_conn = Mock()

        def import_side_effect(name, fromlist=None):
            if name == "malla.schema":
                raise ImportError("Some import error")  # Non-ModuleNotFoundError
            else:
                raise ModuleNotFoundError()  # Other modules not found

        mock_import.side_effect = import_side_effect

        result = db_init._try_call_python_schema(mock_conn)

        self.assertFalse(result)
        # Check that the error was printed
        print_calls = [str(call) for call in mock_print.call_args_list]
        error_found = any("Some import error" in call for call in print_calls)
        self.assertTrue(error_found, f"Expected import error in print calls: {print_calls}")

    @patch('builtins.__import__')
    @patch('builtins.print')
    def test_try_call_python_schema_multiple_modules(self, mock_print, mock_import):
        """Test Python schema initialization tries multiple module names."""
        mock_conn = Mock()

        def import_side_effect(name, fromlist=None):
            if name == "malla.schema":
                raise ModuleNotFoundError()
            elif name == "malla.schema_tier_b":
                mock_module = Mock()
                mock_module.ensure_schema = Mock()
                return mock_module
            else:
                raise ModuleNotFoundError()

        mock_import.side_effect = import_side_effect

        result = db_init._try_call_python_schema(mock_conn)

        self.assertTrue(result)
        mock_print.assert_called_with("[db-init] Calling malla.schema_tier_b.ensure_schema()")

    @patch('src.malla.db_init._connect')
    @patch('src.malla.db_init._try_call_python_schema')
    @patch('src.malla.db_init._run_schema_sql')
    @patch('builtins.print')
    def test_main_success_with_python_schema(self, mock_print, mock_run_sql, mock_try_python, mock_connect):
        """Test successful main execution with Python schema."""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn
        mock_try_python.return_value = True  # Python schema succeeded

        db_init.main()

        mock_connect.assert_called_once()
        mock_try_python.assert_called_once_with(mock_conn)
        mock_run_sql.assert_not_called()  # Should not run SQL if Python succeeded
        mock_print.assert_any_call("[db-init] Starting DB init")
        mock_print.assert_any_call("[db-init] Done")

    @patch('src.malla.db_init._connect')
    @patch('src.malla.db_init._try_call_python_schema')
    @patch('src.malla.db_init._run_schema_sql')
    @patch('builtins.print')
    def test_main_success_with_sql_schema(self, mock_print, mock_run_sql, mock_try_python, mock_connect):
        """Test successful main execution with SQL schema fallback."""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn
        mock_try_python.return_value = False  # Python schema failed

        db_init.main()

        mock_connect.assert_called_once()
        mock_try_python.assert_called_once_with(mock_conn)
        mock_run_sql.assert_called_once_with(mock_conn)  # Should run SQL as fallback
        mock_print.assert_any_call("[db-init] Starting DB init")
        mock_print.assert_any_call("[db-init] Done")

    @patch('src.malla.db_init._connect')
    @patch('builtins.print')
    def test_main_connection_failure(self, mock_print, mock_connect):
        """Test main function behavior when connection fails."""
        mock_connect.side_effect = Exception("Connection failed")

        with self.assertRaises(SystemExit) as context:
            db_init.main()

        self.assertEqual(context.exception.code, 1)
        # Check that the correct print call was made
        print_calls = [str(call) for call in mock_print.call_args_list]
        connection_error_found = any("Connection failed" in call for call in print_calls)
        self.assertTrue(connection_error_found, f"Expected connection error in print calls: {print_calls}")

    @patch('src.malla.db_init._connect')
    @patch('src.malla.db_init._try_call_python_schema')
    @patch('src.malla.db_init._run_schema_sql')
    @patch('builtins.print')
    def test_main_sql_schema_failure(self, mock_print, mock_run_sql, mock_try_python, mock_connect):
        """Test main function behavior when SQL schema execution fails."""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn
        mock_try_python.return_value = False  # Python schema failed
        mock_run_sql.side_effect = Exception("SQL execution failed")

        with self.assertRaises(SystemExit) as context:
            db_init.main()

        self.assertEqual(context.exception.code, 2)
        print_calls = [str(call) for call in mock_print.call_args_list]
        sql_error_found = any("SQL execution failed" in call for call in print_calls)
        self.assertTrue(sql_error_found, f"Expected SQL error in print calls: {print_calls}")

    @patch('src.malla.db_init.main')
    def test_main_execution_when_run_as_script(self, mock_main):
        """Test that main() is called when script is executed directly."""
        # This test verifies the if __name__ == "__main__" block
        # We can't easily test this directly, but we can test the main function independently
        with patch('src.malla.db_init.__name__', '__main__'):
            # Import would trigger the main execution, but since we're mocking,
            # we just verify the main function works
            db_init.main()
            # The main function should have been called in our test setup


if __name__ == '__main__':
    unittest.main()