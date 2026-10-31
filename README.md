# FFR Progress

Read-only viewer for the hidden lifetime counters in a **Final Fantasy Resonance** (Steam) save,
so you can see how close you are to the grind achievements the game gives you no counter for:

- **Resonance Rapid Fire** — use Resonances 400 times (`finishblowCount` in the save)
- **Keep Them on Their Toes** — stagger enemies 1000 times (`breakCount`)
- **Making Lid Proud** — earn 1,000,000 gil total
- **Gil Comes and Goes** — spend 100,000 gil total

plus battles won, escapes, successful steals, gil on hand and play time.

It never writes to your save files. It decrypts a copy in memory, verifies the checksum and reads
the `Player` block. Save in-game and the numbers refresh on their own.

## Download version (Windows)

Grab `FFRProgress.exe` from the [latest release](https://github.com/devin-gaughan/ffr-progress/releases/latest) and run it. It finds your saves in `%LOCALAPPDATA%\FFRS\Steam\<SteamID>\` automatically
and opens the most recently written one; pick another file from the drop-down, or **Browse...**
for a save somewhere else. If Windows SmartScreen complains, that's only because the file is unsigned.

## From source (Windows, Linux, Steam Deck)

Needs Python 3.8+ with tkinter; no other dependencies.

    python ffr_progress.py            # GUI
    python ffr_progress.py --cli      # print all found saves to the terminal
    python ffr_progress.py --cli path/to/GameSaveData1.sav

On Linux / Steam Deck it looks inside the Proton prefix
(`steamapps/compatdata/3259780/pfx/drive_c/users/steamuser/AppData/Local/FFRS/Steam/<SteamID>/`).

## Build the .exe yourself

    pip install pyinstaller
    pyinstaller --onefile --windowed --name FFRProgress ffr_progress.py

## Save format

`GameSaveDataN.sav` = 32-byte `SVHD` header (SHA-1 of the body at bytes 8–28) + AES-256-ECB body,
which decrypts to an Unreal Engine 5 GVAS save (`/Script/mucha.CPP_MuchaGameSaveData`).
Format and key as documented by the open-source
[ffr-save-tracker](https://github.com/zabo-dev/ffr-save-tracker) and
[ffr-save-editor](https://github.com/jesus-seijas-sp/ffr-save-editor) projects.

A note on the files: `GameSaveData0.sav`, `GameSaveData1.sav`, … map to the in-game slots, but
sources disagree on whether file 0 is the autosave or slot 1, so the app labels them by file number
and shows each file's last-saved time.

## License

MIT
