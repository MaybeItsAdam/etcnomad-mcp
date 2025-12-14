
from fastmcp import FastMCP
from pythonosc import udp_client, dispatcher, osc_server
import threading
import time

mcp = FastMCP("ETC Nomad")

EOS_IP = "127.0.0.1"
EOS_PORT_TX = 8000
EOS_PORT_RX = 9001

client = udp_client.SimpleUDPClient(EOS_IP, EOS_PORT_TX)

eos_state = {
    "active_cue_list": None,
    "active_cue_number": None,
    "active_cue_percent": 0.0,
    "active_cue_text": "",
    "pending_cue_list": None,
    "pending_cue_number": None,
    "pending_cue_text": "",
    "live_blind_state": 1, 
    "command_line": "",
    "active_channels": "",
    "faders": {},
    "direct_selects": {},
    "wheels": {},
    "pantilt": [], 
    "xyz": []
}

def handle_active_cue(address, *args):
    """
    Handles /eos/out/active/cue/<list>/<cue> (float argument)
    Example address: /eos/out/active/cue/1/5
    """
    parts = address.split('/')
    if len(parts) >= 7:
        list_num = parts[5]
        cue_num = parts[6]
        percent = args[0] if args else 0.0

        eos_state["active_cue_list"] = list_num
        eos_state["active_cue_number"] = cue_num
        eos_state["active_cue_percent"] = percent

def handle_active_cue_text(address, *args):
    """Handles /eos/out/active/cue/text (string argument)"""
    if args:
        eos_state["active_cue_text"] = args[0]

def handle_pending_cue(address, *args):
    """
    Handles /eos/out/pending/cue/<list>/<cue>
    """
    parts = address.split('/')
    if len(parts) >= 7:
        list_num = parts[5]
        cue_num = parts[6]
        
        eos_state["pending_cue_list"] = list_num
        eos_state["pending_cue_number"] = cue_num

def handle_pending_cue_text(address, *args):
    """Handles /eos/out/pending/cue/text (string argument)"""
    if args:
        eos_state["pending_cue_text"] = args[0]

def handle_live_blind(address, *args):
    """Handles /eos/out/event/state (0=Blind, 1=Live)"""
    if args:
        eos_state["live_blind_state"] = args[0]

def handle_command_line(address, *args):
    """Handles /eos/out/cmd and /eos/out/user/<num>/cmd"""
    if args:
        eos_state["command_line"] = args[0]

def handle_active_chan(address, *args):
    """Handles /eos/out/active/chan"""
    if args:
        eos_state["active_channels"] = args[0]

def handle_fader_bank_label(address, *args):
    """Handles /eos/out/fader/<index> (bank label)"""
    parts = address.split('/')
    if len(parts) >= 5:
        bank = int(parts[4])
        if bank not in eos_state["faders"]: eos_state["faders"][bank] = {"bank_label": "", "faders": {}}
        if args: eos_state["faders"][bank]["bank_label"] = args[0]

def handle_fader_level(address, *args):
    """Handles /eos/out/fader/<index>/<fader> (level)"""
    parts = address.split('/')
    if len(parts) >= 6:
        bank = int(parts[4])
        fader = int(parts[5])
        if bank not in eos_state["faders"]: eos_state["faders"][bank] = {"bank_label": "", "faders": {}}
        if fader not in eos_state["faders"][bank]["faders"]: eos_state["faders"][bank]["faders"][fader] = {'level': 0.0, 'label': ''}
        
        if args and isinstance(args[0], float):
             eos_state["faders"][bank]["faders"][fader]['level'] = args[0]

def handle_fader_label(address, *args):
    """Handles /eos/out/fader/<index>/<fader>/name"""
    parts = address.split('/')
    if len(parts) >= 7:
        bank = int(parts[4])
        fader = int(parts[5])
        if bank not in eos_state["faders"]: eos_state["faders"][bank] = {"bank_label": "", "faders": {}}
        if fader not in eos_state["faders"][bank]["faders"]: eos_state["faders"][bank]["faders"][fader] = {'level': 0.0, 'label': ''}
        
        if args:
            eos_state["faders"][bank]["faders"][fader]['label'] = args[0]

