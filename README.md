# wasapi-latency

A command-line tool for Windows that reads WASAPI device information through
[sounddevice](https://python-sounddevice.readthedocs.io/) and prints:

- device indexes, host API, channel counts and sample rates
- the default WASAPI input and output devices
- the low and high buffer latency reported for each device
- fixed buffer profiles mapped to frames and milliseconds at a chosen sample rate

It does not open audio streams and does not measure round-trip latency. The
numbers come from the device information that PortAudio exposes.

## Requirements

- Windows 10 or 11
- Python 3.10 or newer
- An enabled playback or recording device

## Install

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e . --no-cache-dir
```

Dependencies are `click` and `sounddevice`. `sounddevice` ships its own PortAudio
DLL on Windows, so no separate PortAudio install is needed.

## Check your default output

After installation, open PowerShell and run:

```powershell
wasapi-latency check
```

Example:

```
Default output: 8 - Speakers (Realtek(R) Audio)
Host API: Windows WASAPI
Sample rate: 48000 Hz
Driver-reported buffer latency: 3.00 ms low, 10.00 ms high
This is not total game or audio latency. It is not a playback test.
No audio was played and no Windows settings were changed.
```

The command reads the default output reported by WASAPI. The low and high
values come from the audio driver. They do not measure delay from a game to your
headphones, and they do not tell you whether audio will crackle. The command
does not play sound, record audio, or change any Windows setting. If no default
output is set, choose one in Windows Settings under System, then Sound, and run
the command again.

To see the default microphone too, run `wasapi-latency info`. To see all
WASAPI devices, run `wasapi-latency list`.

## Commands

```
wasapi-latency list [--hostapi TEXT] [--json | --csv]
wasapi-latency info [--json]
wasapi-latency measure [--device INT] [--direction auto|input|output] [--json]
wasapi-latency check
wasapi-latency profiles [--rate INT] [--json]
wasapi-latency recommend --profile NAME [--device INT] [--json]
wasapi-latency doctor
```

`list` shows WASAPI devices by default. `--hostapi` accepts a name substring, a
host API index, or `all`.

`measure` uses the default WASAPI output device when `--device` is omitted. With
`--direction auto` it reports output latency when the device has output channels
and input latency otherwise.

`check` reports the default WASAPI output and its driver-reported buffer
latency. It does not open a stream or change Windows settings.

`recommend` uses the same default device rule and the profile frame counts below.

Exit codes: `0` on success, `1` on a runtime or doctor failure, `2` on invalid
arguments.

## Example output

`wasapi-latency list` on a machine with a Realtek onboard codec:

```
IDX  HOST            DIR     IN  OUT    RATE  LOW ms  HIGH ms  DEFAULT  NAME
---  --------------  ------  --  ---  ------  ------  -------  -------  ---------------------------
  8  Windows WASAPI  output   0    2   48000    3.00    10.00  out      Speakers (Realtek(R) Audio)
  9  Windows WASAPI  input    2    0  192000    3.00    10.00  in       Microphone (Realtek(R) Audio)
```

`DIR`, `LOW ms` and `HIGH ms` describe the direction used in the table: output
for devices with output channels, input otherwise. JSON and CSV contain latency
values for both directions.

`wasapi-latency info`:

```
Host API: Windows WASAPI (index 2)
Default input: 9 - Microphone (Realtek(R) Audio) (Windows WASAPI)
  direction: input
  sample rate: 192000 Hz
  channels: 2
  low latency: 3.00 ms
  high latency: 10.00 ms
Default output: 8 - Speakers (Realtek(R) Audio) (Windows WASAPI)
  direction: output
  sample rate: 48000 Hz
  channels: 2
  low latency: 3.00 ms
  high latency: 10.00 ms
```

`wasapi-latency measure --json`:

```json
{
  "device": 8,
  "name": "Speakers (Realtek(R) Audio)",
  "hostapi": 2,
  "hostapi_name": "Windows WASAPI",
  "direction": "output",
  "sample_rate": 48000.0,
  "channels": 2,
  "low_latency_ms": 3.0,
  "high_latency_ms": 10.0,
  "low_buffer_frames": 144,
  "high_buffer_frames": 480
}
```

`low_buffer_frames` and `high_buffer_frames` are calculated as
`latency_ms / 1000 * sample_rate`, rounded to the nearest frame.

`wasapi-latency doctor`:

```
[ok] sounddevice import: version 0.5.5
[ok] PortAudio host APIs: 4 host APIs
[ok] Windows WASAPI: index 2, Windows WASAPI
[ok] WASAPI devices: 2 devices
[ok] Default output device: device 8
[ok] Default input device: device 9
doctor: 6/6 checks passed
```

A failed check prints a `hint:` line, for example when no default output device
is configured.

## Profiles

Profile frames are fixed counts. Latency depends on the sample rate:

| Profile  | Frames | ms at 48 kHz |
|----------|--------|--------------|
| safe     | 1024   | 21.33        |
| balanced | 512    | 10.67        |
| gaming   | 256    | 5.33         |
| low      | 128    | 2.67         |
| ultra    | 64     | 1.33         |

`latency_ms = frames / sample_rate * 1000`. `profiles` defaults to 48 kHz and
accepts `--rate` to show another rate. `recommend` uses the selected device
sample rate, so its latency for the same profile can differ from the table.

## JSON and CSV

`list --json` prints an array of rows with these keys:

```
index, hostapi, hostapi_name, name, input_channels, output_channels,
sample_rate, low_input_ms, high_input_ms, low_output_ms, high_output_ms,
default_input, default_output
```

`list --csv` writes the same fields, one header row and one row per device.
`default_input` and `default_output` are relative to the device host API.

`info --json` returns the WASAPI host API index and name, plus `input` and
`output` reports using the same fields as `measure --json`.

`profiles --json` returns `sample_rate` and a `profiles` array of
`{profile, frames, latency_ms}`.

`recommend --json` returns the profile, frame count, calculated latency, device
details, and the selected device's low and high latency.

## Limitations

- Latency values are the defaults reported by the driver. Actual stream latency
  also depends on exclusive mode, format conversion, and the Windows audio
  engine.
- The tool does not play or record audio, so it cannot detect glitches, dropouts,
  or clock drift.
- There is no option to open a device in exclusive mode or change its format.
- Default devices are the ones reported by the WASAPI host API, not a separate
  query of Windows sound settings.
- Device names come from the driver and may contain non-ASCII text. Use a
  UTF-8 capable terminal or `--json` when copying names.
- Profiles are starting points. A device may reject a frame count or need more
  buffering to run without dropouts.

## Development

```powershell
pip install -e ".[dev]" --no-cache-dir
python -m pytest
python tools/check_text.py
```

`tools/check_text.py` fails on em dashes, en dashes, and a list of banned
marketing phrases in repository text files. CI runs it together with pytest on
windows-latest with Python 3.10, 3.11, and 3.12.

## License

MIT. See [LICENSE](LICENSE).
