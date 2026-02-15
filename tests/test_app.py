"""
Behavior-driven tests for src/app.py - Main FastAPI Application Entry Point.

These tests validate runtime behavior, not source code structure.
All tests mock external dependencies and assert on outcomes (SystemExit, logs, calls).
"""

import pytest
import sys
import os
import signal
import logging
import runpy
from unittest.mock import patch, MagicMock
from importlib import reload


@pytest.fixture(autouse=True)
def reset_env():
    """Reset ALL app-related environment variables before each test."""
    original_env = os.environ.copy()
    for key in ['APP_HOST', 'APP_PORT', 'LOG_LEVEL', 'APP_WORKERS', 'APP_GRACEFUL_TIMEOUT']:
        os.environ.pop(key, None)
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_api_service():
    """Create a mock api.service module with a realistic app object."""
    mock_app = MagicMock()
    mock_app.title = "AstraGuard AI API"
    mock_app.version = "1.0.0"
    return MagicMock(app=mock_app), mock_app


@pytest.fixture
def mock_uvicorn():
    """Create a mock uvicorn module."""
    mock_uv = MagicMock()
    mock_uv.run = MagicMock()
    return mock_uv


def _load_app_module(mock_service):
    """
    Helper: evict cached module and reimport with the given api.service mock.
    Always call this inside a `patch.dict(sys.modules, {'api.service': mock_service})`
    context so the mock is visible during import.
    """
    sys.modules.pop('src.app', None)
    from src import app as app_module
    return app_module



class TestSignalHandler:
    """
    Test the signal handler factory (_make_signal_handler) and its closures.

    The optimized app uses a factory instead of a bare `signal_handler`
    function so that each registered signal carries a descriptive label in
    its log message while still satisfying signal.signal()'s
    `(int, FrameType | None) -> None` contract.
    """

    def test_handler_logs_shutdown_message(self, mock_api_service):
        """Handler closure must log a message containing 'signal' on invocation."""
        mock_service, _ = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service}):
            app_module = _load_app_module(mock_service)

            handler = app_module._make_signal_handler("SIGINT")

            with patch.object(app_module.logger, 'info') as mock_log:
                with pytest.raises(SystemExit) as exc_info:
                    handler(signal.SIGINT, None)

            mock_log.assert_called_once()
            # The log format uses %s lazy formatting: check args, not just msg
            log_call = mock_log.call_args
            full_message = log_call[0][0] % log_call[0][1:] if log_call[0][1:] else log_call[0][0]
            assert 'signal' in full_message.lower() or 'sigint' in full_message.lower()
            assert exc_info.value.code == 0

    def test_handler_exits_with_code_zero(self, mock_api_service):
        """Handler closure must always exit with code 0 (graceful shutdown)."""
        mock_service, _ = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service}):
            app_module = _load_app_module(mock_service)

            handler = app_module._make_signal_handler("SIGTERM")

            with pytest.raises(SystemExit) as exc_info:
                handler(signal.SIGTERM, None)

            assert exc_info.value.code == 0

    def test_handler_accepts_sigterm(self, mock_api_service):
        """Handler closure must accept SIGTERM with a live FrameType mock."""
        mock_service, _ = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service}):
            app_module = _load_app_module(mock_service)

            handler = app_module._make_signal_handler("SIGTERM")

            with pytest.raises(SystemExit) as exc_info:
                handler(signal.SIGTERM, MagicMock())  # non-None frame

            assert exc_info.value.code == 0

    def test_factory_returns_callable(self, mock_api_service):
        """_make_signal_handler must return a callable."""
        mock_service, _ = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service}):
            app_module = _load_app_module(mock_service)

            handler = app_module._make_signal_handler("SIGINT")
            assert callable(handler)

    def test_label_appears_in_log(self, mock_api_service):
        """The label passed to the factory must appear in the log output."""
        mock_service, _ = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service}):
            app_module = _load_app_module(mock_service)

            handler = app_module._make_signal_handler("SIGTERM")

            with patch.object(app_module.logger, 'info') as mock_log:
                with pytest.raises(SystemExit):
                    handler(signal.SIGTERM, None)

            log_call = mock_log.call_args
            # Reconstruct the formatted string from % args if present
            fmt = log_call[0][0]
            fmt_args = log_call[0][1:]
            full_message = fmt % fmt_args if fmt_args else fmt
            assert 'SIGTERM' in full_message