def handle_ds_bank_label(address, *args):
    """Handles /eos/out/ds/<index>"""
    parts = address.split('/')
    if len(parts) >= 5:
        bank = int(parts[4])
        if bank not in eos_state["direct_selects"]: eos_state["direct_selects"][bank] = {"label": "", "buttons": {}}
        if args: eos_state["direct_selects"][bank]["label"] = args[0]

def handle_ds_button_label(address, *args):
    """Handles /eos/out/ds/<index>/<button>"""
    parts = address.split('/')
    if len(parts) >= 6:
        bank = int(parts[4])
        btn = int(parts[5])
        if bank not in eos_state["direct_selects"]: eos_state["direct_selects"][bank] = {"label": "", "buttons": {}}
        if args: eos_state["direct_selects"][bank]["buttons"][btn] = args[0]

def handle_wheel_mode(address, *args):
    if args: eos_state["wheels"]["mode"] = args[0]

def handle_pantilt(address, *args):
    eos_state["pantilt"] = list(args)

def handle_xyz(address, *args):
    eos_state["xyz"] = list(args)

def default_handler(address, *args):
    pass

def start_osc_listener():
    disp = dispatcher.Dispatcher()
    
    disp.map("/eos/out/active/cue/*/*", handle_active_cue)
    disp.map("/eos/out/active/cue/text", handle_active_cue_text)
    disp.map("/eos/out/pending/cue/*/*", handle_pending_cue)
    disp.map("/eos/out/pending/cue/text", handle_pending_cue_text)
    
    disp.map("/eos/out/event/state", handle_live_blind)
    disp.map("/eos/out/cmd", handle_command_line)
    disp.map("/eos/out/user/*/cmd", handle_command_line)
    disp.map("/eos/out/active/chan", handle_active_chan)
    disp.map("/eos/out/wheel", handle_wheel_mode)
    disp.map("/eos/out/pantilt", handle_pantilt)
    disp.map("/eos/out/xyz", handle_xyz)

    disp.map("/eos/out/fader/*", handle_fader_bank_label)
    disp.map("/eos/out/fader/*/*", handle_fader_level)
    disp.map("/eos/out/fader/*/*/name", handle_fader_label)

    disp.map("/eos/out/ds/*", handle_ds_bank_label)
    disp.map("/eos/out/ds/*/*", handle_ds_button_label)

    disp.set_default_handler(default_handler)

    server = osc_server.ThreadingOSCUDPServer(("0.0.0.0", EOS_PORT_RX), disp)
    print(f"Serving OSC listener on port {EOS_PORT_RX}")
    server.serve_forever()

listener_thread = threading.Thread(target=start_osc_listener, daemon=True)
listener_thread.start()

@mcp.tool()
def command_line(command: str) -> str:
    """Sends a command to the ETC Nomad command line.
    
    Args:
        command: The command string (e.g., "Chan 1 At 50").
    """
    address = "/eos/cmd"
    client.send_message(address, command)
    print(f"Sent: {address} '{command}'")
    return f"Sent command: {command}"

@mcp.tool()
def set_level(value: float) -> str:
    """Sets the level of the currently selected channels (0-100)."""
    address = "/eos/at"
    client.send_message(address, value)
    print(f"Sent: {address} {value}")
    return f"Set level to {value}"

@mcp.tool()
def set_level_mod(modification: str) -> str:
    """Sets level variants.
    
    Args:
        modification: "out", "home", "remdim", "level", "full", "min", "max", "+%", "-%".
    """
    address = f"/eos/at/{modification}"
    client.send_message(address, [])
    print(f"Sent: {address}")
    return f"Set level modification: {modification}"

@mcp.tool()
def set_channel_mod(channel: int, modification: str) -> str:
    """Sets level variants for a specific channel.
    
    Args:
        channel: Channel number.
        modification: "out", "home", "remdim", "level", "full", "min", "max", "+%", "-%".
    """
    address = f"/eos/chan/{channel}/{modification}"
    client.send_message(address, [])
    print(f"Sent: {address}")
    return f"Set Channel {channel} mod: {modification}"

