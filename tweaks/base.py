"""Base tweak classes."""
import re

from core import shell, backup

BACKUP_DIR = backup.BACKUP_DIR


def _reg_set(key: str, name: str, type_: str, value) -> bool:
    r = shell.reg("add", key, "/v", name, "/t", type_, "/d", str(value), "/f")
    return r.returncode == 0


def _reg_del(key: str, name: str) -> bool:
    shell.reg("delete", key, "/v", name, "/f")
    return True


def _reg_query(key: str, name: str):
    r = shell.reg("query", key, "/v", name)
    if r.returncode != 0:
        return None, None
    for line in r.stdout.splitlines():
        if not line.strip() or not line.startswith("    "):
            continue
        # reg.exe pads columns with runs of 4+ spaces, so splitting on that
        # (instead of any whitespace) preserves single spaces inside the value.
        cols = [c for c in re.split(r" {4,}", line.strip()) if c != ""]
        if len(cols) < 3 or cols[0] != name or not cols[1].startswith("REG_"):
            continue
        return cols[1], " ".join(cols[2:])
    return None, None


def _reg_verify(key: str, name: str, expected_type: str, expected_value) -> bool:
    type_, value = _reg_query(key, name)
    if type_ is None:
        return False
    if expected_type == "REG_DWORD":
        try:
            return int(value, 0) == int(expected_value)
        except (ValueError, TypeError):
            return False
    return str(value).strip() == str(expected_value).strip()


def _reg_backup(key: str, fname: str) -> None:
    out = BACKUP_DIR / f"{fname}.reg"
    if not out.exists():
        shell.reg("export", key, str(out), "/y")


class TweakContext:
    def __init__(self, adapter=None):
        self.adapter = adapter


class Tweak:
    def __init__(
        self,
        id: int,
        name: str,
        description: str,
        category: str = "stack",
        requires_adapter: bool = False,
    ):
        self.id = id
        self.name = name
        self.description = description
        self.category = category
        self.requires_adapter = requires_adapter

    def apply(self, ctx: TweakContext) -> bool:
        raise NotImplementedError

    def revert(self, ctx: TweakContext) -> bool:
        raise NotImplementedError

    def snapshot(self, ctx: TweakContext) -> dict:
        """Return JSON-serializable current state. Empty dict = nothing to save."""
        return {}

    def restore(self, ctx: TweakContext, snap: dict) -> bool:
        """Apply a snapshot. Return True if anything was restored."""
        return False


class RegTweak(Tweak):
    def __init__(self, id, name, description, key, value_name, value_type, apply_value,
                 category="registry"):
        super().__init__(id, name, description, category=category)
        self.key = key
        self.value_name = value_name
        self.value_type = value_type
        self.apply_value = apply_value
        self._pre_apply_snap = None

    def apply(self, ctx):
        self._pre_apply_snap = self.snapshot(ctx)
        _reg_backup(self.key, self.value_name)
        if not _reg_set(self.key, self.value_name, self.value_type, self.apply_value):
            return False
        return _reg_verify(self.key, self.value_name,
                           self.value_type, self.apply_value)

    def revert(self, ctx):
        """Restore whatever this run's apply() saw before it wrote a value.
        If apply() was never called this session, fall back to deleting the
        value (Windows' own default for most of these keys is "absent")."""
        if self._pre_apply_snap is not None:
            return self.restore(ctx, self._pre_apply_snap)
        return _reg_del(self.key, self.value_name)

    def snapshot(self, ctx):
        type_, value = _reg_query(self.key, self.value_name)
        if type_ is None:
            return {"existed": False}
        return {"existed": True, "type": type_, "value": value}

    def restore(self, ctx, snap):
        if snap.get("existed"):
            return _reg_set(self.key, self.value_name,
                            snap.get("type", "REG_DWORD"),
                            snap.get("value", 0))
        _reg_del(self.key, self.value_name)
        return True


class PowerCfgValueTweak(Tweak):
    """Sets an AC+DC value index for a powercfg subgroup/setting on the
    active power scheme. Same generic apply/revert/snapshot/restore shape
    as RegTweak, but for settings that live in the power-plan store rather
    than a plain registry value.
    """

    def __init__(self, id, name, description, subgroup, setting,
                 apply_value, revert_value, category="power"):
        super().__init__(id, name, description, category=category)
        self.subgroup = subgroup
        self.setting = setting
        self.apply_value = apply_value
        self.revert_value = revert_value

    def _current_ac(self):
        r = shell.run(["powercfg", "/query", "SCHEME_CURRENT", self.subgroup, self.setting])
        if r.returncode != 0:
            return None
        for line in r.stdout.splitlines():
            line = line.strip()
            if line.startswith("Current AC Power Setting Index:"):
                return line.split(":", 1)[1].strip()
        return None

    def _set(self, value) -> bool:
        r1 = shell.run(["powercfg", "/setacvalueindex", "SCHEME_CURRENT",
                        self.subgroup, self.setting, str(value)])
        r2 = shell.run(["powercfg", "/setdcvalueindex", "SCHEME_CURRENT",
                        self.subgroup, self.setting, str(value)])
        shell.run(["powercfg", "/setactive", "SCHEME_CURRENT"])
        return r1.returncode == 0 and r2.returncode == 0

    def apply(self, ctx):
        if self._current_ac() is None:
            return None
        if not self._set(self.apply_value):
            return False
        cur = self._current_ac()
        try:
            return int(cur, 0) == int(self.apply_value)
        except (TypeError, ValueError):
            return False

    def revert(self, ctx):
        return self._set(self.revert_value)

    def snapshot(self, ctx):
        cur = self._current_ac()
        return {"value": cur if cur is not None else self.revert_value}

    def restore(self, ctx, snap):
        v = snap.get("value")
        if v is None:
            return False
        try:
            v = int(v, 0)
        except (TypeError, ValueError):
            pass
        return self._set(v)