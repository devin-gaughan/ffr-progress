#!/usr/bin/env python3
"""FFR Progress - read-only achievement counter viewer for Final Fantasy Resonance (Steam).

Shows the hidden lifetime counters stored in your save (Resonances used, staggers,
wins, etc.) so you can see how close you are to "Resonance Rapid Fire" (400) and
"Keep Them on Their Toes" (1000). It never writes to your save files.

Save format: 32-byte "SVHD" header (SHA-1 of body at bytes 8..28), body is
AES-256-ECB, plaintext is an Unreal Engine 5 GVAS save game.
Format and key documented by the open-source ffr-save-tracker / ffr-save-editor projects.

Pure standard library (tkinter only), so it runs from source on Windows, Linux and
Steam Deck, and packs into a single .exe with PyInstaller.
"""
import glob
import hashlib
import os
import struct
import sys
import time

APP_NAME = "FFR Progress"
APP_VERSION = "1.0.0"
KEY = b"wwrqPkdwzPvgfchQ8kTYHVbn4umTf3d7"
SAVE_CLASS = "/Script/mucha.CPP_MuchaGameSaveData"

# ---------------------------------------------------------------------------
# AES-256 ECB decryption, pure Python (no dependencies). Slow-ish but a 600 KB
# save decrypts in about a second, and it only runs when the file changes.
# ---------------------------------------------------------------------------

def _build_tables():
    sbox = [0] * 256
    p = q = 1
    while True:
        # multiply p by 3
        p = p ^ ((p << 1) & 0xFF) ^ (0x1B if p & 0x80 else 0)
        # divide q by 3
        q ^= q << 1
        q ^= q << 2
        q ^= q << 4
        q &= 0xFF
        if q & 0x80:
            q ^= 0x09
        x = q ^ (q << 1) ^ (q << 2) ^ (q << 3) ^ (q << 4)
        x = (x ^ (x >> 8) ^ 0x63) & 0xFF
        sbox[p] = x
        if p == 1:
            break
    sbox[0] = 0x63
    inv = [0] * 256
    for i, v in enumerate(sbox):
        inv[v] = i
    return sbox, inv


SBOX, INV_SBOX = _build_tables()


def _xtime(a):
    a <<= 1
    return (a ^ 0x1B) & 0xFF if a & 0x100 else a


def _mul(a, b):
    r = 0
    while b:
        if b & 1:
            r ^= a
        a = _xtime(a)
        b >>= 1
    return r


_MUL9 = [_mul(i, 9) for i in range(256)]
_MUL11 = [_mul(i, 11) for i in range(256)]
_MUL13 = [_mul(i, 13) for i in range(256)]
_MUL14 = [_mul(i, 14) for i in range(256)]


def _expand_key(key):
    nk = len(key) // 4          # 8 words for AES-256
    rounds = nk + 6             # 14
    w = [list(key[4 * i:4 * i + 4]) for i in range(nk)]
    rcon = 1
    for i in range(nk, 4 * (rounds + 1)):
        t = list(w[i - 1])
        if i % nk == 0:
            t = t[1:] + t[:1]
            t = [SBOX[b] for b in t]
            t[0] ^= rcon
            rcon = _xtime(rcon)
        elif nk > 6 and i % nk == 4:
            t = [SBOX[b] for b in t]
        w.append([w[i - nk][j] ^ t[j] for j in range(4)])
    # round keys as flat 16-byte lists
    return [sum(w[4 * r:4 * r + 4], []) for r in range(rounds + 1)], rounds


def _decrypt_block(block, round_keys, rounds):
    s = [block[i] ^ round_keys[rounds][i] for i in range(16)]
    for rnd in range(rounds - 1, -1, -1):
        # inverse shift rows
        s = [s[(i - 4 * (i % 4)) % 16] for i in range(16)]
        # inverse sub bytes
        s = [INV_SBOX[b] for b in s]
        # add round key
        rk = round_keys[rnd]
        s = [s[i] ^ rk[i] for i in range(16)]
        # inverse mix columns (skipped on the final round)
        if rnd > 0:
            out = []
            for c in range(4):
                a0, a1, a2, a3 = s[4 * c:4 * c + 4]
                out += [
                    _MUL14[a0] ^ _MUL11[a1] ^ _MUL13[a2] ^ _MUL9[a3],
                    _MUL9[a0] ^ _MUL14[a1] ^ _MUL11[a2] ^ _MUL13[a3],
                    _MUL13[a0] ^ _MUL9[a1] ^ _MUL14[a2] ^ _MUL11[a3],
                    _MUL11[a0] ^ _MUL13[a1] ^ _MUL9[a2] ^ _MUL14[a3],
                ]
            s = out
    return bytes(s)


