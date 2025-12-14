# ETCnomad MCP

MCP server for communicating with ETCnomad via OSC

Implements all commands featured [here](https://www.etcconnect.com/WebDocs/Controls/EosFamilyOnlineHelp/en/Content/23_Show_Control/08_OSC/Using_OSC_with_Eos/OSC_Eos_Control.htm#OSCMacro)

## Prerequisites
- ETCnomad (Eos Family software)
- Python 3.10+
- `uv` or `pip`

## Setup

**Configure ETCnomad**:
   - Open Browser:Setup -> System Settings -> System -> Show Control -> OSC
   - Enable **OSC RX** and **OSC TX**
   - Set **OSC UDP RX Port** to 8000
   - Set **OSC UDP TX Port** to 9001

Install Dependencies:
```bash
uv sync
```

## Usage

### Running Locally
```bash
uv run eos_server.py
```

### Claude Desktop Configuration
Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "etc-nomad": {
      "command": "uv",
      "args": [
        "run",
        "--with",
        "fastmcp",
        "--with",
        "python-osc",
        "/absolute/path/to/eos_server.py"
      ]
    }
  }
}
```