@mcp.tool()
def set_group_mod(group: int, modification: str) -> str:
    """Sets level variants for a specific group.
    
    Args:
        group: Group number.
        modification: "out", "home", "remdim", "level", "full", "min", "max", "+%", "-%".
    """
    address = f"/eos/group/{group}/{modification}"
    client.send_message(address, [])
    print(f"Sent: {address}")
    return f"Set Group {group} mod: {modification}"

@mcp.tool()
def set_parameter(param: str, value: float) -> str:
    """Sets a specific parameter to a value.
    
    Args:
        param: Parameter name (e.g., "pan", "tilt", "zoom").
        value: Value to set.
    """
    address = f"/eos/param/{param}"
    client.send_message(address, value)
    print(f"Sent: {address} {value}")
    return f"Set {param} to {value}"

@mcp.tool()
def set_parameter_mod(param: str, modification: str) -> str:
    """Sets parameter variants.
    
    Args:
        param: Parameter name.
        modification: "out", "home", "level", "full", "min", "max", "+%", "-%".
    """
    address = f"/eos/param/{param}/{modification}"
    client.send_message(address, [])
    print(f"Sent: {address}")
    return f"Set {param} modification: {modification}"

@mcp.tool()
def set_dmx(address_num: int, value: int) -> str:
    """Sets a DMX address to a level (0-255)."""
    address = f"/eos/addr/{address_num}/DMX"
    client.send_message(address, value)
    print(f"Sent: {address} {value}")
    return f"Set DMX address {address_num} to {value}"

@mcp.tool()
def wheel_level(ticks: float) -> str:
    """Adjusts the level wheel.
    
    Args:
        ticks: Number of ticks (positive/negative). e.g. 1.0, -1.0.
    """
    address = "/eos/wheel/level"
    client.send_message(address, ticks)
    print(f"Sent: {address} {ticks}")
    return f"Adjusted Level Wheel by {ticks}"

@mcp.tool()
def wheel_parameter(param: str, ticks: float) -> str:
    """Adjusts a parameter wheel.
    
    Args:
        param: Parameter name (e.g. "pan").
        ticks: Number of ticks.
    """
    address = f"/eos/wheel/{param}"
    client.send_message(address, ticks)
    print(f"Sent: {address} {ticks}")
    return f"Adjusted {param} Wheel by {ticks}"

@mcp.tool()
def switch_parameter(param: str, ticks: float) -> str:
    """Sets switch mode for repeats.
    
    Args:
        param: Parameter name.
        ticks: Tick rate.
    """
    address = f"/eos/switch/{param}"
    client.send_message(address, ticks)
    print(f"Sent: {address} {ticks}")
    return f"Set Switch {param} to {ticks}"

@mcp.tool()
def set_xyz(x: float, y: float, z: float) -> str:
    """Sets XYZ position."""
    address = "/eos/xyz"
    client.send_message(address, [x, y, z])
    print(f"Sent: {address} {x}, {y}, {z}")
    return f"Set XYZ to {x}, {y}, {z}"

@mcp.tool()
def set_color_hs(hue: float, saturation: float) -> str:
    """Sets color using Hue (0-360) and Saturation (0-100)."""
    address = "/eos/color/hs"
    client.send_message(address, [hue, saturation])
    print(f"Sent: {address} {hue}, {saturation}")
    return f"Set Color HS: {hue}, {saturation}"

@mcp.tool()
def set_color_rgb(red: float, green: float, blue: float) -> str:
    """Sets color using RGB values (0.0-1.0)."""
    address = "/eos/color/rgb"
    client.send_message(address, [red, green, blue])
    print(f"Sent: {address} {red}, {green}, {blue}")
    return f"Set Color RGB: {red}, {green}, {blue}"

@mcp.tool()
def set_color_xy(x: float, y: float) -> str:
    """Sets color using CIE xy coordinates (0.0-1.0)."""
    address = "/eos/color/xy"
    client.send_message(address, [x, y])
    print(f"Sent: {address} {x}, {y}")
    return f"Set Color XY: {x}, {y}"

@mcp.tool()
def set_pan_tilt(pan: float, tilt: float) -> str:
    """Sets Pan and Tilt (0.0-1.0 range usually maps to max range)."""
    address = "/eos/pantilt/xy"
    client.send_message(address, [pan, tilt])
    print(f"Sent: {address} {pan}, {tilt}")
    return f"Set Pan/Tilt to {pan}, {tilt}"

