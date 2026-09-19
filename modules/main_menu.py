from core import ui


class MainMenu:
    def run(self) -> None:
        while True:
            ui.clear()
            ui.header("SENSIBLE TWEAKS  v1.0")
            print("     [1]  Network Tweaks")
            print("     [2]  CPU Tweaks")
            print("     [3]  GPU Tweaks")
            print("     [4]  RAM Tweaks")
            print("     [5]  Registry Tweaks")
            print("     [6]  Windows Settings")
            print("     [7]  FPS Tweaks")
            print("     [8]  Fortnite Tweaks")
            print("     [0]  Exit")
            print()
            c = ui.prompt().lower()

            if c == "1":
                from modules.network_menu import NetworkMenu
                NetworkMenu().run()
            elif c == "2":
                from modules.tweak_menu import SimpleTweakMenu
                from tweaks.cpu import build_cpu_tweaks
                SimpleTweakMenu("CPU TWEAKS", "cpu", build_cpu_tweaks).run()
            elif c == "3":
                from modules.tweak_menu import SimpleTweakMenu
                from tweaks.gpu import build_gpu_tweaks
                SimpleTweakMenu("GPU TWEAKS", "gpu", build_gpu_tweaks).run()
            elif c == "4":
                from modules.tweak_menu import SimpleTweakMenu
                from tweaks.ram import build_ram_tweaks
                SimpleTweakMenu("RAM TWEAKS", "ram", build_ram_tweaks).run()
            elif c == "5":
                from modules.tweak_menu import SimpleTweakMenu
                from tweaks.registry import build_registry_tweaks
                SimpleTweakMenu("REGISTRY TWEAKS", "registry", build_registry_tweaks).run()
            elif c == "6":
                from modules.tweak_menu import SimpleTweakMenu
                from tweaks.windows_settings import build_windows_settings_tweaks
                SimpleTweakMenu("WINDOWS SETTINGS", "winsettings", build_windows_settings_tweaks).run()
            elif c == "7":
                from modules.tweak_menu import SimpleTweakMenu
                from tweaks.fps import build_fps_tweaks
                SimpleTweakMenu("FPS TWEAKS", "fps", build_fps_tweaks).run()
            elif c == "8":
                from modules.tweak_menu import SimpleTweakMenu
                from tweaks.fortnite import build_fortnite_tweaks
                SimpleTweakMenu("FORTNITE TWEAKS", "fortnite", build_fortnite_tweaks).run()
            elif c == "0":
                return