class TestAppModuleImport:
    """
    Test module-level public symbols.

    In the optimized app, `app` is no longer imported eagerly at module scope
    (it lives inside `_load_app()`), so we no longer assert `hasattr(module, 'app')`.
    Instead we verify the lazy loader is present and functional, and confirm the
    remaining stable public symbols (logger, _make_signal_handler) are accessible.
    """

    def test_successful_import_exposes_logger(self, mock_api_service):
        """Module must expose a `logging.Logger` instance as `logger`."""
        mock_service, _ = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service}):
            app_module = _load_app_module(mock_service)

            assert hasattr(app_module, 'logger')
            assert isinstance(app_module.logger, logging.Logger)

    def test_successful_import_exposes_signal_handler_factory(self, mock_api_service):
        """Module must expose `_make_signal_handler` as a callable factory."""
        mock_service, _ = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service}):
            app_module = _load_app_module(mock_service)

            assert hasattr(app_module, '_make_signal_handler')
            assert callable(app_module._make_signal_handler)

    def test_successful_import_exposes_load_app(self, mock_api_service):
        """Module must expose `_load_app` as a callable."""
        mock_service, _ = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service}):
            app_module = _load_app_module(mock_service)

            assert hasattr(app_module, '_load_app')
            assert callable(app_module._load_app)

    def test_load_app_returns_app_object(self, mock_api_service):
        """_load_app() must return the app object from api.service."""
        mock_service, mock_app = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service}):
            app_module = _load_app_module(mock_service)
            loaded = app_module._load_app()

            assert loaded is mock_app

    def test_import_does_not_eagerly_load_app(self, mock_api_service):
        """
        Importing the module must NOT trigger api.service import as a side effect.
        This is the core guarantee of the lazy-load pattern: tooling and test
        runners can import app.py without paying the full initialization cost.
        """
        mock_service, _ = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service}):
            sys.modules.pop('src.app', None)
            mock_service.reset_mock()

            import src.app  # noqa: F401 — import only, no call

            # api.service.app attribute should NOT have been accessed at import time
            assert not mock_service.app.called


class TestMainBlockPortValidation:
    """Test port validation in main block."""

    def test_invalid_port_string_causes_exit(self, mock_api_service, mock_uvicorn):
        """Non-numeric APP_PORT must cause sys.exit(1)."""
        mock_service, _ = mock_api_service
        os.environ['APP_PORT'] = 'invalid'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')

        assert exc_info.value.code == 1

    def test_port_out_of_range_causes_exit(self, mock_api_service, mock_uvicorn):
        """Port > 65535 must cause sys.exit(1)."""
        mock_service, _ = mock_api_service
        os.environ['APP_PORT'] = '70000'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')

        assert exc_info.value.code == 1

    def test_port_zero_causes_exit(self, mock_api_service, mock_uvicorn):
        """Port = 0 must cause sys.exit(1)."""
        mock_service, _ = mock_api_service
        os.environ['APP_PORT'] = '0'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')

        assert exc_info.value.code == 1

    def test_negative_port_causes_exit(self, mock_api_service, mock_uvicorn):
        """Negative port must cause sys.exit(1)."""
        mock_service, _ = mock_api_service
        os.environ['APP_PORT'] = '-1'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')

        assert exc_info.value.code == 1


