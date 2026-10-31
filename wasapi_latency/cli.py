"""Command-line interface for wasapi_latency."""

import json
import sys

try:
    import sounddevice as sd
except Exception:  # pragma: no cover
    sd = None

import click

from . import core

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version="0.1.0", prog_name="wasapi-latency")
def main():
    """Inspect and tune Windows WASAPI buffer latency."""


@main.command()
def info():
    """Show Windows WASAPI host API and default devices."""
    sd_mod = core.get_sd()
    idx, host = core.find_wasapi_hostapi(sd_mod)
    click.echo("Host API: %s (index %d)" % (host.get("name", host) if isinstance(host, dict) else host, idx))
    inp_idx, out_idx = core.default_device_indices(sd_mod)

    def show(label, dev_index, kind):
        if dev_index is None:
            click.echo("%s device: (none)" % label)
            return
        _, dev = core.query_device(sd_mod, dev_index)
        in_ch, out_ch = core.device_channels(dev)
        sr = core.device_sample_rate(dev)
        lows = core.latency_ms(dev, kind=kind, level="low")
        highs = core.latency_ms(dev, kind=kind, level="high")
        click.echo("%s device: %s - %s" % (label, dev_index, core.device_name(dev)))
        click.echo("  sample rate: %s Hz" % _fmt_number(sr))
        click.echo("  channels: %d in / %d out" % (in_ch, out_ch))
        click.echo("  low latency: %.2f ms" % lows)
        click.echo("  high latency: %.2f ms" % highs)

    show("Default input", inp_idx, "input")
    show("Default output", out_idx, "output")


@main.command()
@click.option("--device", "device", type=int, default=None, help="Device index to measure.")
def measure(device):
    """Report buffer latency for an output device."""
    sd_mod = core.get_sd()
    target = device
    if target is None:
        _, target = core.default_device_indices(sd_mod)
    idx, dev = core.query_device(sd_mod, target)
    in_ch, out_ch = core.device_channels(dev)
    sr = core.device_sample_rate(dev)
    lows = core.latency_ms(dev, kind="output", level="low")
    highs = core.latency_ms(dev, kind="output", level="high")
    channels = out_ch if out_ch > 0 else in_ch
    click.echo("Device: %s - %s" % (idx, core.device_name(dev)))
    click.echo("Sample rate: %s Hz" % _fmt_number(sr))
    click.echo("Channels: %d" % channels)
    click.echo("Low buffer latency: %.2f ms" % lows)
    click.echo("High buffer latency: %.2f ms" % highs)


@main.command()
def profiles():
    """Table of recommended WASAPI buffer profiles at 48 kHz."""
    click.echo("%-12s %8s %10s" % ("Profile", "Frames", "ms@48k"))
    click.echo("%-12s %8s %10s" % ("-" * 12, "-" * 8, "-" * 10))
    for name in core.PROFILE_ORDER:
        frames = core.PROFILES[name]
        ms = core.frames_to_ms(frames, core.DEFAULT_SAMPLE_RATE)
        click.echo("%-12s %8d %10.2f" % (name, frames, ms))


@main.command()
@click.option("--profile", "profile", required=True, help="Profile name.")
@click.option("--device", "device", type=int, default=None, help="Device index.")
@click.option("--json", "as_json", is_flag=True, help="Output JSON.")
def recommend(profile, device, as_json):
    """Recommend a WASAPI buffer profile for a device."""
    try:
        result = core.recommend(profile, device_index=device)
    except ValueError as exc:
        raise click.ClickException(str(exc))
    if as_json:
        click.echo(core.to_json(result))
    else:
        click.echo("Profile: %s" % result["profile"])
        click.echo("Frames: %d" % result["frames"])
        click.echo("Latency: %.2f ms" % result["ms"])
        click.echo("Device: %s - %s" % (result["device"], result["device_name"]))
        click.echo("Sample rate: %s Hz" % _fmt_number(result["sample_rate"]))
        click.echo("Channels: %d" % result["channels"])


@main.command()
def doctor():
    """Check sounddevice import and WASAPI availability."""
    ok, messages = core.doctor()
    for msg in messages:
        click.echo(msg)
    if not ok:
        raise click.ClickException("Doctor check failed")


def _fmt_number(value):
    try:
        if float(value).is_integer():
            return str(int(value))
    except (TypeError, ValueError):
        pass
    return str(value)


if __name__ == "__main__":
    main()
