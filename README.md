# eos-mcp

An MCP server for controlling [ETC Eos family](https://www.etcconnect.com/) lighting consoles
(Eos, Gio, Ion, ETCnomad) over OSC. It exposes the console's command line, playback, selection,
levels, colour, position, faders, direct selects, and macros as MCP tools, and mirrors the
console's live status so a model can read back what it just did.

Implements the OSC surface documented in
[Using OSC with Eos](https://www.etcconnect.com/WebDocs/Controls/EosFamilyOnlineHelp/en/Content/23_Show_Control/08_OSC/Using_OSC_with_Eos/OSC_Eos_Control.htm).

> **This drives real lights.** Commands take effect immediately on whatever the console is
> connected to. Point it at ETCnomad offline, or a console in Blind, until you trust it.

## How it works

Two independent UDP paths:

```
                 commands  ->  EOS_PORT_TX (console's "OSC UDP RX Port")
  eos-mcp  ──────────────────────────────────────────────────────►  Eos console
           ◄──────────────────────────────────────────────────────
                 status    <-  EOS_PORT_RX (console's "OSC UDP TX Port")
```

Status is **push-based**: the server knows only what the console has sent it. Nothing is
polled. Call `sync_state` once at the start of a session to ask Eos to publish its current
state, and again whenever data looks stale.

```
eos_mcp/
├── app.py            FastMCP instance
├── server.py         entry point: logging, listener startup, mcp.run()
├── config.py         EosConfig, validated from the environment
├── state.py          console state + lock + snapshot()
├── errors.py         EosConfigError / EosValidationError / EosSendError
├── logging_setup.py  stderr logging (stdout carries the MCP protocol)
├── osc/
│   ├── address.py    validates anything interpolated into an OSC address
│   ├── client.py     EosClient - lazy socket, structured send errors
│   └── listener.py   OscListener - receives status, folds it into state
└── tools/            one module per area of the console
```

## Prerequisites

- An Eos family console or ETCnomad
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/) — no separate Python install
  or clone needed; `uv` fetches Python and the server itself.

## Setup

**1. Enable OSC on the console.**
Browser → Setup → System Settings → System → Show Control → OSC:

| Setting | Value |
| --- | --- |
| OSC RX | Enabled |
| OSC TX | Enabled |
| OSC UDP RX Port | `8000` |
| OSC UDP TX Port | `9001` |

`OSC UDP RX Port` must match this server's `EOS_PORT_TX`, and `OSC UDP TX Port` must match its
`EOS_PORT_RX`. They are named from the console's point of view, so they look crossed over.

**2. Add it to your MCP client.**

For Claude Desktop, add this to `claude_desktop_config.json`
(Settings → Developer → Edit Config):

```json
{
  "mcpServers": {
    "eos": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/MaybeItsAdam/eos-mcp", "eos-mcp"],
      "env": {
        "EOS_IP": "127.0.0.1",
        "EOS_PORT_TX": "8000",
        "EOS_PORT_RX": "9001"
      }
    }
  }
}
```

`uvx` fetches and caches the server straight from GitHub on first launch — nothing to clone or
install by hand. Restart Claude Desktop after editing the config. Any MCP client that launches a
command works the same way; drop the `command`/`args`/`env` above into its config format.

To pin to a specific commit instead of tracking `main`, append `@<commit-sha>` to the repo URL,
e.g. `"git+https://github.com/MaybeItsAdam/eos-mcp@<sha>"`.

The server also publishes a `system_instructions` prompt covering how to sync state and when
to confirm before acting.

## Configuration

All optional. Defaults suit ETCnomad running on the same machine.

| Variable | Default | Description |
| --- | --- | --- |
| `EOS_IP` | `127.0.0.1` | Console address to send commands to. |
| `EOS_PORT_TX` | `8000` | Port commands are sent to. Match the console's **OSC UDP RX Port**. |
| `EOS_PORT_RX` | `9001` | Port status is received on. Match the console's **OSC UDP TX Port**. |
| `EOS_RX_HOST` | `0.0.0.0` | Local interface the listener binds to. |
| `EOS_LOG_LEVEL` | `INFO` | `DEBUG` logs every OSC message sent and received. |

Invalid values are rejected at startup with a message naming the variable.

## Tools

Every tool returns a structured result with an `ok` field. `ok: false` means the command never
reached the console, and `error` says why — check it rather than assuming success.

**Diagnostics** — `get_connection_health`, `sync_state`

**Status** — `get_active_cue`, `get_pending_cue`, `get_live_blind_state`, `get_command_line`,
`get_selection`, `get_faders`, `get_direct_selects`, `get_system_state`

**Command line** — `command_line` (anything the console can do, including destructive
operations)

**Levels** — `set_level`, `apply_modifier`, `set_parameter`, `set_parameter_mod`, `set_dmx`

**Selection** — `select_channel` (accepts `"5"` or `"1 Thru 10"`), `select_group`,
`select_effect`, `select_curve`, `select_pixel_map`, `select_address_target`,
`open_magic_sheet`

**Playback** — `fire_cue` (point cues supported), `go_cue`, `stop_back_cue`, `reset_osc`

**Colour and position** — `set_color_rgb`, `set_color_hs`, `set_color_xy`, `set_pan_tilt`,
`set_xyz`

**Faders and direct selects** — `set_fader`, `control_fader_button`, `press_direct_select`

**Presets** — `fire_preset`, `fire_palette`, `recall_snapshot`, `bump_sub`

**Keys and macros** — `press_key`, `press_softkey`, `fire_macro`

**Encoders** — `wheel_level`, `wheel_parameter`, `switch_parameter`

**Cue list banks** — `config_cue_list_bank`, `page_cue_list_bank`, `select_cue_list_bank_cue`,
`reset_cue_list_bank`

Argument ranges and valid values are declared in each tool's schema, so out-of-range input is
rejected before it reaches the console.

## Troubleshooting

Start with `get_connection_health` — it distinguishes the failure modes below.

**Queries say "no data reported yet".** Nothing has been requested. Call `sync_state`. If it
reports no reply, the console is not sending: check OSC **TX** is enabled, and that its OSC UDP
TX Port equals `EOS_PORT_RX`.

**`get_connection_health` reports a bind error.** Another process holds `EOS_PORT_RX`, often a
second copy of this server. Stop it, or set `EOS_PORT_RX` to a free port and change the
console's OSC UDP TX Port to match.

**Commands return `ok: false` with a send error.** The console is unreachable at `EOS_IP`.
Check the address, and that both machines are on the same network. UDP is fire-and-forget, so a
successful send only means the packet left this machine.

**Commands report `ok: true` but nothing happens.** The packets are leaving this machine, but
the console is not acting on them: check OSC **RX** is enabled and that its OSC UDP RX Port
equals `EOS_PORT_TX`. Also confirm the console is in Live rather than Blind —
`get_live_blind_state`.

**Firewall.** Both ports are UDP. On Windows, allow the Eos application and the Python
interpreter through the firewall.

**Nothing works and there is no log output.** Set `EOS_LOG_LEVEL=DEBUG`. Logs go to stderr;
your MCP client may hide them.

## Development

```bash
git clone https://github.com/MaybeItsAdam/eos-mcp
cd eos-mcp
uv sync --all-groups
uv run pytest          # test suite; no console required
uv run ruff check .
uv run ruff format .
uv run mypy
```

To point a client at your local checkout instead of GitHub, use
`"command": "uv", "args": ["--directory", "/absolute/path/to/eos-mcp", "run", "eos_server.py"]`
in place of the `uvx` block above.

The tests build genuine OSC datagrams and run them through the real python-osc dispatcher, and
the integration tests bind a listener on an ephemeral port, so the receive path is covered
without hardware.

Two rules the test suite enforces mechanically:

- **Never write to stdout.** Under the stdio transport stdout carries JSON-RPC frames; a stray
  `print()` corrupts the session. Use `eos_mcp.logging_setup.get_logger`.
  (`tests/test_no_stdout.py`)
- **Validate anything interpolated into an OSC address.** A `/` in a tool argument redirects
  the message to a different address on a live console. Use the helpers in
  `eos_mcp/osc/address.py`.

## Licence

MIT — see [LICENSE](LICENSE).