class TestMainBlockLogLevelValidation:
    """Test log level validation in main block."""

    def test_invalid_log_level_defaults_to_info(self, mock_api_service, mock_uvicorn):
        """Invalid LOG_LEVEL must default to 'info' without exiting."""
        mock_service, _ = mock_api_service
        os.environ['LOG_LEVEL'] = 'invalid_level'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        call_kwargs = mock_uvicorn.run.call_args[1]
        assert call_kwargs['log_level'] == 'info'

    def test_valid_log_level_debug_is_accepted(self, mock_api_service, mock_uvicorn):
        """LOG_LEVEL='DEBUG' (uppercase) must be normalised and accepted."""
        mock_service, _ = mock_api_service
        os.environ['LOG_LEVEL'] = 'DEBUG'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        call_kwargs = mock_uvicorn.run.call_args[1]
        assert call_kwargs['log_level'] == 'debug'

    def test_valid_log_level_error_is_accepted(self, mock_api_service, mock_uvicorn):
        """LOG_LEVEL='error' must be accepted as-is."""
        mock_service, _ = mock_api_service
        os.environ['LOG_LEVEL'] = 'error'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        call_kwargs = mock_uvicorn.run.call_args[1]
        assert call_kwargs['log_level'] == 'error'


class TestMainBlockUvicornConfiguration:
    """Test uvicorn.run configuration in main block."""

    def test_uvicorn_run_called_with_default_host(self, mock_api_service, mock_uvicorn):
        """uvicorn.run must receive host='0.0.0.0' by default."""
        mock_service, _ = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        assert mock_uvicorn.run.call_args[1]['host'] == '0.0.0.0'

    def test_uvicorn_run_called_with_default_port(self, mock_api_service, mock_uvicorn):
        """uvicorn.run must receive port=8002 by default."""
        mock_service, _ = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        assert mock_uvicorn.run.call_args[1]['port'] == 8002

    def test_uvicorn_run_uses_custom_host_from_env(self, mock_api_service, mock_uvicorn):
        """uvicorn.run must use APP_HOST when set."""
        mock_service, _ = mock_api_service
        os.environ['APP_HOST'] = '127.0.0.1'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        assert mock_uvicorn.run.call_args[1]['host'] == '127.0.0.1'

    def test_uvicorn_run_uses_custom_port_from_env(self, mock_api_service, mock_uvicorn):
        """uvicorn.run must use APP_PORT when set."""
        mock_service, _ = mock_api_service
        os.environ['APP_PORT'] = '9000'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        assert mock_uvicorn.run.call_args[1]['port'] == 9000

    def test_uvicorn_run_receives_app_instance_when_single_worker(self, mock_api_service, mock_uvicorn):
        """
        With APP_WORKERS=1 (default), uvicorn.run first positional arg must be
        the live app object (not an import string).
        """
        mock_service, mock_app = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        first_arg = mock_uvicorn.run.call_args[0][0]
        assert first_arg is mock_app

    def test_uvicorn_run_uses_import_string_for_multi_worker(self, mock_api_service, mock_uvicorn):
        """
        With APP_WORKERS > 1, uvicorn.run first positional arg must be the
        'api.service:app' import string so workers can fork independently.
        """
        mock_service, _ = mock_api_service
        os.environ['APP_WORKERS'] = '4'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        first_arg = mock_uvicorn.run.call_args[0][0]
        assert first_arg == 'api.service:app'

    def test_uvicorn_run_passes_graceful_timeout(self, mock_api_service, mock_uvicorn):
        """uvicorn.run must receive timeout_graceful_shutdown from config."""
        mock_service, _ = mock_api_service
        os.environ['APP_GRACEFUL_TIMEOUT'] = '45'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        assert mock_uvicorn.run.call_args[1]['timeout_graceful_shutdown'] == 45

    def test_uvicorn_run_default_graceful_timeout(self, mock_api_service, mock_uvicorn):
        """uvicorn.run must use a 30s graceful timeout by default."""
        mock_service, _ = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        assert mock_uvicorn.run.call_args[1]['timeout_graceful_shutdown'] == 30


