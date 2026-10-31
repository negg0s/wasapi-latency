"""Core helpers for querying Windows WASAPI devices and profiles."""

import json
import sys

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - optional at import time
    sd = None

PROFILES = {
    "safe": 1024,
    "balanced": 512,
    "gaming": 256,
    "low": 128,
    "ultra": 64,
}
PROFILE_ORDER = ["safe", "balanced", "gaming", "low", "ultra"]
DEFAULT_SAMPLE_RATE = 48000


_REAL_SD = sd


def get_sd():
    """Resolve the sounddevice module, honouring test monkeypatches."""
    candidates = []
    for name in ("wasapi_latency.cli", "wasapi_latency.core", "wasapi_latency"):
        module = sys.modules.get(name)
        if module is not None and hasattr(module, "sd") and getattr(module, "sd") is not None:
            candidates.append(getattr(module, "sd"))
    sm = sys.modules.get("sounddevice")
    if sm is not None:
        candidates.append(sm)
    # Prefer a patched/replaced module over the originally imported one.
    patched = [c for c in candidates if c is not _REAL_SD]
    if patched:
        return patched[0]
    if candidates:
        return candidates[0]
    try:
        import sounddevice as _sd
        return _sd
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("sounddevice is not available: %s" % exc)


def _hostapis(sd_mod=None):
    sd_mod = sd_mod or get_sd()
    result = sd_mod.query_hostapis()
    # sounddevice returns a list of dicts; tolerate dict-like mocks.
    if isinstance(result, dict):
        return list(result.values()) if all(isinstance(v, dict) for v in result.values()) else [result]
    return list(result)


def find_wasapi_hostapi(sd_mod=None):
    sd_mod = sd_mod or get_sd()
    hostapis = _hostapis(sd_mod)
    for index, info in enumerate(hostapis):
        name = ""
        if isinstance(info, dict):
            name = str(info.get("name", ""))
        else:
            name = str(info)
        if "WASAPI" in name.upper():
            return index, info
    raise RuntimeError("Windows WASAPI host API not found")


def wasapi_hostapi_index(sd_mod=None):
    index, _ = find_wasapi_hostapi(sd_mod)
    return index


def default_device_indices(sd_mod=None):
    sd_mod = sd_mod or get_sd()
    _, info = find_wasapi_hostapi(sd_mod)
    if not isinstance(info, dict):
        return None, None
    inp = info.get("default_input_device", None)
    out = info.get("default_output_device", None)
    if inp == -1:
        inp = None
    if out == -1:
        out = None
    return inp, out


def query_device(sd_mod=None, index=None):
    sd_mod = sd_mod or get_sd()
    if index is None:
        inp, out = default_device_indices(sd_mod)
        index = out if out is not None else inp
    return index, sd_mod.query_devices(index)


def device_name(device):
    if isinstance(device, dict):
        return str(device.get("name", ""))
    return str(device)


def device_sample_rate(device):
    if isinstance(device, dict):
        for key in ("default_samplerate", "default_sample_rate", "samplerate", "sample_rate"):
            if key in device and device.get(key) is not None:
                return float(device[key])
    return float(DEFAULT_SAMPLE_RATE)


def device_channels(device):
    if isinstance(device, dict):
        inp = device.get("max_input_channels", 0) or 0
        out = device.get("max_output_channels", 0) or 0
        return int(inp), int(out)
    return 0, 0


def latency_ms(device, kind="output", level="low"):
    """Return latency in ms for a device dict."""
    if not isinstance(device, dict):
        return 0.0
    if kind == "input":
        low_key = "default_low_input_latency"
        high_key = "default_high_input_latency"
    else:
        low_key = "default_low_output_latency"
        high_key = "default_high_output_latency"
    key = low_key if level == "low" else high_key
    # Fallbacks for alternate key names.
    if key not in device:
        alt = "default_low_latency" if level == "low" else "default_high_latency"
        key = alt if alt in device else key
    value = device.get(key, 0.0)
    try:
        return float(value) * 1000.0
    except (TypeError, ValueError):
        return 0.0


def all_latencies_ms(device, kind="output"):
    return {
        "low_ms": latency_ms(device, kind=kind, level="low"),
        "high_ms": latency_ms(device, kind=kind, level="high"),
    }


def frames_to_ms(frames, sample_rate=DEFAULT_SAMPLE_RATE):
    return frames / float(sample_rate) * 1000.0


def profile_frames(name):
    if name not in PROFILES:
        raise ValueError("Unknown profile: %s" % name)
    return PROFILES[name]


def profile_info(name, sample_rate=DEFAULT_SAMPLE_RATE):
    frames = profile_frames(name)
    return {
        "profile": name,
        "frames": frames,
        "ms": frames_to_ms(frames, sample_rate),
        "latency_ms": frames_to_ms(frames, sample_rate),
    }


def recommend(profile, device_index=None, sd_mod=None):
    sd_mod = sd_mod or get_sd()
    if profile not in PROFILES:
        raise ValueError("Unknown profile: %s" % profile)
    if device_index is None:
        _, out_idx = default_device_indices(sd_mod)
        device_index = out_idx
    idx, dev = query_device(sd_mod, device_index)
    sr = device_sample_rate(dev)
    frames = PROFILES[profile]
    ms = frames_to_ms(frames, sr)
    inp, out = device_channels(dev)
    channels = out if out > 0 else inp
    return {
        "profile": profile,
        "frames": frames,
        "ms": ms,
        "latency_ms": ms,
        "device": idx,
        "device_index": idx,
        "device_name": device_name(dev),
        "sample_rate": sr,
        "channels": channels,
    }


def doctor(sd_mod=None):
    """Return (ok, messages)."""
    messages = []
    try:
        sd_mod = sd_mod or get_sd()
    except Exception as exc:
        return False, ["sounddevice import: FAIL (%s)" % exc]
    messages.append("sounddevice import: OK")
    # version
    version = getattr(sd_mod, "__version__", None)
    if version is None:
        try:
            import importlib.metadata as md
            version = md.version("sounddevice")
        except Exception:
            version = "unknown"
    messages.append("sounddevice version: %s" % version)
    try:
        idx, info = find_wasapi_hostapi(sd_mod)
        messages.append("WASAPI host API: OK (index %s)" % idx)
        messages.append("WASAPI host API name: %s" % (info.get("name") if isinstance(info, dict) else info))
        return True, messages
    except Exception as exc:
        messages.append("WASAPI host API: FAIL (%s)" % exc)
        return False, messages


def to_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False)
