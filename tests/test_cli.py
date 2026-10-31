import json
import sys
import types

import pytest
from click.testing import CliRunner

from wasapi_latency.cli import main

HOSTAPIS = [
    {"name": "MME", "devices": [0, 1], "default_input_device": 1, "default_output_device": 0},
    {
        "name": "Windows WASAPI",
        "devices": [8, 9],
        "default_input_device": 9,
        "default_output_device": 8,
    },
]

DEVICES = {
    8: {
        "name": "Speakers (WASAPI)",
        "index": 8,
        "hostapi": 1,
        "max_input_channels": 0,
        "max_output_channels": 2,
        "default_low_input_latency": 0.0,
        "default_low_output_latency": 0.003,
        "default_high_input_latency": 0.0,
        "default_high_output_latency": 0.01,
        "default_samplerate": 48000.0,
    },
    9: {
        "name": "Mic (WASAPI)",
        "index": 9,
        "hostapi": 1,
        "max_input_channels": 2,
        "max_output_channels": 0,
        "default_low_input_latency": 0.003,
        "default_low_output_latency": 0.0,
        "default_high_input_latency": 0.01,
        "default_high_output_latency": 0.0,
        "default_samplerate": 192000.0,
    },
}


def make_fake_sd():
    mod = types.SimpleNamespace()
    mod.__version__ = "0.5.5"

    def query_hostapis():
        return [dict(h) for h in HOSTAPIS]

    def query_devices(index):
        return dict(DEVICES[index])

    mod.query_hostapis = query_hostapis
    mod.query_devices = query_devices
    return mod


@pytest.fixture
def fake_sd(monkeypatch):
    mod = make_fake_sd()
    import wasapi_latency.cli as cli_mod
    import wasapi_latency.core as core_mod

    monkeypatch.setattr(cli_mod, "sd", mod, raising=False)
    monkeypatch.setattr(core_mod, "sd", mod, raising=False)
    monkeypatch.setitem(sys.modules, "sounddevice", mod)
    return mod


@pytest.fixture
def runner():
    return CliRunner()


def test_info(fake_sd, runner):
    result = runner.invoke(main, ["info"])
    assert result.exit_code == 0, result.output
    assert "Windows WASAPI" in result.output
    assert "Speakers (WASAPI)" in result.output
    assert "Mic (WASAPI)" in result.output
    assert "48000" in result.output
    assert "192000" in result.output


def test_measure_default(fake_sd, runner):
    result = runner.invoke(main, ["measure"])
    assert result.exit_code == 0, result.output
    assert "Speakers (WASAPI)" in result.output
    assert "3.00 ms" in result.output or "3.0 ms" in result.output
    assert "10.00 ms" in result.output or "10.0 ms" in result.output


def test_measure_device(fake_sd, runner):
    result = runner.invoke(main, ["measure", "--device", "9"])
    assert result.exit_code == 0, result.output
    assert "Mic (WASAPI)" in result.output


def test_profiles(fake_sd, runner):
    result = runner.invoke(main, ["profiles"])
    assert result.exit_code == 0, result.output
    for name in ("safe", "balanced", "gaming", "low", "ultra"):
        assert name in result.output
    assert "1024" in result.output
    assert "512" in result.output


def test_recommend_text(fake_sd, runner):
    result = runner.invoke(main, ["recommend", "--profile", "balanced"])
    assert result.exit_code == 0, result.output
    assert "balanced" in result.output
    assert "512" in result.output


def test_recommend_json(fake_sd, runner):
    result = runner.invoke(main, ["recommend", "--profile", "gaming", "--device", "8", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["profile"] == "gaming"
    assert data["frames"] == 256
    assert "ms" in data
    assert data["device"] == 8
    assert "Speakers (WASAPI)" in data["device_name"]


def test_recommend_unknown(fake_sd, runner):
    result = runner.invoke(main, ["recommend", "--profile", "nope"])
    assert result.exit_code != 0


def test_doctor(fake_sd, runner):
    result = runner.invoke(main, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    assert "sounddevice" in result.output.lower()


def test_help(runner):
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "info" in result.output
    assert "measure" in result.output
    assert "profiles" in result.output
    assert "recommend" in result.output
    assert "doctor" in result.output