def aes_ecb_decrypt(key, data):
    round_keys, rounds = _expand_key(key)
    out = bytearray()
    for i in range(0, len(data) - len(data) % 16, 16):
        out += _decrypt_block(data[i:i + 16], round_keys, rounds)
    return bytes(out)


# ---------------------------------------------------------------------------
# Save container + GVAS property reader (only what we need: the Player block)
# ---------------------------------------------------------------------------

class SaveError(Exception):
    pass


def decrypt_save(raw, limit=None):
    """Decrypt the save body. With `limit`, only the first `limit` bytes are decrypted
    (ECB mode makes that valid), which is all we need for the Player block."""
    if raw[:4] != b"SVHD":
        raise SaveError("Not a Final Fantasy Resonance save (missing SVHD header)")
    body = raw[32:]
    if hashlib.sha1(body).digest() != raw[8:28]:
        raise SaveError("Checksum mismatch (file may be mid-write, try again)")
    if limit:
        body = body[:limit - limit % 16]
    plain = aes_ecb_decrypt(KEY, body)
    if plain[:4] != b"GVAS":
        raise SaveError("Decryption failed (unexpected save version?)")
    return plain


class Reader:
    def __init__(self, buf):
        self.b, self.o = buf, 0

    def read(self, n):
        v = self.b[self.o:self.o + n]
        self.o += n
        return v

    def i32(self):
        return struct.unpack("<i", self.read(4))[0]

    def u8(self):
        return self.read(1)[0]

    def string(self):
        n = self.i32()
        if n == 0:
            return ""
        if n < 0:
            return self.read(-n * 2)[:-2].decode("utf-16le")
        return self.read(n)[:-1].decode("utf-8", "replace")

    def ptype(self):
        name = self.string()
        return name, [self.ptype() for _ in range(self.i32())]


def _read_props_flat(r):
    """Read one property list; only scalar values are decoded, everything else skipped."""
    out = {}
    while True:
        name = r.string()
        if name == "None":
            return out
        (kind, _sub) = r.ptype()
        size = r.i32()
        flags = r.u8()
        if flags & 1:
            r.i32()
        if flags & 2:
            r.read(16)
        end = r.o + size
        if kind == "IntProperty":
            out[name] = r.i32()
        elif kind == "Int64Property":
            out[name] = struct.unpack("<q", r.read(8))[0]
        elif kind == "FloatProperty":
            out[name] = struct.unpack("<f", r.read(4))[0]
        elif kind == "DoubleProperty":
            out[name] = struct.unpack("<d", r.read(8))[0]
        elif kind == "BoolProperty":
            out[name] = bool(flags & 16) if size == 0 else bool(r.u8())
        elif kind in ("StrProperty", "NameProperty", "EnumProperty"):
            out[name] = r.string()
        elif kind == "StructProperty" and _sub and _sub[0][0] == "DateTime":
            out[name] = struct.unpack("<q", r.read(8))[0]
        r.o = end


def read_player_block(plain):
    r = Reader(plain)
    assert r.read(4) == b"GVAS"
    r.i32(); r.i32(); r.i32(); r.read(10); r.string(); r.i32()
    n = r.i32()
    r.read(n * 20)
    cls = r.string()
    r.u8()
    if cls != SAVE_CLASS:
        raise SaveError("Unexpected save class: " + cls)
    # top level: walk until we hit "Player", read it as a struct
    while True:
        name = r.string()
        if name == "None":
            raise SaveError("No Player block in save")
        (kind, sub) = r.ptype()
        size = r.i32()
        flags = r.u8()
        if flags & 1:
            r.i32()
        if flags & 2:
            r.read(16)
        end = r.o + size
        if name == "Player" and kind == "StructProperty":
            return _read_props_flat(r)
        r.o = end


def load_counters(path):
    with open(path, "rb") as f:
        raw = f.read()
    # The Player block sits in the first few KB; decrypt progressively larger
    # prefixes so a normal save is read in milliseconds.
    for limit in (16 * 1024, 128 * 1024, None):
        try:
            return read_player_block(decrypt_save(raw, limit))
        except (struct.error, IndexError, AssertionError):
            if limit is None:
                raise SaveError("Could not parse save (unexpected layout)")


# ---------------------------------------------------------------------------
# Locating saves
# ---------------------------------------------------------------------------

