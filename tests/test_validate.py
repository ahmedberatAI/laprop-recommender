"""Unit tests for laprop.processing.validate."""

import pytest

from laprop.processing.validate import validate_record


class TestValidateRecord:
    def test_normal_record_no_warnings(self):
        # Title without any RAM candidate > 128 and screen in 10-20 range
        warnings = validate_record(
            title="Laptop i7 FHD 15.6 inch",
            cpu="I7-13700H",
            gpu="RTX 4060",
            ram_gb=16.0,
            ssd_gb=512.0,
            screen_size=15.6,
        )
        assert warnings == []

    def test_ram_over_128_warning(self):
        warnings = validate_record(
            title="Laptop 256GB RAM DDR5",
            cpu="I7-13700H",
            gpu="RTX 4060",
            ram_gb=256.0,
            ssd_gb=512.0,
            screen_size=15.6,
        )
        assert "ram_over_128" in warnings

    def test_screen_size_too_small_warning(self):
        warnings = validate_record(
            title='Laptop 8" mini tablet',
            cpu="I5-1335U",
            gpu="integrated",
            ram_gb=8.0,
            ssd_gb=256.0,
            screen_size=8.0,
        )
        assert "screen_size_out_of_range" in warnings

    def test_screen_size_too_large_warning(self):
        warnings = validate_record(
            title='Laptop 22" monitor-like',
            cpu="I5-1335U",
            gpu="integrated",
            ram_gb=8.0,
            ssd_gb=256.0,
            screen_size=22.0,
        )
        assert "screen_size_out_of_range" in warnings

    def test_none_values_no_crash(self):
        warnings = validate_record(
            title="Simple Laptop",
            cpu=None,
            gpu=None,
            ram_gb=None,
            ssd_gb=None,
            screen_size=None,
        )
        assert isinstance(warnings, list)
