import csv
import io
import json
import types

import pytest
from click.testing import CliRunner

from wasapi_latency import core
from wasapi_latency.cli import main

HOSTAPIS = [
    {"name": "MME", "devices": [0, 1], "default_input_device": 1, "default_output_device": 0},
    {"name": "Windows WASAPI", "devices": [2, 3, 4], "default_input_device": 3, "default_output_device": 2},
    {"name": "Windows WDM-KS", "devices": [5], "default_input_device": -1, "default_output_device": -1},
]

DEVICES = {
    0: {
        "name": "Speakers (MME)",
        "hostapi": 0,
        "max_input_channels": 0,
        "max_output_channels": 2,
        "default_samplerate": 44100.0,
        "default_low_output_latency": 0.03,
        "default_high_output_latency": 0.06,
    },
    1: {
        "name": "Microphone (MME)",
        "hostapi": 0,
        "max_input_channels": 1,
        "max_output_channels": 0,
        "default_samplerate": 44100.0,
        "default_low_input_latency": 0.03,
        "default_high_input_latency": 0.06,
    },
    2: {
        "name": "Speakers (WASAPI)",
        "hostapi": 1,
        "max_input_channels": 0,
        "max_output_channels": 2,
        "default_samplerate": 48000.0,
        "default_low_output_latency": 0.003,
        "default_high_output_latency": 0.01,
    },
    3: {
        "name": "Microphone (WASAPI)",
        "hostapi": 1,
        "max_input_channels": 2,
        "max_output_channels": 0,
        "default_samplerate": 192000.0,
        "default_low_input_latency": 0.003,
        "default_high_input_latency": 0.01,
    },
    4: {
        "name": "Headphones, USB (WASAPI)",
        "hostapi": 1,
        "max_input_channels": 0,
        "max_output_channels": 2,
        "default_samplerate": 44100.0,
        "default_low_output_latency": 0.005,
        "default_high_output_latency": 0.02,
    },
    5: {
        "name": "S/PDIF (WDM-KS)",
        "hostapi": 2,
        "max_input_channels": 0,
        "max_output_channels": 2,
        "default_samplerate": 48000.0,
        "default_low_output_latency": 0.002,
        "default_high_output_latency": 0.004,
    },
}


def make_fake_sd(hostapis=None):
    module = types.SimpleNamespace(__version__="0.5.5")
    api_entries = list(HOSTAPIS if hostapis is None else hostapis)

    def query_hostapis():
        return [dict(entry) for entry in api_entries]

    def query_devices(index=None):
        if index is None:
            return [dict(DEVICES[key]) for key in sorted(DEVICES)]
        return dict(DEVICES[index])

    module.query_hostapis = query_hostapis
    module.query_devices = query_devices
    return module


@pytest.fixture
def fake_sd(monkeypatch):
    module = make_fake_sd()
    monkeypatch.setattr(core, "sd", module)
    return module


@pytest.fixture
def runner():
    return CliRunner()


def invoke(runner, args):
    return runner.invoke(main, args)


def test_list_defaults_to_wasapi(fake_sd, runner):
    result = invoke(runner, ["list"])
    assert result.exit_code == 0, result.output
    assert "Speakers (WASAPI)" in result.output
    assert "Headphones, USB (WASAPI)" in result.output
    assert "Speakers (MME)" not in result.output
    assert "3.00" in result.output
    assert "10.00" in result.output


def test_list_hostapi_name_and_index(fake_sd, runner):
    by_name = invoke(runner, ["list", "--hostapi", "mme"])
    by_index = invoke(runner, ["list", "--hostapi", "0"])
    assert by_name.exit_code == 0, by_name.output
    assert by_index.exit_code == 0, by_index.output
    assert "Speakers (MME)" in by_name.output
    assert "WASAPI" not in by_name.output
    assert by_name.output == by_index.output


