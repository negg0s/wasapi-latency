"""Device, latency and profile helpers for wasapi-latency."""

import json
from collections.abc import Mapping

PROFILES = {
    "safe": 1024,
    "balanced": 512,
    "gaming": 256,
    "low": 128,
    "ultra": 64,
}
PROFILE_ORDER = ("safe", "balanced", "gaming", "low", "ultra")
DEFAULT_SAMPLE_RATE = 48000

# Replaced by tests to avoid touching real audio hardware.
sd = None


def get_sd():
    """Return the sounddevice module or raise RuntimeError."""
    if sd is not None:
        return sd
    try:
        import sounddevice as module
    except Exception as exc:
        raise RuntimeError("sounddevice is not installed: %s" % exc) from exc
    return module


def to_json(value):
    return json.dumps(value, indent=2, ensure_ascii=False)


def _name(info):
    if isinstance(info, Mapping):
        return str(info.get("name", ""))
    return str(info)


def hostapis(sd_mod=None):
    sd_mod = sd_mod or get_sd()
    raw = sd_mod.query_hostapis()
    if isinstance(raw, Mapping):
        return [raw[key] for key in sorted(raw)]
    return list(raw)


def find_hostapi(query, sd_mod=None):
    """Find a host API by index or case-insensitive name substring."""
    entries = hostapis(sd_mod)
    text = str(query).strip()
    names = ", ".join("%d=%s" % (i, _name(info)) for i, info in enumerate(entries))
    if text.isdigit():
        index = int(text)
        if 0 <= index < len(entries):
            return index, entries[index]
        raise ValueError("Host API index %d is out of range (available: %s)" % (index, names))
    matches = [(i, info) for i, info in enumerate(entries) if text.lower() in _name(info).lower()]
    if not matches:
        raise ValueError("No host API matches %r (available: %s)" % (text, names))
    exact = [match for match in matches if _name(match[1]).lower() == text.lower()]
    if exact:
        return exact[0]
    if len(matches) > 1:
        raise ValueError(
            "Host API %r is ambiguous (matches: %s)"
            % (text, ", ".join(_name(info) for _, info in matches))
        )
    return matches[0]


def find_wasapi_hostapi(sd_mod=None):
    return find_hostapi("WASAPI", sd_mod)


def default_device_indices(sd_mod=None):
    """Default input and output indices reported by the WASAPI host API."""
    _, info = find_wasapi_hostapi(sd_mod)
    if not isinstance(info, Mapping):
        return None, None
    inp = info.get("default_input_device", -1)
    out = info.get("default_output_device", -1)
    return (None if inp == -1 else inp), (None if out == -1 else out)


def query_device(index, sd_mod=None):
    """Query one device and turn PortAudio errors into ValueError."""
    sd_mod = sd_mod or get_sd()
    try:
        return sd_mod.query_devices(index)
    except Exception as exc:
        raise ValueError("Device %s not found. Run 'wasapi-latency list' to see indexes." % index) from exc


def device_name(device):
    if isinstance(device, Mapping):
        return str(device.get("name", ""))
    return str(device)


def device_sample_rate(device):
    if isinstance(device, Mapping):
        for key in ("default_samplerate", "default_sample_rate", "samplerate", "sample_rate"):
            value = device.get(key)
            if value is not None:
                return float(value)
    return float(DEFAULT_SAMPLE_RATE)


def device_channels(device):
    if isinstance(device, Mapping):
        inp = int(device.get("max_input_channels", 0) or 0)
        out = int(device.get("max_output_channels", 0) or 0)
        return inp, out
    return 0, 0


def latency_ms(device, direction="output", level="low"):
    """Latency in milliseconds for a direction and latency level."""
    if not isinstance(device, Mapping):
        return 0.0
    if direction == "input":
        key = "default_low_input_latency" if level == "low" else "default_high_input_latency"
    else:
        key = "default_low_output_latency" if level == "low" else "default_high_output_latency"
    value = device.get(key, 0.0)
    try:
        return float(value) * 1000.0
    except (TypeError, ValueError):
        return 0.0


