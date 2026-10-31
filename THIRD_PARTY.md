# Third-party notices

## ffr-save-tracker (zabo-dev) — MIT

The save-container handling and the GVAS (Unreal Engine save game) property parser in
`ffr_progress.py` are adapted from `tools/ffrs_save.py` in
https://github.com/zabo-dev/ffr-save-tracker, which also documents the save format and
the AES key used by Final Fantasy Resonance. The code was rewritten and trimmed for this
tool, but it follows the structure of that script. The original notice is reproduced below.

    MIT License

    Copyright (c) 2026 zabo-dev

    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.

## ffr-save-editor (jesus-seijas-sp)

https://github.com/jesus-seijas-sp/ffr-save-editor independently documents the same save
format. No code from it is used here.

Everything else in this repository (the pure-Python AES-256 implementation, the Tkinter
interface, save discovery, live refresh and the command-line mode) was written for FFR
Progress.
