# Third-party notices

DD2 Completionist Tracker is licensed under the GNU General Public License v3.0 (see `LICENSE`). It builds on the
work below. Data files marked "shipped" are included in the release ZIP (under `assets/`) and fetched by
`dd2.py fetch-assets` when running from source; their exact upstream commits are pinned in `assets.lock.json`.

The tool ships no files from Dragon's Dogma 2. Map images, item names and quest texts are read from the player's own
installation on their own PC. Dragon's Dogma is a trademark of Capcom; this project is not affiliated with Capcom.

| Project | Licence | What we use |
|---|---|---|
| [kvasszn/ree-save-editor](https://github.com/kvasszn/ree-save-editor) | GPL-3.0 | The save container, the Mandarin cipher and the record format (`tools/dd2_decrypt.py`, `tools/dd2_parse.py` are ports); shipped: `rszdd2.json`, `enumsdd2.json` |
| [seifhassine/REasy](https://github.com/seifhassine/REasy) | MIT | RSZ and scene reading (`tools/ree_rsz.py`), PAK reading (`tools/ree_pak.py`); shipped: `rszdd2_dlc.json`, `enumsdd2_dlc.json`, `lists/DD2_STM.list` |
| [kagenocookie/RE-Engine-Lib](https://github.com/kagenocookie/RE-Engine-Lib) | MIT | PAK reading (`tools/ree_pak.py`), texture reading (`tools/ree_tex.py`) |
| [dtlnor/REMSG_Converter](https://github.com/dtlnor/REMSG_Converter) | MIT | Game text (`.msg`) reading (`tools/ree_msg.py`) |
| [Leaflet](https://leafletjs.com/) 1.9.4 | BSD-2-Clause | The map view (`map/vendor/leaflet.js`, `leaflet.css`) |
| [kazuhikoarase/qrcode-generator](https://github.com/kazuhikoarase/qrcode-generator) 1.4.4 | MIT | The QR code for the phone address (`map/vendor/qrcode.min.js`) |

The GPL-3.0 text that covers ree-save-editor is the project's own `LICENSE`. The other licence texts follow.

## Bundled in the Windows program

The release ZIP also contains a Python runtime and the packages the tracker uses, put together by PyInstaller. Their
licence texts are in the `licenses` folder next to `DD2 Completionist Tracker.exe`:

| Component | Licence | File in `licenses` |
|---|---|---|
| Python 3.14 | Python Software Foundation License | `python-LICENSE.txt` |
| [cryptography](https://github.com/pyca/cryptography) (AES for the save cipher), statically linked with OpenSSL | Apache-2.0 or BSD-3-Clause; OpenSSL: Apache-2.0 | `cryptography-LICENSE*` |
| [Pillow](https://python-pillow.github.io/) (map images), with the image libraries it bundles | MIT-CMU and the bundled libraries' licences | `pillow-LICENSE.txt` |
| [PyInstaller](https://pyinstaller.org/) bootloader | GPL-2.0 with the bootloader exception | `pyinstaller-COPYING.txt` |

## REasy

```
MIT License

Copyright (c) 2025 Battlezone

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
```

## RE-Engine-Lib

```
MIT License

Copyright (c) 2025 shadowcookie

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
```

## REMSG_Converter

```
MIT License

Copyright (c) 2023 dtlnor

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
```

## Leaflet

```
BSD 2-Clause License

Copyright (c) 2010-2023, Volodymyr Agafonkin
Copyright (c) 2010-2011, CloudMade
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

## qrcode-generator

```
MIT License

Copyright (c) 2009 Kazuhiko Arase

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
```