def frames_to_ms(frames, sample_rate=DEFAULT_SAMPLE_RATE):
    return frames / float(sample_rate) * 1000.0


def ms_to_frames(ms, sample_rate=DEFAULT_SAMPLE_RATE):
    return int(round(ms / 1000.0 * sample_rate))


def profile_frames(name):
    try:
        return PROFILES[name]
    except KeyError:
        raise ValueError("Unknown profile: %s" % name) from None


def profile_rows(sample_rate=DEFAULT_SAMPLE_RATE):
    return [
        {
            "profile": name,
            "frames": PROFILES[name],
            "latency_ms": frames_to_ms(PROFILES[name], sample_rate),
        }
        for name in PROFILE_ORDER
    ]


def _device_indices(hostapi_index, hostapi_info, sd_mod):
    if isinstance(hostapi_info, Mapping) and hostapi_info.get("devices"):
        return [int(index) for index in hostapi_info["devices"]]
    devices = list(sd_mod.query_devices())
    return [
        index
        for index, device in enumerate(devices)
        if isinstance(device, Mapping) and device.get("hostapi") == hostapi_index
    ]


def _hostapi_name(index, sd_mod):
    try:
        return _name(hostapis(sd_mod)[index])
    except (IndexError, TypeError):
        return None


def device_report(index, device, hostapi_index=None, hostapi_name=None):
    inp, out = device_channels(device)
    return {
        "index": int(index),
        "name": device_name(device),
        "hostapi": hostapi_index,
        "hostapi_name": hostapi_name,
        "input_channels": inp,
        "output_channels": out,
        "sample_rate": device_sample_rate(device),
        "low_input_ms": latency_ms(device, "input", "low"),
        "high_input_ms": latency_ms(device, "input", "high"),
        "low_output_ms": latency_ms(device, "output", "low"),
        "high_output_ms": latency_ms(device, "output", "high"),
    }


def list_devices(hostapi="wasapi", sd_mod=None):
    """Return device rows for one host API, or for all when hostapi is 'all'."""
    sd_mod = sd_mod or get_sd()
    if hostapi is None or str(hostapi).lower() == "all":
        targets = list(enumerate(hostapis(sd_mod)))
    else:
        targets = [find_hostapi(hostapi, sd_mod)]

    rows = []
    for hostapi_index, info in targets:
        hostapi_name = _name(info)
        default_in = info.get("default_input_device", -1) if isinstance(info, Mapping) else -1
        default_out = info.get("default_output_device", -1) if isinstance(info, Mapping) else -1
        for device_index in _device_indices(hostapi_index, info, sd_mod):
            device = query_device(device_index, sd_mod)
            row = device_report(device_index, device, hostapi_index, hostapi_name)
            row["default_input"] = device_index == default_in
            row["default_output"] = device_index == default_out
            rows.append(row)
    return rows


def _latency_fields(row, direction):
    prefix = "input" if direction == "input" else "output"
    return row["low_%s_ms" % prefix], row["high_%s_ms" % prefix]


def measure(device_index=None, direction="auto", sd_mod=None):
    """Buffer latency report for a device, defaulting to the default output."""
    sd_mod = sd_mod or get_sd()
    if device_index is None:
        default_in, default_out = default_device_indices(sd_mod)
        device_index = default_out if default_out is not None else default_in
        if device_index is None:
            raise RuntimeError(
                "WASAPI has no default output or input device. "
                "Set one in Windows Settings > System > Sound."
            )

    device = query_device(device_index, sd_mod)
    inp, out = device_channels(device)
    if direction == "auto":
        if out > 0:
            direction = "output"
        elif inp > 0:
            direction = "input"
        else:
            raise RuntimeError("Device %s has no input or output channels" % device_index)
    elif direction == "output" and out == 0:
        raise ValueError("Device %s has no output channels" % device_index)
    elif direction == "input" and inp == 0:
        raise ValueError("Device %s has no input channels" % device_index)

    row = device_report(device_index, device, device.get("hostapi"))
    row["hostapi_name"] = _hostapi_name(row["hostapi"], sd_mod) if row["hostapi"] is not None else None
    low_ms, high_ms = _latency_fields(row, direction)
    sample_rate = row["sample_rate"]
    return {
        "device": row["index"],
        "name": row["name"],
        "hostapi": row["hostapi"],
        "hostapi_name": row["hostapi_name"],
        "direction": direction,
        "sample_rate": sample_rate,
        "channels": out if direction == "output" else inp,
        "low_latency_ms": low_ms,
        "high_latency_ms": high_ms,
        "low_buffer_frames": ms_to_frames(low_ms, sample_rate),
        "high_buffer_frames": ms_to_frames(high_ms, sample_rate),
    }


