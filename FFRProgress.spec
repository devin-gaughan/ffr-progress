# PyInstaller spec: single-file windowed exe, with unused Tcl/Tk data stripped.
a = Analysis(['ffr_progress.py'], excludes=['unittest', 'pydoc', 'doctest', 'email', 'http', 'xml', 'multiprocessing', 'asyncio', 'ssl', 'socket', 'select', 'decimal', 'lzma', 'bz2'])
a.datas = [d for d in a.datas if not any(s in d[0].replace('\\', '/') for s in ('/tzdata/', '/msgs/', '/demos/', '/images/', '/encoding/', '/opt0.4/', '/http1.0/'))]
a.binaries = [b for b in a.binaries if not b[0].lower().startswith(('libssl', 'libcrypto', '_ssl', '_hashlib', '_lzma', '_bz2', '_decimal', '_socket', 'select', '_multiprocessing', '_asyncio', '_overlapped', '_queue', 'libffi', '_ctypes'))]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], name='FFRProgress', console=False, upx=True, strip=False)
