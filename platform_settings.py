import socket

import sublime
import sublime_plugin


class PlatformSettingsEventListener(sublime_plugin.EventListener):
    def check_settings(self, view, first=False):
        s = view.settings()
        default_keys = ["${platform}", "user_${platform}", "${hostname}", "${platform}_${hostname}"]
        keys = s.get("platform_settings_keys", default_keys)
        if not keys:
            keys = default_keys

        hostname = socket.gethostname().split('.')[0].casefold()

        if not first:
            first = not s.get("platform_settings_was_here", False)
        if not first:
            s.clear_on_change("platform_settings")

        platform_settings = {}
        for key in keys:
            key = key.replace("${platform}", sublime.platform())
            key = key.replace("${hostname}", hostname)
            platform_settings.update(s.get(key, {}) or {})

        for key in platform_settings:
            current = s.get(key, None)
            value = platform_settings.get(key)
            if current != value:
                s.set(key, value)

        def on_change():
            self.check_settings(view)
        s.set("platform_settings_was_here", True)
        s.add_on_change("platform_settings", lambda: sublime.set_timeout(on_change, 0))

    def on_activated(self, view):
        self.check_settings(view)

    def on_new(self, view):
        self.check_settings(view, True)

    def on_load(self, view):
        self.check_settings(view, True)