@mcp.tool()
def select_channel(channel: str) -> str:
    """Selects a channel number (or range string)."""
    address = "/eos/chan"
    try:
        val = int(channel)
        client.send_message(address, val)
    except ValueError:
        return f"Invalid channel number: {channel}. Use command_line for ranges."
    print(f"Sent: {address} {channel}")
    return f"Selected Channel {channel}"

@mcp.tool()
def select_group(group: int) -> str:
    """Selects a group."""
    address = "/eos/group"
    client.send_message(address, group)
    print(f"Sent: {address} {group}")
    return f"Selected Group {group}"

@mcp.tool()
def select_address_target(address_num: int) -> str:
    """Selects an address (as a target)."""
    address = "/eos/addr"
    client.send_message(address, address_num)
    print(f"Sent: {address} {address_num}")
    return f"Selected Address {address_num}"

@mcp.tool()
def select_curve(curve: int) -> str:
    """Selects a curve."""
    address = "/eos/curve"
    client.send_message(address, curve)
    print(f"Sent: {address} {curve}")
    return f"Selected Curve {curve}"

@mcp.tool()
def select_effect(effect: int) -> str:
    """Selects an effect."""
    address = "/eos/fx"
    client.send_message(address, effect)
    print(f"Sent: {address} {effect}")
    return f"Selected Effect {effect}"

@mcp.tool()
def select_pixel_map(pixmap: int) -> str:
    """Selects a Pixel Map."""
    address = "/eos/pixmap"
    client.send_message(address, pixmap)
    print(f"Sent: {address} {pixmap}")
    return f"Selected Pixel Map {pixmap}"

@mcp.tool()
def open_magic_sheet(ms: int) -> str:
    """Opens a Magic Sheet."""
    address = "/eos/ms"
    client.send_message(address, ms)
    print(f"Sent: {address} {ms}")
    return f"Opened Magic Sheet {ms}"

@mcp.tool()
def press_key(key_name: str) -> str:
    """Presses and releases a hardkey (e.g., "Data", "About", "Go_To_Cue")."""
    address = f"/eos/key/{key_name}"
    client.send_message(address, 1.0)
    client.send_message(address, 0.0)
    print(f"Sent Key Press: {key_name}")
    return f"Pressed key {key_name}"

@mcp.tool()
def fire_macro(macro: int) -> str:
    """Fires a macro."""
    address = "/eos/macro/fire"
    client.send_message(address, macro)
    print(f"Sent: {address} {macro}")
    return f"Fired Macro {macro}"

@mcp.tool()
def press_softkey(index: int) -> str:
    """Presses a softkey (1-12)."""
    address = f"/eos/softkey/{index}"
    client.send_message(address, 1.0)
    client.send_message(address, 0.0)
    print(f"Sent Softkey: {index}")
    return f"Pressed Softkey {index}"

@mcp.tool()
def fire_preset(preset: int) -> str:
    """Fires (recalls) a preset."""
    address = "/eos/preset/fire"
    client.send_message(address, preset)
    print(f"Sent: {address} {preset}")
    return f"Fired Preset {preset}"

@mcp.tool()
def fire_palette(palette_type: str, number: int) -> str:
    """Fires a palette.
    
    Args:
        palette_type: "intensity" (ip), "focus" (fp), "color" (cp), or "beam" (bp).
        number: Palette number.
    """
    type_map = {
        "intensity": "ip", "ip": "ip",
        "focus": "fp", "fp": "fp",
        "color": "cp", "cp": "cp",
        "beam": "bp", "bp": "bp"
    }
    pt = type_map.get(palette_type.lower())
    if not pt:
        return "Invalid palette type. Use intensity, focus, color, or beam."
    
    address = f"/eos/{pt}/fire"
    client.send_message(address, number)
    print(f"Sent: {address} {number}")
    return f"Fired {palette_type} palette {number}"

@mcp.tool()
def recall_snapshot(snapshot: int) -> str:
    """Recalls a snapshot."""
    address = "/eos/snap"
    client.send_message(address, snapshot)
    print(f"Sent: {address} {snapshot}")
    return f"Recalled Snapshot {snapshot}"