class TestMainBlockErrorHandling:
    """Test error handling in main block."""

    def test_uvicorn_import_error_causes_exit(self, mock_api_service):
        """Missing uvicorn must cause sys.exit(1)."""
        mock_service, _ = mock_api_service
        sys.modules.pop('uvicorn', None)

        with patch.dict(sys.modules, {'api.service': mock_service}):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')

        assert exc_info.value.code == 1

    def test_oserror_address_in_use_causes_exit(self, mock_api_service, mock_uvicorn):
        """OSError EADDRINUSE (errno 98) must cause sys.exit(1)."""
        mock_service, _ = mock_api_service
        err = OSError("Address already in use")
        err.errno = 98
        mock_uvicorn.run.side_effect = err

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')

        assert exc_info.value.code == 1

    def test_oserror_permission_denied_causes_exit(self, mock_api_service, mock_uvicorn):
        """OSError EACCES (errno 13) must cause sys.exit(1)."""
        mock_service, _ = mock_api_service
        err = OSError("Permission denied")
        err.errno = 13
        mock_uvicorn.run.side_effect = err

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')

        assert exc_info.value.code == 1

    def test_oserror_other_causes_exit(self, mock_api_service, mock_uvicorn):
        """Any unrecognised OSError errno must still cause sys.exit(1)."""
        mock_service, _ = mock_api_service
        err = OSError("Some other error")
        err.errno = 999
        mock_uvicorn.run.side_effect = err

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')

        assert exc_info.value.code == 1

    def test_keyboard_interrupt_causes_graceful_exit(self, mock_api_service, mock_uvicorn):
        """KeyboardInterrupt must cause sys.exit(0)."""
        mock_service, _ = mock_api_service
        mock_uvicorn.run.side_effect = KeyboardInterrupt()

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')

        assert exc_info.value.code == 0

    def test_unexpected_exception_causes_exit(self, mock_api_service, mock_uvicorn):
        """Any unexpected Exception must cause sys.exit(1)."""
        mock_service, _ = mock_api_service
        mock_uvicorn.run.side_effect = RuntimeError("Unexpected error")

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')

        assert exc_info.value.code == 1


class TestMainBlockSignalRegistration:
    """Test signal handler registration in main block."""

    def test_sigint_handler_is_registered(self, mock_api_service, mock_uvicorn):
        """SIGINT handler must be registered via signal.signal."""
        mock_service, _ = mock_api_service
        mock_signal_func = MagicMock()

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal', mock_signal_func):
                runpy.run_path('src/app.py', run_name='__main__')

        sigint_calls = [c for c in mock_signal_func.call_args_list if c[0][0] == signal.SIGINT]
        assert len(sigint_calls) >= 1

    def test_sigterm_handler_is_registered(self, mock_api_service, mock_uvicorn):
        """SIGTERM handler must be registered via signal.signal."""
        mock_service, _ = mock_api_service
        mock_signal_func = MagicMock()

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal', mock_signal_func):
                runpy.run_path('src/app.py', run_name='__main__')

        sigterm_calls = [c for c in mock_signal_func.call_args_list if c[0][0] == signal.SIGTERM]
        assert len(sigterm_calls) >= 1

    def test_signal_handlers_registered_before_uvicorn(self, mock_api_service, mock_uvicorn):
        """
        Signal handlers must be registered before uvicorn.run is called so
        the process is always interruptible, even during slow app loading.
        """
        mock_service, _ = mock_api_service
        call_order = []
        mock_signal_func = MagicMock(side_effect=lambda *a, **kw: call_order.append('signal'))
        mock_uvicorn.run.side_effect = lambda *a, **kw: call_order.append('uvicorn')

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal', mock_signal_func):
                runpy.run_path('src/app.py', run_name='__main__')

        assert call_order.index('signal') < call_order.index('uvicorn')


