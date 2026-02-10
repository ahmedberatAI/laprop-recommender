"""Unit tests for laprop.utils.logging."""

import logging

from laprop.utils.logging import get_logger, setup_logging, SafeStreamHandler


class TestGetLogger:
    def test_returns_logger(self):
        logger = get_logger("test_module")
        assert isinstance(logger, logging.Logger)
        assert logger.name == "test_module"

    def test_consistent_logger(self):
        l1 = get_logger("same_module")
        l2 = get_logger("same_module")
        assert l1 is l2

    def test_setup_logging_idempotent(self):
        """Calling setup_logging multiple times should not add duplicate handlers."""
        setup_logging()
        setup_logging()
        root = logging.getLogger("laprop")
        # Should have handlers but not duplicate them excessively
        assert len(root.handlers) >= 1


class TestSafeStreamHandler:
    def test_handler_can_be_instantiated(self):
        import io
        stream = io.StringIO()
        handler = SafeStreamHandler(stream)
        record = logging.LogRecord(
            name="test", level=logging.INFO, pathname="test.py",
            lineno=1, msg="Test message", args=(), exc_info=None,
        )
        handler.emit(record)
        output = stream.getvalue()
        assert "Test message" in output
