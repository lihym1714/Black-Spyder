rule android_network_security_config
{
    meta:
        category = "transport"
        platform = "android"
    strings:
        $a = "networkSecurityConfig"
        $b = "cleartextTrafficPermitted"
    condition:
        any of them
}

rule android_debug_backup_flags
{
    meta:
        category = "debug-backup"
        platform = "android"
    strings:
        $a = "android:debuggable=\"true\""
        $b = "android:allowBackup=\"true\""
    condition:
        any of them
}

rule android_exported_components
{
    meta:
        category = "component-exposure"
        platform = "android"
    strings:
        $a = "android:exported=\"true\""
    condition:
        $a
}

rule android_pinning_or_attestation_clues
{
    meta:
        category = "security-control"
        platform = "android"
    strings:
        $a = "CertificatePinner"
        $b = "Play Integrity"
        $c = "SafetyNet"
        $d = "RootBeer"
    condition:
        any of them
}

rule android_webview_hardening_clues
{
    meta:
        category = "webview"
        platform = "android"
    strings:
        $a = "setJavaScriptEnabled"
        $b = "setAllowFileAccess"
        $c = "setWebContentsDebuggingEnabled"
        $d = "android.webkit.WebView"
    condition:
        any of them
}

rule ios_ats_and_links
{
    meta:
        category = "transport-links"
        platform = "ios"
    strings:
        $a = "NSAppTransportSecurity"
        $b = "NSAllowsArbitraryLoads"
        $c = "CFBundleURLTypes"
        $d = "com.apple.developer.associated-domains"
    condition:
        any of them
}

rule ios_attestation_and_integrity_clues
{
    meta:
        category = "security-control"
        platform = "ios"
    strings:
        $a = "DeviceCheck"
        $b = "AppAttest"
        $c = "DCAppAttestService"
        $d = "amIJailbroken"
    condition:
        any of them
}

rule mobile_backend_endpoint_clues
{
    meta:
        category = "backend-clue"
        platform = "generic"
    strings:
        $a = "https://"
        $b = "http://"
        $c = "wss://"
        $d = "ws://"
        $e = "apiBaseUrl"
        $f = "baseUrl"
    condition:
        any of them
}
