"""Cell-level parsers + per-entity cross-field rules. Har parser ValueError(msg) uthata hai (msg user ko dikhta hai)."""
import re
from datetime import time

TRUE = {"1", "true", "yes", "y", "t", "haan"}
FALSE = {"0", "false", "no", "n", "f", "nahi"}
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def s(maxlen=None):
    def parse(v, ctx):
        if maxlen and len(v) > maxlen:
            raise ValueError(f"max {maxlen} characters allowed (got {len(v)})")
        return v
    return parse


def email():
    def parse(v, ctx):
        if not EMAIL_RE.match(v):
            raise ValueError(f"'{v}' valid email nahi hai")
        return v
    return parse


def i(min=None, max=None):
    def parse(v, ctx):
        try:
            n = int(float(v)) if re.fullmatch(r"-?\d+(\.0+)?", v) else int(v)
        except ValueError:
            raise ValueError(f"'{v}' whole number hona chahiye")
        if min is not None and n < min:
            raise ValueError(f"{n} < minimum {min}")
        if max is not None and n > max:
            raise ValueError(f"{n} > maximum {max}")
        return n
    return parse


def b():
    def parse(v, ctx):
        x = v.strip().lower()
        if x in TRUE:
            return True
        if x in FALSE:
            return False
        raise ValueError(f"'{v}' yes/no (ya true/false) hona chahiye")
    return parse


def choice(mapping):
    """mapping: {lowercase alias: stored value}. Allowed values error me dikhte hain."""
    allowed = sorted(set(mapping.values()))

    def parse(v, ctx):
        key = re.sub(r"[\s_-]+", " ", v.strip().lower())
        if key in mapping:
            return mapping[key]
        raise ValueError(f"'{v}' allowed nahi. Allowed: {', '.join(allowed)}")
    return parse


def t():
    def parse(v, ctx):
        m = re.fullmatch(r"(\d{1,2}):(\d{2})(:\d{2})?", v.strip())
        if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            raise ValueError(f"'{v}' time HH:MM format me hona chahiye (e.g. 09:00)")
        return time(int(m.group(1)), int(m.group(2)))
    return parse


def fk(model, field, label=None):
    """Value DB me us model ke `field` se match hona chahiye (REQ-1.2: invalid reference)."""
    def parse(v, ctx):
        obj = ctx.lookup(model, field).get(v)
        if obj is None:
            raise ValueError(f"{label or model.__name__} '{v}' database me nahi mila (pehle usko import karo)")
        return obj
    return parse


DAYS = {k: v for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat")
        for k, v in ((d.lower(), d),)}
DAYS.update({"monday": "Mon", "tuesday": "Tue", "wednesday": "Wed", "thursday": "Thu", "friday": "Fri", "saturday": "Sat"})
COURSE_TYPES = {"major": "MAJOR", "minor": "MINOR", "skill": "SKILL", "skill based": "SKILL", "skillbased": "SKILL",
                "value": "VALUE", "value added": "VALUE", "valueadded": "VALUE"}
ROOM_TYPES = {"classroom": "CLASSROOM", "class": "CLASSROOM", "lab": "LAB", "laboratory": "LAB",
              "seminar": "SEMINAR", "seminar hall": "SEMINAR"}
LEVELS = {"no": "NO", "unavailable": "NO", "avoid": "AVOID", "prefer not": "AVOID", "prefer": "PREFER", "preferred": "PREFER"}


# ---------- cross-field rules (return list of (column, message)) ----------
def check_course(c):
    errs = []
    size, lab, hours = c.get("lab_block_size", 1), c.get("requires_lab", False), c.get("hours_per_week", 3)
    if size > 1 and not lab:
        errs.append(("lab_block_size", "lab_block_size > 1 ke liye requires_lab = yes hona chahiye"))
    if hours % size:
        errs.append(("lab_block_size", f"hours_per_week ({hours}) lab_block_size ({size}) se divisible nahi"))
    return errs


def check_timeslot(c):
    return [("end_time", "end_time, start_time ke baad hona chahiye")] if c["end_time"] <= c["start_time"] else []