def defaults_report(sd_mod=None):
    """WASAPI host API plus reports for its default input and output devices."""
    sd_mod = sd_mod or get_sd()
    hostapi_index, hostapi_info = find_wasapi_hostapi(sd_mod)
    default_in, default_out = default_device_indices(sd_mod)
    report = {
        "hostapi": hostapi_index,
        "hostapi_name": _name(hostapi_info),
        "input": None,
        "output": None,
    }
    if default_in is not None:
        report["input"] = measure(default_in, "input", sd_mod)
    if default_out is not None:
        report["output"] = measure(default_out, "output", sd_mod)
    return report


def recommend(profile, device_index=None, sd_mod=None):
    """Map a profile frame count onto a device sample rate."""
    frames = profile_frames(profile)
    report = measure(device_index, "auto", sd_mod)
    latency = frames_to_ms(frames, report["sample_rate"])
    return {
        "profile": profile,
        "frames": frames,
        "latency_ms": latency,
        "device": report["device"],
        "name": report["name"],
        "hostapi": report["hostapi"],
        "hostapi_name": report["hostapi_name"],
        "direction": report["direction"],
        "sample_rate": report["sample_rate"],
        "channels": report["channels"],
        "device_low_latency_ms": report["low_latency_ms"],
        "device_high_latency_ms": report["high_latency_ms"],
    }


def _check(name, ok, detail, hint=None):
    return {"name": name, "ok": bool(ok), "detail": detail, "hint": hint}


def doctor(sd_mod=None):
    """Run environment checks. Returns a list of check dictionaries."""
    checks = []
    try:
        sd_mod = sd_mod or get_sd()
    except Exception as exc:
        checks.append(
            _check(
                "sounddevice import",
                False,
                str(exc),
                "Install it with: pip install sounddevice",
            )
        )
        return checks

    version = getattr(sd_mod, "__version__", "unknown")
    checks.append(_check("sounddevice import", True, "version %s" % version))

    try:
        entries = hostapis(sd_mod)
    except Exception as exc:
        checks.append(
            _check(
                "PortAudio host APIs",
                False,
                str(exc),
                "Reinstall the package: pip install --force-reinstall sounddevice",
            )
        )
        return checks
    checks.append(_check("PortAudio host APIs", True, "%d host APIs" % len(entries)))

    try:
        hostapi_index, hostapi_info = find_wasapi_hostapi(sd_mod)
    except ValueError as exc:
        checks.append(
            _check(
                "Windows WASAPI",
                False,
                str(exc),
                "WASAPI is only available on Windows. Check that the Windows Audio "
                "service is running and a playback device is enabled.",
            )
        )
        return checks
    checks.append(_check("Windows WASAPI", True, "index %d, %s" % (hostapi_index, _name(hostapi_info))))

    devices = _device_indices(hostapi_index, hostapi_info, sd_mod)
    checks.append(
        _check(
            "WASAPI devices",
            bool(devices),
            "%d devices" % len(devices),
            "Enable a playback or recording device in Windows Settings > System > Sound.",
        )
    )

    default_in, default_out = default_device_indices(sd_mod)
    checks.append(
        _check(
            "Default output device",
            default_out is not None,
            "device %d" % default_out if default_out is not None else "none",
            "Set a default output device in Windows Settings > System > Sound.",
        )
    )
    if default_in is None:
        checks.append(_check("Default input device", True, "none (microphone not required)"))
    else:
        checks.append(_check("Default input device", True, "device %d" % default_in))
    return checks
