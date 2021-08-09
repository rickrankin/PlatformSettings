import io
import os
import platform
import re
import socket

import sublime
import sublime_plugin


class VersionError(Exception):
    pass


class Version:
    __version_rx = re.compile(r'(?P<major>\d+)'
                              r'(\.(?P<minor>\d+))?'
                              r'(\.(?P<patch>\d+))?'
                              r'([.-]?(?P<label>\w+))?')

    def __init__(self,
                 major=None,
                 minor=None,
                 patch=None,
                 label=None,
                 text=None):
        self._major = major
        self._minor = minor
        self._patch = patch
        self._label = label
        if text:
            self._parse(text)

    def __str__(self):
        return self.full

    @property
    def full(self):
        result = io.StringIO()
        if self._major is not None and self._major > 0:
            result.write(str(self._major))
            if self._minor is not None and self._minor > 0:
                result.write("." + str(self._minor))
                if self._patch is not None and self._patch > 0:
                    result.write("." + str(self._patch))
                    if self._label:
                        result.write("." + str(self._label))
        return result.getvalue()

    @property
    def label(self):
        return self._label

    @property
    def major(self):
        return self._major

    @property
    def minor(self):
        return self._minor

    @property
    def patch(self):
        return self._patch

    def _parse(self, text: str):
        def get_int(data, default=0):
            return default if data is None else int(data)

        mo = type(self).__version_rx.search(text)
        if mo:
            groups = mo.groupdict()
            self._major = get_int(groups.get('major'))
            self._minor = get_int(groups.get('minor'))
            self._patch = get_int(groups.get('patch'))
            self._label = groups.get('label')
        else:
            raise VersionError("unrecognized version: '{}'".format(text))


class OsInfo:
    def __init__(self):
        # amd64, x86_64, etc
        self._arch = platform.machine().lower()
        self._bits = 64 if "64" in self._arch else 32

        # darwin, linux, windows
        self._type = platform.system().lower()

        # darwin, debian, redhat, windows
        self._family = self._get_family()

        # centos, darwin, debian, fedora, ubuntu, windows
        self._id = "unknown"

        # cygwin, msys2, wsl
        self._subsys = self._get_subsys()

        self._version = Version()

        if self._type == "windows":
            self._id = "windows"
            self._version = Version(text=platform.win32_ver()[1])
        elif self._type == "darwin":
            self._id = "darwin"
            self._version = Version(text=platform.mac_ver()[0])
        else:
            self._parse_os_release()

    def __str__(self):
        return ("OsType["
                "arch: {0.arch}"
                ", bits: {0.bits}"
                ", family: {0.family}"
                ", id: {0.id}"
                ", subsys: {0.subsys}"
                ", type: {0.type}"
                ", version: {0.version}"
                "]".format(self))

    @property
    def arch(self):
        return self._arch

    @property
    def bits(self):
        return self._bits

    @property
    def family(self):
        return self._family

    @property
    def id(self):
        return self._id

    @property
    def subsys(self):
        return self._subsys

    @property
    def type(self):
        return self._type

    @property
    def version(self):
        return self._version

    def refresh(self):
        self._parse_os_release()

    def _get_family(self):
        if self._type in ["windows", "darwin"]:
            family = self._type
        else:
            family = "redhat" if os.path.isfile("/etc/redhat-release") else "debian"
        return family

    def _get_subsys(self):
        subsys = "none"
        if self._type == "darwin":
            pass
        elif self._type == "linux":
            subsys = "wsl" if "WSLENV" in os.environ else "none"
        elif self._type == "windows" and "BASH_ENV" in os.environ:
            subsys = "msys2" if "MSYSTEM" in os.environ else "cygwin"
        return subsys

    def _parse_os_release(self):
        os_release_data = {}

        value_rx = re.compile(r"^\s*(?P<key>[A-Z0-9_]+)\s*=\s*(?P<value>.*)$")
        quote_rx = re.compile(r"^([\"'])(.*)\1$")
        try:
            with open("/etc/os-release", "r", encoding="utf-8", errors="ignore") as stream:
                for line in stream:
                    mo = value_rx.match(line)
                    if mo:
                        key = mo.group('key')
                        val = mo.group('value').strip()
                        mo2 = quote_rx.match(val)
                        if mo2:
                            val = mo2.group(2)
                        os_release_data[key] = val

            self._id = os_release_data.get("ID")
            if self._id is None or self._id == "generic":
                self._id = os_release_data.get("ID_LIKE")
            version = os_release_data.get("VERSION_ID")
            if version:
                self._version = Version(text=version)

        except OSError:
            pass


class PlatformSettingsEventListener(sublime_plugin.EventListener):
    os_info = OsInfo()

    def check_settings(self, view, first=False):
        s = view.settings()
        default_keys = [
            "user_${platform}",
            "${platform}",
            "${platform}_${hostname}",
            "${hostname}_${os_subsys}",
            "${hostname}",
        ]
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
            key = key.replace("${os_subsys}", type(self).os_info.subsys)
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
