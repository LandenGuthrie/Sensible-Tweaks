"""General-purpose registry tweaks: telemetry, background services, Windows chrome noise."""
from .base import RegTweak

SEARCH_POLICY_KEY = r"HKLM\SOFTWARE\Policies\Microsoft\Windows\Windows Search"
APP_PRIVACY_KEY = r"HKLM\SOFTWARE\Policies\Microsoft\Windows\AppPrivacy"
CLOUD_CONTENT_KEY = r"HKLM\SOFTWARE\Policies\Microsoft\Windows\CloudContent"
DATA_COLLECTION_KEY = r"HKLM\SOFTWARE\Policies\Microsoft\Windows\DataCollection"
SYSTEM_POLICY_KEY = r"HKLM\SOFTWARE\Policies\Microsoft\Windows\System"
ADVERTISING_KEY = r"HKLM\SOFTWARE\Policies\Microsoft\Windows\AdvertisingInfo"
WINDOWS_AI_KEY = r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsAI"


def build_registry_tweaks():
    return [
        RegTweak(1, "Disable Telemetry",
                 "Set diagnostic data collection to the minimum ('Security') level",
                 DATA_COLLECTION_KEY, "AllowTelemetry", "REG_DWORD", 0),

        RegTweak(2, "Disable Cortana",
                 "Prevent Cortana from running",
                 SEARCH_POLICY_KEY, "AllowCortana", "REG_DWORD", 0),

        RegTweak(3, "Disable Search Web Results",
                 "Keep Start menu search local-only (no Bing web results)",
                 SEARCH_POLICY_KEY, "ConnectedSearchUseWeb", "REG_DWORD", 0),

        RegTweak(4, "Disable Background Apps",
                 "Force-deny apps from running in the background system-wide",
                 APP_PRIVACY_KEY, "LetAppsRunInBackground", "REG_DWORD", 2),

        RegTweak(5, "Disable Consumer Features",
                 "Stop Windows from auto-installing suggested/promotional apps",
                 CLOUD_CONTENT_KEY, "DisableWindowsConsumerFeatures", "REG_DWORD", 1),

        RegTweak(6, "Disable Start Menu Tips",
                 "Turn off 'suggestions' and tips injected into the Start menu",
                 CLOUD_CONTENT_KEY, "DisableSoftLanding", "REG_DWORD", 1),

        RegTweak(7, "Disable Windows Spotlight",
                 "Turn off lock-screen Spotlight ads/suggestions",
                 CLOUD_CONTENT_KEY, "DisableWindowsSpotlightFeatures", "REG_DWORD", 1),

        RegTweak(8, "Disable Diagnostic Tracking Service",
                 "Stop the DiagTrack (Connected User Experiences and Telemetry) service",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\DiagTrack",
                 "Start", "REG_DWORD", 4),

        RegTweak(9, "Disable Program Compatibility Assistant",
                 "Stop PcaSvc from monitoring app compatibility in the background",
                 r"HKLM\SYSTEM\CurrentControlSet\Services\PcaSvc",
                 "Start", "REG_DWORD", 4),

        RegTweak(10, "Disable Windows Search Indexing",
                  "Stop the WSearch service from indexing files in the background",
                  r"HKLM\SYSTEM\CurrentControlSet\Services\WSearch",
                  "Start", "REG_DWORD", 4),

        RegTweak(11, "Disable Activity Feed",
                  "Stop Windows from tracking your app/document activity feed",
                  SYSTEM_POLICY_KEY, "EnableActivityFeed", "REG_DWORD", 0),

        RegTweak(12, "Disable Activity Publishing",
                  "Stop this PC from publishing your activity history to Microsoft",
                  SYSTEM_POLICY_KEY, "PublishUserActivities", "REG_DWORD", 0),

        RegTweak(13, "Disable Activity Upload",
                  "Stop this PC from uploading activity history to your Microsoft account",
                  SYSTEM_POLICY_KEY, "UploadUserActivities", "REG_DWORD", 0),

        RegTweak(14, "Disable Advertising ID",
                  "Stop apps from using your per-user advertising ID for targeted ads",
                  ADVERTISING_KEY, "DisabledByGroupPolicy", "REG_DWORD", 1),

        RegTweak(15, "Disable Clipboard History",
                  "Turn off the Win+V clipboard history feature",
                  SYSTEM_POLICY_KEY, "AllowClipboardHistory", "REG_DWORD", 0),

        RegTweak(16, "Disable Cross-Device Clipboard Sync",
                  "Stop clipboard contents from syncing to your Microsoft account/other devices",
                  SYSTEM_POLICY_KEY, "AllowCrossDeviceClipboard", "REG_DWORD", 0),

        RegTweak(17, "Disable Windows Recall Data Analysis",
                  "Block the Recall/AI Explorer snapshot-and-analyze feature (Windows 11 24H2+)",
                  WINDOWS_AI_KEY, "DisableAIDataAnalysis", "REG_DWORD", 1),

        RegTweak(18, "Block Recall Enablement",
                  "Prevent Recall from being enabled at all on this device",
                  WINDOWS_AI_KEY, "AllowRecallEnablement", "REG_DWORD", 0),

        RegTweak(19, "Disable Xbox Auth Manager Service",
                  "Stop XblAuthManager background service "
                  "(only needed for Xbox Live sign-in, not local play)",
                  r"HKLM\SYSTEM\CurrentControlSet\Services\XblAuthManager",
                  "Start", "REG_DWORD", 4),

        RegTweak(20, "Disable Xbox Game Save Service",
                  "Stop XblGameSave background service (Xbox Live cloud saves)",
                  r"HKLM\SYSTEM\CurrentControlSet\Services\XblGameSave",
                  "Start", "REG_DWORD", 4),

        RegTweak(21, "Disable Xbox Networking Service",
                  "Stop XboxNetApiSvc background service (Xbox Live networking)",
                  r"HKLM\SYSTEM\CurrentControlSet\Services\XboxNetApiSvc",
                  "Start", "REG_DWORD", 4),

        RegTweak(22, "Disable Xbox Accessory Management Service",
                  "Stop XboxGipSvc background service "
                  "(only needed for Xbox controller accessory features - "
                  "leave enabled if you use an Xbox controller)",
                  r"HKLM\SYSTEM\CurrentControlSet\Services\XboxGipSvc",
                  "Start", "REG_DWORD", 4),
    ]
