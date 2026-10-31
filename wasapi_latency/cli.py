"""Command-line interface for wasapi-latency."""

import click

from . import __version__, core

CONTEXT_SETTINGS = {"help_option_names": ["-h", "--help"]}


def _fmt_number(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return str(int(number))
    return "%.2f" % number


def _fmt_ms(value):
    return "%.2f" % value


def _table(headers, rows, right_align=()):
    widths = [len(str(header)) for header in headers]
    for row in rows:
        for index, cell in enumerate(row):
            widths[index] = max(widths[index], len(str(cell)))

    def render(cells):
        parts = []
        for index, cell in enumerate(cells):
            text = str(cell)
            if headers[index] in right_align:
                text = text.rjust(widths[index])
            else:
                text = text.ljust(widths[index])
            parts.append(text)
        return "  ".join(parts).rstrip()

    lines = [render(headers), render(["-" * width for width in widths])]
    lines.extend(render(row) for row in rows)
    return "\n".join(lines)


def _fail(message):
    raise click.ClickException(str(message))


def _latency_pair(row):
    if row["output_channels"] > 0:
        return "output", row["low_output_ms"], row["high_output_ms"]
    return "input", row["low_input_ms"], row["high_input_ms"]


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(version=__version__, prog_name="wasapi-latency")
def main():
    """Inspect Windows WASAPI devices and buffer latency."""


@main.command("list")
@click.option(
    "--hostapi",
    "hostapi",
    default="wasapi",
    show_default=True,
    help="Host API name, index, or 'all'.",
)
@click.option("--json", "as_json", is_flag=True, help="Print JSON.")
@click.option("--csv", "as_csv", is_flag=True, help="Print CSV.")
def list_command(hostapi, as_json, as_csv):
    """List audio devices for a host API."""
    if as_json and as_csv:
        _fail("Use either --json or --csv, not both.")
    try:
        rows = core.list_devices(hostapi)
    except (RuntimeError, ValueError) as exc:
        _fail(exc)

    if as_json:
        click.echo(core.to_json(rows))
        return
    if as_csv:
        click.echo(_to_csv(rows))
        return

    table_rows = []
    for row in rows:
        direction, low_ms, high_ms = _latency_pair(row)
        default = []
        if row["default_input"]:
            default.append("in")
        if row["default_output"]:
            default.append("out")
        table_rows.append(
            [
                row["index"],
                row["hostapi_name"] or "",
                direction,
                row["input_channels"],
                row["output_channels"],
                _fmt_number(row["sample_rate"]),
                _fmt_ms(low_ms),
                _fmt_ms(high_ms),
                ",".join(default),
                row["name"],
            ]
        )
    click.echo(
        _table(
            ["IDX", "HOST", "DIR", "IN", "OUT", "RATE", "LOW ms", "HIGH ms", "DEFAULT", "NAME"],
            table_rows,
            right_align=("IDX", "IN", "OUT", "RATE", "LOW ms", "HIGH ms"),
        )
    )


CSV_COLUMNS = (
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
)


def _to_csv(rows):
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().rstrip("\r\n")


def _print_device_report(prefix, report):
    if report is None:
        click.echo("%s: none" % prefix)
        return
    click.echo(
        "%s: %d - %s (%s)"
        % (prefix, report["device"], report["name"], report["hostapi_name"] or "unknown host API")
    )
    click.echo("  direction: %s" % report["direction"])
    click.echo("  sample rate: %s Hz" % _fmt_number(report["sample_rate"]))
    click.echo("  channels: %d" % report["channels"])
    click.echo("  low latency: %s ms" % _fmt_ms(report["low_latency_ms"]))
    click.echo("  high latency: %s ms" % _fmt_ms(report["high_latency_ms"]))


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Print JSON.")
def info(as_json):
    """Show the WASAPI host API and its default devices."""
    try:
        report = core.defaults_report()
    except (RuntimeError, ValueError) as exc:
        _fail(exc)
    if as_json:
        click.echo(core.to_json(report))
        return
    click.echo("Host API: %s (index %d)" % (report["hostapi_name"], report["hostapi"]))
    _print_device_report("Default input", report["input"])
    _print_device_report("Default output", report["output"])


@main.command()
@click.option("--device", "device", type=int, default=None, help="Device index (default: default output).")
@click.option(
    "--direction",
    type=click.Choice(["auto", "input", "output"]),
    default="auto",
    show_default=True,
    help="Latency direction.",
)
@click.option("--json", "as_json", is_flag=True, help="Print JSON.")
def measure(device, direction, as_json):
    """Report buffer latency for one device."""
    try:
        report = core.measure(device, direction)
    except (RuntimeError, ValueError) as exc:
        _fail(exc)
    if as_json:
        click.echo(core.to_json(report))
        return
    click.echo("Device: %d - %s" % (report["device"], report["name"]))
    click.echo("Host API: %s" % (report["hostapi_name"] or "unknown"))
    click.echo("Direction: %s" % report["direction"])
    click.echo("Sample rate: %s Hz" % _fmt_number(report["sample_rate"]))
    click.echo("Channels: %d" % report["channels"])
    click.echo("Low buffer latency: %s ms (%d frames)" % (_fmt_ms(report["low_latency_ms"]), report["low_buffer_frames"]))
    click.echo(
        "High buffer latency: %s ms (%d frames)"
        % (_fmt_ms(report["high_latency_ms"]), report["high_buffer_frames"])
    )


@main.command()
@click.option("--rate", "sample_rate", type=click.IntRange(min=1), default=core.DEFAULT_SAMPLE_RATE, show_default=True)
@click.option("--json", "as_json", is_flag=True, help="Print JSON.")
def profiles(sample_rate, as_json):
    """Show the buffer profiles used by recommend."""
    rows = core.profile_rows(sample_rate)
    if as_json:
        click.echo(core.to_json({"sample_rate": sample_rate, "profiles": rows}))
        return
    table_rows = [
        [row["profile"], row["frames"], _fmt_ms(row["latency_ms"])]
        for row in rows
    ]
    click.echo("Sample rate: %s Hz" % _fmt_number(sample_rate))
    click.echo(
        _table(
            ["PROFILE", "FRAMES", "LATENCY ms"],
            table_rows,
            right_align=("FRAMES", "LATENCY ms"),
        )
    )


@main.command()
@click.option("--profile", type=click.Choice(core.PROFILE_ORDER), required=True, help="Profile name.")
@click.option("--device", "device", type=int, default=None, help="Device index (default: default output).")
@click.option("--json", "as_json", is_flag=True, help="Print JSON.")
def recommend(profile, device, as_json):
    """Show the buffer size for a profile on a device."""
    try:
        result = core.recommend(profile, device)
    except (RuntimeError, ValueError) as exc:
        _fail(exc)
    if as_json:
        click.echo(core.to_json(result))
        return
    click.echo("Profile: %s" % result["profile"])
    click.echo("Frames: %d" % result["frames"])
    click.echo("Latency: %s ms" % _fmt_ms(result["latency_ms"]))
    click.echo("Device: %d - %s" % (result["device"], result["name"]))
    click.echo("Host API: %s" % (result["hostapi_name"] or "unknown"))
    click.echo("Direction: %s" % result["direction"])
    click.echo("Sample rate: %s Hz" % _fmt_number(result["sample_rate"]))
    click.echo("Channels: %d" % result["channels"])
    click.echo("Device low latency: %s ms" % _fmt_ms(result["device_low_latency_ms"]))
    click.echo("Device high latency: %s ms" % _fmt_ms(result["device_high_latency_ms"]))


@main.command()
def doctor():
    """Check sounddevice, WASAPI, and default devices."""
    checks = core.doctor()
    for check in checks:
        status = "ok" if check["ok"] else "fail"
        click.echo("[%s] %s: %s" % (status, check["name"], check["detail"]))
        if not check["ok"] and check["hint"]:
            click.echo("       hint: %s" % check["hint"])
    passed = sum(1 for check in checks if check["ok"])
    click.echo("doctor: %d/%d checks passed" % (passed, len(checks)))
    if passed != len(checks):
        click.get_current_context().exit(1)


if __name__ == "__main__":
    main()