def test_list_all(fake_sd, runner):
    result = invoke(runner, ["list", "--hostapi", "all", "--json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert len(rows) == 6
    assert {row["hostapi_name"] for row in rows} == {"MME", "Windows WASAPI", "Windows WDM-KS"}


def test_list_json_defaults(fake_sd, runner):
    result = invoke(runner, ["list", "--json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert [row["index"] for row in rows] == [2, 3, 4]
    speakers = rows[0]
    assert speakers["default_output"] is True
    assert speakers["default_input"] is False
    assert speakers["low_output_ms"] == pytest.approx(3.0)
    assert speakers["high_output_ms"] == pytest.approx(10.0)
    assert speakers["sample_rate"] == 48000.0
    assert rows[1]["default_input"] is True


def test_list_csv(fake_sd, runner):
    result = invoke(runner, ["list", "--csv"])
    assert result.exit_code == 0, result.output
    rows = list(csv.DictReader(io.StringIO(result.output)))
    assert len(rows) == 3
    assert set(rows[0]) == set(
        [
            "index",
            "hostapi",
            "hostapi_name",
            "name",
            "input_channels",
            "output_channels",
            "sample_rate",
            "low_input_ms",
            "high_input_ms",
            "low_output_ms",
            "high_output_ms",
            "default_input",
            "default_output",
        ]
    )
    assert rows[2]["name"] == "Headphones, USB (WASAPI)"
    assert rows[2]["default_output"] == "False"
    assert rows[0]["default_output"] == "True"


def test_list_unknown_hostapi(fake_sd, runner):
    result = invoke(runner, ["list", "--hostapi", "asio"])
    assert result.exit_code != 0
    assert "No host API matches" in result.output


def test_list_json_and_csv_conflict(fake_sd, runner):
    result = invoke(runner, ["list", "--json", "--csv"])
    assert result.exit_code != 0
    assert "either --json or --csv" in result.output


def test_info_text(fake_sd, runner):
    result = invoke(runner, ["info"])
    assert result.exit_code == 0, result.output
    assert "Windows WASAPI" in result.output
    assert "Default input: 3 - Microphone (WASAPI)" in result.output
    assert "Default output: 2 - Speakers (WASAPI)" in result.output
    assert "192000 Hz" in result.output
    assert "48000 Hz" in result.output
    assert "channels: 2" in result.output
    assert "low latency: 3.00 ms" in result.output
    assert "high latency: 10.00 ms" in result.output


def test_info_json(fake_sd, runner):
    result = invoke(runner, ["info", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["hostapi"] == 1
    assert data["hostapi_name"] == "Windows WASAPI"
    assert data["output"]["device"] == 2
    assert data["input"]["device"] == 3
    assert data["input"]["direction"] == "input"
    assert data["output"]["low_latency_ms"] == pytest.approx(3.0)


def test_measure_default_output(fake_sd, runner):
    result = invoke(runner, ["measure"])
    assert result.exit_code == 0, result.output
    assert "Speakers (WASAPI)" in result.output
    assert "Low buffer latency: 3.00 ms (144 frames)" in result.output
    assert "High buffer latency: 10.00 ms (480 frames)" in result.output


def test_check_default_output_explains_report_without_changing_settings(fake_sd, runner):
    result = invoke(runner, ["check"])
    assert result.exit_code == 0, result.output
    assert "Default output: 2 - Speakers (WASAPI)" in result.output
    assert "Driver-reported buffer latency: 3.00 ms low, 10.00 ms high" in result.output
    assert "This is not total game or audio latency" in result.output
    assert "No audio was played and no Windows settings were changed" in result.output


def test_check_default_output_requires_default_output(runner, monkeypatch):
    module = make_fake_sd(
        hostapis=[{"name": "Windows WASAPI", "devices": [2], "default_input_device": 3, "default_output_device": -1}]
    )
    monkeypatch.setattr(core, "sd", module)
    result = invoke(runner, ["check"])
    assert result.exit_code == 1
    assert "No default WASAPI output device is set" in result.output
    assert "Windows Settings > System > Sound" in result.output


def test_measure_selected_input(fake_sd, runner):
    result = invoke(runner, ["measure", "--device", "3"])
    assert result.exit_code == 0, result.output
    assert "Microphone (WASAPI)" in result.output
    assert "Direction: input" in result.output
    assert "3.00 ms (576 frames)" in result.output


def test_measure_json(fake_sd, runner):
    result = invoke(runner, ["measure", "--device", "2", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["device"] == 2
    assert data["direction"] == "output"
    assert data["channels"] == 2
    assert data["low_latency_ms"] == pytest.approx(3.0)
    assert data["high_buffer_frames"] == 480


def test_measure_rejects_wrong_direction(fake_sd, runner):
    result = invoke(runner, ["measure", "--device", "3", "--direction", "output"])
    assert result.exit_code != 0
    assert "no output channels" in result.output


def test_measure_unknown_device(fake_sd, runner):
    result = invoke(runner, ["measure", "--device", "99"])
    assert result.exit_code != 0
    assert "Device 99 not found" in result.output


def test_measure_without_defaults(monkeypatch, runner):
    module = make_fake_sd(
        hostapis=[{"name": "Windows WASAPI", "devices": [2], "default_input_device": -1, "default_output_device": -1}]
    )
    monkeypatch.setattr(core, "sd", module)
    result = invoke(runner, ["measure"])
    assert result.exit_code != 0
    assert "no default output or input device" in result.output


def test_profiles_table(fake_sd, runner):
    result = invoke(runner, ["profiles"])
    assert result.exit_code == 0, result.output
    for name in core.PROFILE_ORDER:
        assert name in result.output
    assert "1024" in result.output
    assert "21.33" in result.output
    assert "1.33" in result.output


def test_profiles_rate_and_json(fake_sd, runner):
    result = invoke(runner, ["profiles", "--rate", "44100", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["sample_rate"] == 44100
    by_name = {row["profile"]: row for row in data["profiles"]}
    assert by_name["safe"]["frames"] == 1024
    assert by_name["safe"]["latency_ms"] == pytest.approx(1024 / 44100 * 1000)
    assert list(by_name) == list(core.PROFILE_ORDER)


def test_profiles_matches_recommend(fake_sd, runner):
    profiles_data = json.loads(invoke(runner, ["profiles", "--json"]).output)
    recommend_data = json.loads(invoke(runner, ["recommend", "--profile", "balanced", "--json"]).output)
    profile = next(row for row in profiles_data["profiles"] if row["profile"] == "balanced")
    assert recommend_data["frames"] == profile["frames"]
    assert recommend_data["latency_ms"] == pytest.approx(profile["latency_ms"])


def test_recommend_text(fake_sd, runner):
    result = invoke(runner, ["recommend", "--profile", "gaming", "--device", "4"])
    assert result.exit_code == 0, result.output
    assert "Profile: gaming" in result.output
    assert "Frames: 256" in result.output
    assert "Latency: 5.80 ms" in result.output
    assert "Headphones, USB (WASAPI)" in result.output


def test_recommend_json(fake_sd, runner):
    result = invoke(runner, ["recommend", "--profile", "gaming", "--device", "2", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["profile"] == "gaming"
    assert data["frames"] == 256
    assert data["latency_ms"] == pytest.approx(256 / 48000 * 1000)
    assert data["device"] == 2
    assert data["channels"] == 2
    assert data["device_low_latency_ms"] == pytest.approx(3.0)


def test_recommend_unknown_profile(fake_sd, runner):
    result = invoke(runner, ["recommend", "--profile", "nope"])
    assert result.exit_code != 0
    assert "Invalid value" in result.output


def test_doctor_ok(fake_sd, runner):
    result = invoke(runner, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "[ok] sounddevice import: version 0.5.5" in result.output
    assert "[ok] Windows WASAPI" in result.output
    assert "[ok] Default output device: device 2" in result.output
    assert "doctor: 6/6 checks passed" in result.output


def test_doctor_missing_wasapi(runner, monkeypatch):
    module = make_fake_sd(hostapis=[HOSTAPIS[0]])
    monkeypatch.setattr(core, "sd", module)
    result = invoke(runner, ["doctor"])
    assert result.exit_code == 1
    assert "[fail] Windows WASAPI" in result.output
    assert "hint: WASAPI is only available on Windows" in result.output
    assert "doctor: 2/3 checks passed" in result.output


def test_doctor_missing_default_output(runner, monkeypatch):
    hostapis = [
        {"name": "Windows WASAPI", "devices": [2], "default_input_device": -1, "default_output_device": -1}
    ]
    module = make_fake_sd(hostapis=hostapis)
    monkeypatch.setattr(core, "sd", module)
    result = invoke(runner, ["doctor"])
    assert result.exit_code == 1
    assert "[fail] Default output device: none" in result.output
    assert "Set a default output device" in result.output


def test_doctor_sounddevice_missing(runner, monkeypatch):
    def broken():
        raise RuntimeError("sounddevice is not installed")

    monkeypatch.setattr(core, "get_sd", broken)
    result = invoke(runner, ["doctor"])
    assert result.exit_code == 1
    assert "[fail] sounddevice import" in result.output
    assert "pip install sounddevice" in result.output


def test_help_lists_commands(runner):
    result = invoke(runner, ["--help"])
    assert result.exit_code == 0
    for command in ("list", "info", "measure", "check", "profiles", "recommend", "doctor"):
        assert command in result.output
