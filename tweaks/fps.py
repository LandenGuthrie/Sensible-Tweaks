"""General FPS/latency tweaks not tied to a specific game."""
from .base import RegTweak

GAMEBAR_KEY = r"HKCU\SOFTWARE\Microsoft\GameBar"
GAMECONFIG_KEY = r"HKCU\System\GameConfigStore"


def build_fps_tweaks():
    return [
        RegTweak(1, "Disable Game DVR (per-user)",
                 "Turn off the user-level Game DVR background recording toggle "
                 "(complements the machine-wide policy in GPU Tweaks)",
                 GAMECONFIG_KEY, "GameDVR_Enabled", "REG_DWORD", 0),

        RegTweak(2, "Disable Xbox Game Bar Overlay",
                 "Stop Win+G from launching the Game Bar overlay app",
                 GAMEBAR_KEY, "UseNexusForGameBarEnabled", "REG_DWORD", 0),

        RegTweak(3, "Disable Game Bar Startup Tip",
                 "Stop the 'press Win+G to open Game Bar' tip from popping up in games",
                 GAMEBAR_KEY, "ShowStartupPanel", "REG_DWORD", 0),
    ]