@mcp.tool()
def bump_sub(sub: int, level: float = 1.0) -> str:
    """Bumps a submaster to a level (default 1.0 / 100%)."""
    address = f"/eos/sub/{sub}/fire"
    client.send_message(address, level)
    print(f"Sent: {address} {level}")
    return f"Bumped Sub {sub} to {level}"

@mcp.tool()
def set_fader(bank: int, fader: int, level: float) -> str:
    """Sets a fader level (0.0-1.0)."""
    address = f"/eos/fader/{bank}/{fader}"
    client.send_message(address, level)
    print(f"Sent: {address} {level}")
    return f"Set Fader {bank}/{fader} to {level}"

@mcp.tool()
def control_fader_button(bank: int, fader: int, action: str) -> str:
    """Controls fader buttons.
    
    Args:
        bank: Fader bank/index.
        fader: Fader index.
        action: "load", "unload", "stop", "fire".
    """
    address = f"/eos/fader/{bank}/{fader}/{action}"
    client.send_message(address, [])
    print(f"Sent: {address}")
    return f"Fader {bank}/{fader} action: {action}"

@mcp.tool()
def press_direct_select(bank: int, button: int) -> str:
    """Presses a direct select button."""
    address = f"/eos/ds/{bank}/{button}"
    client.send_message(address, 1.0)
    client.send_message(address, 0.0)
    print(f"Sent DS Press: {bank}/{button}")
    return f"Pressed Direct Select {bank}/{button}"

@mcp.tool()
def config_cue_list_bank(index: int, list_num: int, prev: int = 2, pending: int = 6) -> str:
    """Configures an OSC Cue List Bank."""
    address = f"/eos/cuelist/{index}/config/{list_num}/{prev}/{pending}"
    client.send_message(address, [])
    print(f"Sent: {address}")
    return f"Configured Cue List Bank {index} for List {list_num}"

@mcp.tool()
def page_cue_list_bank(index: int, delta: int) -> str:
    """Pages a Cue List Bank up or down."""
    address = f"/eos/cuelist/{index}/page/{delta}"
    client.send_message(address, [])
    print(f"Sent: {address}")
    return f"Paged Cue List Bank {index} by {delta}"

@mcp.tool()
def select_cue_list_bank_cue(index: int, cue: str) -> str:
    """Selects a cue in a Cue List Bank (jumps to it)."""
    address = f"/eos/cuelist/{index}/select/{cue}"
    client.send_message(address, [])
    print(f"Sent: {address}")
    return f"Cue List Bank {index} jump to cue {cue}"

@mcp.tool()
def reset_cue_list_bank(index: int) -> str:
    """Resets a Cue List Bank."""
    address = f"/eos/cuelist/{index}/reset"
    client.send_message(address, [])
    print(f"Sent: {address}")
    return f"Reset Cue List Bank {index}"

# --- Cues ---

@mcp.tool()
def fire_cue(list_number: int, cue_number: str) -> str:
    """Fires a specific cue."""
    address = f"/eos/cue/{list_number}/{cue_number}/fire"
    client.send_message(address, 1.0)
    print(f"Sent: {address}")
    return f"Fired cue {cue_number} in list {list_number}"

@mcp.tool()
def go_cue() -> str:
    """Presses the Go button for the master playback pair."""
    address = "/eos/key/go_0"
    client.send_message(address, 1.0)
    client.send_message(address, 0.0)
    print(f"Sent Go")
    return "Pressed Go"

@mcp.tool()
def stop_back_cue() -> str:
    """Presses the Stop/Back button."""
    address = "/eos/key/stop"
    client.send_message(address, 1.0)
    client.send_message(address, 0.0)
    print(f"Sent Stop/Back")
    return "Pressed Stop/Back"

@mcp.tool()
def get_active_cue() -> str:
    """Returns the current active cue."""
    if eos_state["active_cue_number"] is None:
        return "No active cue data received yet."
    return (f"Active Cue: {eos_state['active_cue_list']}/{eos_state['active_cue_number']} "
            f"({eos_state['active_cue_percent']*100:.0f}%) "
            f"Label: '{eos_state['active_cue_text']}'")