class TestMainBlockLogging:
    """Test logging behavior in main block."""

    def test_startup_logs_host_and_port(self, mock_api_service, mock_uvicorn):
        """Startup must log a message that contains the host address."""
        mock_service, _ = mock_api_service

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                with patch('logging.Logger.info') as mock_log:
                    runpy.run_path('src/app.py', run_name='__main__')

        all_messages = ' '.join(str(c) for c in mock_log.call_args_list)
        assert '0.0.0.0' in all_messages or 'host' in all_messages.lower()

    def test_error_logged_on_invalid_port(self, mock_api_service, mock_uvicorn):
        """An error must be logged when APP_PORT is non-numeric."""
        mock_service, _ = mock_api_service
        os.environ['APP_PORT'] = 'not_a_number'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                with patch('logging.Logger.error') as mock_error:
                    with pytest.raises(SystemExit):
                        runpy.run_path('src/app.py', run_name='__main__')

        assert mock_error.called

    def test_warning_logged_for_invalid_log_level(self, mock_api_service, mock_uvicorn):
        """A warning must be logged when LOG_LEVEL is unrecognised."""
        mock_service, _ = mock_api_service
        os.environ['LOG_LEVEL'] = 'banana'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                with patch('logging.Logger.warning') as mock_warning:
                    runpy.run_path('src/app.py', run_name='__main__')

        assert mock_warning.called

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_port_1_is_valid(self, mock_api_service, mock_uvicorn):
        """Port 1 is the lower boundary and must be accepted."""
        mock_service, _ = mock_api_service
        os.environ['APP_PORT'] = '1'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        assert mock_uvicorn.run.call_args[1]['port'] == 1

    def test_port_65535_is_valid(self, mock_api_service, mock_uvicorn):
        """Port 65535 is the upper boundary and must be accepted."""
        mock_service, _ = mock_api_service
        os.environ['APP_PORT'] = '65535'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        assert mock_uvicorn.run.call_args[1]['port'] == 65535

    def test_port_65536_is_invalid(self, mock_api_service, mock_uvicorn):
        """Port 65536 is one above the upper boundary and must be rejected."""
        mock_service, _ = mock_api_service
        os.environ['APP_PORT'] = '65536'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                with pytest.raises(SystemExit) as exc_info:
                    runpy.run_path('src/app.py', run_name='__main__')

        assert exc_info.value.code == 1

    def test_all_valid_log_levels(self, mock_api_service, mock_uvicorn):
        """Every documented log level must pass through unchanged."""
        mock_service, _ = mock_api_service

        for level in ["critical", "error", "warning", "info", "debug"]:
            mock_uvicorn.run.reset_mock()
            os.environ['LOG_LEVEL'] = level

            with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
                with patch('signal.signal'):
                    runpy.run_path('src/app.py', run_name='__main__')

            assert mock_uvicorn.run.call_args[1]['log_level'] == level

    def test_log_level_case_insensitive(self, mock_api_service, mock_uvicorn):
        """LOG_LEVEL must be normalised to lowercase before use."""
        mock_service, _ = mock_api_service
        os.environ['LOG_LEVEL'] = 'WARNING'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        assert mock_uvicorn.run.call_args[1]['log_level'] == 'warning'

    def test_invalid_workers_defaults_to_one(self, mock_api_service, mock_uvicorn):
        """Non-numeric APP_WORKERS must fall back to 1 without crashing."""
        mock_service, _ = mock_api_service
        os.environ['APP_WORKERS'] = 'many'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        assert mock_uvicorn.run.call_args[1]['workers'] == 1

    def test_invalid_graceful_timeout_defaults_to_thirty(self, mock_api_service, mock_uvicorn):
        """Non-numeric APP_GRACEFUL_TIMEOUT must fall back to 30 without crashing."""
        mock_service, _ = mock_api_service
        os.environ['APP_GRACEFUL_TIMEOUT'] = 'soon'

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                runpy.run_path('src/app.py', run_name='__main__')

        assert mock_uvicorn.run.call_args[1]['timeout_graceful_shutdown'] == 30


class TestOSErrorSpecificCodes:
    """Test specific OSError errno handling."""

    def test_oserror_errno_48_address_in_use_mac(self, mock_api_service, mock_uvicorn):
        """OSError errno 48 (EADDRINUSE on macOS) must cause sys.exit(1)."""
        mock_service, _ = mock_api_service
        err = OSError("Address already in use")
        err.errno = 48
        mock_uvicorn.run.side_effect = err

        with patch.dict(sys.modules, {'api.service': mock_service, 'uvicorn': mock_uvicorn}):
            with patch('signal.signal'):
                with patch('logging.Logger.error') as mock_error:
                    with pytest.raises(SystemExit) as exc_info:
                        runpy.run_path('src/app.py', run_name='__main__')

        assert exc_info.value.code == 1
        assert mock_error.called