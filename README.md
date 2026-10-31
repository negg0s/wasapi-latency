# wasapi-latency

A small Python CLI for inspecting Windows WASAPI host API settings and
recommending buffer sizes/latency profiles.

## Install (editable)

```bash
pip install -e .
```

Dependencies are `click` and `sounddevice` (already installed globally).

## Commands

```bash
wasapi-latency info
wasapi-latency measure
wasapi-latency measure --device 8
wasapi-latency profiles
wasapi-latency recommend --profile balanced
wasapi-latency recommend --profile gaming --device 8 --json
wasapi-latency doctor
```

## Profiles

Frames and milliseconds are given at 48 kHz:

| Profile  | Frames | ms @ 48k |
|----------|--------|----------|
| safe     | 1024   | 21.33    |
| balanced | 512    | 10.67    |
| gaming   | 256    | 5.33     |
| low      | 128    | 2.67     |
| ultra    | 64     | 1.33     |

## License

MIT
```