def default_save_dirs():
    dirs = []
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA", "")
        if base:
            dirs += glob.glob(os.path.join(base, "FFRS", "Steam", "*"))
    else:
        home = os.path.expanduser("~")
        for lib in (os.path.join(home, ".steam", "steam"),
                    os.path.join(home, ".local", "share", "Steam"),
                    os.path.join(home, ".var", "app", "com.valvesoftware.Steam", ".local", "share", "Steam")):
            dirs += glob.glob(os.path.join(lib, "steamapps", "compatdata", "3259780", "pfx",
                                           "drive_c", "users", "steamuser", "AppData", "Local",
                                           "FFRS", "Steam", "*"))
    return [d for d in dirs if os.path.isdir(d)]


def find_saves():
    saves = []
    for d in default_save_dirs():
        saves += sorted(glob.glob(os.path.join(d, "GameSaveData*.sav")))
    return saves


def slot_label(path):
    """Label by file name; the game's own slot numbering may be offset by one."""
    name = os.path.basename(path)
    try:
        n = int(name[len("GameSaveData"):-4])
    except ValueError:
        return name
    return "Save file %d" % n


def saved_time_text(path):
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(os.path.getmtime(path)))
    except OSError:
        return "?"


def fmt_playtime(seconds):
    s = int(seconds)
    return "%dh %02dm" % (s // 3600, (s % 3600) // 60)


# ---------------------------------------------------------------------------
# Command-line mode (no GUI): python ffr_progress.py --cli [save.sav]
# ---------------------------------------------------------------------------

def cli(args):
    paths = args or find_saves()
    if not paths:
        print("No saves found. Pass a GameSaveDataN.sav path.")
        return 1
    for p in paths:
        try:
            c = load_counters(p)
        except Exception as e:
            print("%s: %s" % (p, e))
            continue
        print("== %s (%s)" % (slot_label(p), p))
        print("  Resonances used : %5d / 400   (Resonance Rapid Fire)" % c.get("finishblowCount", -1))
        print("  Staggers        : %5d / 1000  (Keep Them on Their Toes)" % c.get("breakCount", -1))
        print("  Gil earned      : %10d / 1000000 (Making Lid Proud)" % c.get("earnedMoney", -1))
        print("  Gil spent       : %10d / 100000  (Gil Comes and Goes)" % c.get("spentMoney", -1))
        print("  Battles won %d, escapes %d, steals %d, play time %s, saved %s" % (
            c.get("WinNum", 0), c.get("EscapeNum", 0), c.get("StealSuccessNum", 0),
            fmt_playtime(c.get("PlayTime", 0)), saved_time_text(p)))
    return 0


# ---------------------------------------------------------------------------
# GUI
# ---------------------------------------------------------------------------

GOALS = [
    # key, label, target, achievement
    ("finishblowCount", "Resonances used", 400, "Resonance Rapid Fire"),
    ("breakCount", "Enemies staggered", 1000, "Keep Them on Their Toes"),
    ("earnedMoney", "Gil earned (total)", 1_000_000, "Making Lid Proud"),
    ("spentMoney", "Gil spent (total)", 100_000, "Gil Comes and Goes"),
]

EXTRA = [
    ("WinNum", "Battles won"),
    ("EscapeNum", "Escapes"),
    ("StealSuccessNum", "Successful steals"),
    ("currentMoney", "Gil on hand"),
]


def gui():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    root = tk.Tk()
    root.title("%s %s" % (APP_NAME, APP_VERSION))
    root.resizable(False, False)
    try:
        root.tk.call("tk", "scaling", 1.25)
    except tk.TclError:
        pass

    state = {"path": None, "mtime": None, "poll": True}

    outer = ttk.Frame(root, padding=14)
    outer.grid(sticky="nsew")

    # --- slot picker -------------------------------------------------------
    top = ttk.Frame(outer)
    top.grid(row=0, column=0, sticky="ew", pady=(0, 10))
    ttk.Label(top, text="Save slot:").grid(row=0, column=0, padx=(0, 6))
    slot_var = tk.StringVar()
    slot_box = ttk.Combobox(top, textvariable=slot_var, state="readonly", width=48)
    slot_box.grid(row=0, column=1, padx=(0, 6))
    saves = find_saves()

    def refresh_slot_list():
        nonlocal saves
        saves = find_saves()
        labels = ["%s  -  %s" % (slot_label(p), os.path.basename(p)) for p in saves]
        slot_box["values"] = labels
        return labels

    labels = refresh_slot_list()

    def choose_other():
        p = filedialog.askopenfilename(title="Pick a GameSaveDataN.sav",
                                       filetypes=[("FFR save", "GameSaveData*.sav"), ("All", "*")])
        if p:
            if p not in saves:
                saves.append(p)
                slot_box["values"] = list(slot_box["values"]) + [
                    "%s  -  %s" % (slot_label(p), os.path.basename(p))]
            slot_box.current(saves.index(p))
            on_slot_change()

    ttk.Button(top, text="Browse...", command=choose_other).grid(row=0, column=2)

    # --- progress rows -----------------------------------------------------
    rows = ttk.Frame(outer)
    rows.grid(row=1, column=0, sticky="ew")
    bars = {}
    for i, (key, label, target, ach) in enumerate(GOALS):
        ttk.Label(rows, text=label, font=("", 10, "bold")).grid(row=2 * i, column=0, sticky="w")
        val = ttk.Label(rows, text="-", anchor="e", width=24)
        val.grid(row=2 * i, column=1, sticky="e")
        bar = ttk.Progressbar(rows, length=420, maximum=target, mode="determinate")
        bar.grid(row=2 * i + 1, column=0, columnspan=2, sticky="ew", pady=(2, 8))
        ttk.Label(rows, text=ach, foreground="#777").grid(row=2 * i + 1, column=2, padx=(10, 0), sticky="w")
        bars[key] = (bar, val, target)

    # --- extra stats -------------------------------------------------------
    extra = ttk.LabelFrame(outer, text="Other lifetime stats", padding=8)
    extra.grid(row=2, column=0, sticky="ew", pady=(6, 6))
    extra_vals = {}
    for i, (key, label) in enumerate(EXTRA):
        ttk.Label(extra, text=label + ":").grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=(0, 6))
        v = ttk.Label(extra, text="-", width=14, anchor="w")
        v.grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w", padx=(0, 18))
        extra_vals[key] = v
    ttk.Label(extra, text="Play time:").grid(row=2, column=0, sticky="w", padx=(0, 6))
    play_val = ttk.Label(extra, text="-", width=14, anchor="w")
    play_val.grid(row=2, column=1, sticky="w")
    ttk.Label(extra, text="Saved:").grid(row=2, column=2, sticky="w", padx=(0, 6))
    saved_val = ttk.Label(extra, text="-", anchor="w")
    saved_val.grid(row=2, column=3, sticky="w")

    # --- status ------------------------------------------------------------
    status = ttk.Label(outer, text="", foreground="#555")
    status.grid(row=3, column=0, sticky="w", pady=(4, 0))
    ttk.Label(outer, text="Read-only: this tool never modifies your saves. "
                          "Save in-game and the numbers update automatically.",
              foreground="#777", font=("", 8)).grid(row=4, column=0, sticky="w", pady=(6, 0))

    def show(c, path):
        for key, (bar, val, target) in bars.items():
            n = c.get(key, 0)
            bar["value"] = min(n, target)
            done = "  done" if n >= target else "  (%d to go)" % (target - n)
            val["text"] = "{:,} / {:,}{}".format(n, target, done)
        for key, v in extra_vals.items():
            v["text"] = "{:,}".format(c.get(key, 0))
        play_val["text"] = fmt_playtime(c.get("PlayTime", 0))
        saved_val["text"] = saved_time_text(path)

    def load(path, announce=True):
        try:
            c = load_counters(path)
        except Exception as e:
            status["text"] = "Could not read save: %s" % e
            return
        show(c, path)
        state["mtime"] = os.path.getmtime(path)
        if announce:
            status["text"] = "Loaded %s at %s" % (slot_label(path), time.strftime("%H:%M:%S"))

    def on_slot_change(*_):
        idx = slot_box.current()
        if idx < 0:
            return
        state["path"] = saves[idx]
        load(state["path"])

    slot_box.bind("<<ComboboxSelected>>", on_slot_change)

    def poll():
        p = state["path"]
        if p and os.path.exists(p):
            try:
                m = os.path.getmtime(p)
            except OSError:
                m = None
            if m and m != state["mtime"]:
                # file just changed; give the game a moment to finish writing
                root.after(600, lambda: load(p))
                state["mtime"] = m
        root.after(1500, poll)

    if saves:
        # default to the most recently written slot
        newest = max(range(len(saves)), key=lambda i: os.path.getmtime(saves[i]))
        slot_box.current(newest)
        on_slot_change()
    else:
        status["text"] = "No saves found automatically. Use Browse... to pick GameSaveDataN.sav"
    poll()
    root.mainloop()


if __name__ == "__main__":
    if "--cli" in sys.argv:
        sys.exit(cli([a for a in sys.argv[1:] if a != "--cli"]))
    gui()
