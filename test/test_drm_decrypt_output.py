import shutil
import struct
import subprocess

import pytest

from ofscraper.commands.scraper.actions.download.utils.keyhelpers import strip_pssh


def _box(typ, payload=b""):
    return struct.pack(">I4s", 8 + len(payload), typ) + payload


def _types(data, start=0, end=None):
    end = len(data) if end is None else end
    out, pos = [], start
    while pos + 8 <= end:
        size, typ = struct.unpack(">I4s", data[pos : pos + 8])
        out.append(typ)
        if typ in (b"moov", b"moof"):
            out += [b"  " + t for t in _types(data, pos + 8, pos + size)]
        pos += size
    return out


def test_strip_pssh_renames_in_place(tmp_path):
    pssh = _box(b"pssh", b"\x00" * 40)
    moov = _box(b"moov", _box(b"mvhd", b"\x00" * 100) + pssh + _box(b"trak", b"\x00" * 20))
    # "pssh" inside mdat is media data, not a box, and must not change
    mdat = _box(b"mdat", b"xxxxpsshyyyy")
    data = _box(b"ftyp", b"isom\x00\x00\x02\x00") + pssh + moov + mdat
    f = tmp_path / "a.mp4"
    f.write_bytes(data)

    assert strip_pssh(f) == 2
    out = f.read_bytes()
    assert len(out) == len(data)
    assert b"pssh" not in b"".join(_types(out))
    assert _types(out) == [t.replace(b"pssh", b"free") for t in _types(data)]
    assert out.endswith(mdat)


def test_strip_pssh_leaves_clean_file_alone(tmp_path):
    data = _box(b"ftyp", b"isom") + _box(b"moov", _box(b"mvhd", b"\x00" * 100))
    f = tmp_path / "a.mp4"
    f.write_bytes(data)
    assert strip_pssh(f) == 0
    assert f.read_bytes() == data


FFMPEG = shutil.which("ffmpeg")
KEY = "00112233445566778899aabbccddeeff"


def _ffmpeg(*args):
    subprocess.run([FFMPEG, "-v", "error", "-y", *args], check=True)


def _framemd5(path):
    r = subprocess.run(
        [FFMPEG, "-v", "error", "-i", str(path), "-map", "0:v", "-f", "framemd5", "-"],
        capture_output=True, text=True,
    )
    # decoding still-encrypted data fails outright on ffmpeg 8+
    return r.stdout if r.returncode == 0 else f"decode failed ({r.returncode})"


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg not installed")
def test_installed_ffmpeg_decrypts_cenc_like_un_encrypt(tmp_path):
    # end to end with whatever ffmpeg is installed: encrypt a clip with CENC,
    # decrypt it with the same arguments as un_encrypt, and compare frames
    plain, enc, dec = tmp_path / "plain.mp4", tmp_path / "enc.mp4", tmp_path / "dec.mp4"
    _ffmpeg("-f", "lavfi", "-i", "testsrc=duration=2:size=320x240:rate=25",
            "-c:v", "libx264", "-pix_fmt", "yuv420p", str(plain))
    _ffmpeg("-i", str(plain), "-c", "copy", "-encryption_scheme", "cenc-aes-ctr",
            "-encryption_key", KEY, "-encryption_kid", "a7e61c373e219033c21091fa607bf3b8", str(enc))
    assert _framemd5(enc) != _framemd5(plain)  # really encrypted
    _ffmpeg("-decryption_key", KEY, "-i", str(enc), "-codec", "copy", str(dec))
    strip_pssh(dec)
    assert _framemd5(dec) == _framemd5(plain)