@mcp.tool()
def get_pending_cue() -> str:
    """Returns the current pending cue."""
    if eos_state["pending_cue_number"] is None:
        return "No pending cue data received yet."
    return (f"Pending Cue: {eos_state['pending_cue_list']}/{eos_state['pending_cue_number']} "
            f"Label: '{eos_state['pending_cue_text']}'")

@mcp.tool()
def get_live_blind_state() -> str:
    """Returns current Live/Blind state."""
    state = "Live" if eos_state["live_blind_state"] == 1 else "Blind"
    return f"Console State: {state}"

@mcp.tool()
def request_setup() -> str:
    """Requests setup info."""
    address = "/eos/get/setup"
    client.send_message(address, [])
    print(f"Sent: {address}")
    return "Requested setup info."

@mcp.tool()
def reset_osc() -> str:
    """Resets OSC connections."""
    address = "/eos/reset"
    client.send_message(address, [])
    print(f"Sent: {address}")
    return "Sent OSC Reset"

@mcp.tool()
def get_command_line() -> str:
    """Returns the current command line text."""
    return f"Command Line: {eos_state['command_line']}"

@mcp.tool()
def get_selection() -> str:
    """Returns the current active channel selection."""
    return f"Selected Channels: {eos_state['active_channels']}"

@mcp.tool()
def get_faders(bank: int) -> str:
    """Returns the status of faders in a specific bank (1-based)."""
    if bank not in eos_state["faders"]:
        return f"No data for Fader Bank {bank}"
    
    data = eos_state["faders"][bank]
    bank_info = f"Bank {bank} ({data['bank_label']}):\n"
    fader_info = []
    for f_idx, f_data in data["faders"].items():
        fader_info.append(f"  Fader {f_idx}: {f_data['label']} = {f_data['level']:.2f}")
    
    if not fader_info: return bank_info + "  No faders populated."
    return bank_info + "\n".join(fader_info)

@mcp.tool()
def get_direct_selects(bank: int) -> str:
    """Returns the status of a Direct Select bank (1-based)."""
    if bank not in eos_state["direct_selects"]:
        return f"No data for DS Bank {bank}"
    
    data = eos_state["direct_selects"][bank]
    bank_info = f"DS Bank {bank} ({data['label']}):\n"
    btn_info = []
    for btn_idx, label in data["buttons"].items():
        btn_info.append(f"  Btn {btn_idx}: {label}")
    
    if not btn_info: return bank_info + "  No buttons populated."
    return bank_info + "\n".join(btn_info)

@mcp.tool()
def get_system_state() -> str:
    """Returns aggregate system state information."""
    state_str = "Live" if eos_state["live_blind_state"] == 1 else "Blind"
    wheel_mode = eos_state["wheels"].get("mode", "Unknown")
    
    info = [
        f"Console State: {state_str}",
        f"Wheel Mode: {wheel_mode}",
    ]
    if eos_state["pantilt"]:
        info.append(f"Pan/Tilt: {eos_state['pantilt']}")
    if eos_state["xyz"]:
        info.append(f"XYZ: {eos_state['xyz']}")
    
    return "\n".join(info)

@mcp.tool()
def sync_state() -> str:
    """
    Forces Eos to re-send all current status information.
    STRONGLY RECOMMENDED: Call this tool immediately upon startup to populate the state.
    """
    client.send_message("/eos/get/cue/active", [])
    client.send_message("/eos/get/cue/pending", [])
    
    client.send_message("/eos/get/version", [])
    client.send_message("/eos/get/cmd", [])
    client.send_message("/eos/get/setup", [])

    # Request fader banks (0, 1, 2)
    client.send_message("/eos/fader/0/config", []) 
    client.send_message("/eos/fader/1/config", []) 
    
    # Request direct selects bank 1
    client.send_message("/eos/ds/1/config", [])
    
    return "Synchronization requests sent to Eos."

@mcp.prompt()
def system_instructions() -> str:
    """Returns the system instructions for using this MCP server."""
    return (
        "You are controlling an ETC Eos lighting console via OSC.\n"
        "The current state of the console (cues, faders, etc.) is NOT automatically known.\n"
        "You MUST call the `sync_state` tool immediately upon starting to populate the state.\n"
        "Wait for the confirmation message before querying for specific status.\n"
    )

if __name__ == "__main__":
    mcp.run()
