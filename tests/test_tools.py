"""Tests for the host tools in tools/ (loaded by path; tools/ is not a package)."""
import importlib.util
import pathlib
import random


ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# The reply captured from a stock FM-1_015 unit on 2026-09-06 (notes/2026-09-06-bench.md).
IDENTITY_REPLY = bytes.fromhex(
    "F0 00 32 45 58 01 00 00 23 4D 5A 44 79 05 26 4C 1A"
    "00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 20 06 F7")


def pack7(data):
    out, acc, nbits = bytearray(), 0, 0
    for b in data:
        acc |= b << nbits
        nbits += 8
        while nbits >= 7:
            out.append(acc & 0x7F)
            acc >>= 7
            nbits -= 7
    if nbits:
        out.append(acc & 0x7F)
    return bytes(out)


class TestIdentify:
    mod = load("fm1_identify")

    def test_unpack7_round_trip(self):
        for size in range(0, 40):
            data = bytes(random.Random(size).randrange(256) for _ in range(size))
            assert self.mod.unpack7(pack7(data))[:size] == data

    def test_header_is_the_packed_id_block(self):
        assert self.mod.unpack7(bytes([0x00, 0x32, 0x45, 0x58]))[:3] == bytes([0x00, 0x59, 0x11])

    def test_decodes_real_v15_reply(self):
        info = self.mod.decode(IDENTITY_REPLY)
        assert info["model"] == "FM-1" and info["version"] == 15
        assert info["identity"] == "FM-1_015" and info["checksum_ok"] is True
        assert "error" not in info

    def test_rejects_garbage(self):
        assert "error" in self.mod.decode(b"\xF0\x7E\x7F\x06\x02\xF7")
        assert "error" in self.mod.decode(IDENTITY_REPLY[:-1])

    def test_query_is_exactly_the_updater_identity_request(self):
        assert self.mod.QUERY == [0x00, 0x32, 0x45, 0x00, 0x00, 0x00, 0x40, 0x7F]


class TestExtractFwsc:
    mod = load("extract_fwsc_from_updater")

    @staticmethod
    def package(seed, size=260 * 1024):
        rnd = random.Random(seed)
        pkg = bytearray(rnd.randrange(256) for _ in range(size))
        pkg[0x424:0x42A] = b"AC791N"
        pkg[-16:-11] = b"JLUFW"
        return bytes(pkg)

    def test_finds_package_behind_qt_length_prefix(self):
        pkg = self.package(1)
        blob = b"\x00" * 5000 + len(pkg).to_bytes(4, "big") + pkg + b"\xFF" * 3000
        found = self.mod.find_packages(blob)
        assert len(found) == 1
        (start, data), = found.values()
        assert data == pkg and start == 5004

    def test_dedupes_fat_binary_copies_and_ignores_decoys(self):
        pkg = self.package(2)
        decoy = b"junk" * 100 + b"JLUFW" + b"\x00" * 11       # trailer without a length word
        blob = decoy + len(pkg).to_bytes(4, "big") + pkg + b"pad" * 50 + len(pkg).to_bytes(4, "big") + pkg
        found = self.mod.find_packages(blob)
        assert len(found) == 1 and next(iter(found.values()))[1] == pkg

    def test_requires_chip_marker(self):
        pkg = bytearray(self.package(3))
        pkg[0x424:0x42A] = b"XXXXXX"
        blob = len(pkg).to_bytes(4, "big") + bytes(pkg)
        assert self.mod.find_packages(blob) == {}


class TestMsfaTable:
    mod = load("check_msfa_table")

    def image(self, variant=False):
        rows = [list(r) for r in self.mod.MSFA_ALGORITHMS]
        if variant:                                   # Dexed's rows 4 and 6 (0xC1)
            rows[3][0] = 0xC1
            rows[5][0] = 0xC1
        table = bytes(b for r in rows for b in r)
        return b"\x11" * 1000 + table + b"\x22" * 500

    def test_the_table_is_googles(self):
        """The reference is the vendored msfa fm_core.cc's table, row for row."""
        import re
        src = (ROOT / "engines" / "third_party" / "msfa" / "fm_core.cc").read_text()
        rows = re.findall(r"\{ \{ ((?:0x[0-9a-f]{2}, ){5}0x[0-9a-f]{2}) \} \}", src)
        assert [tuple(int(x, 16) for x in r.split(", ")) for r in rows] == \
            list(self.mod.MSFA_ALGORITHMS)

    def test_finds_the_fm1_table(self, tmp_path, capsys):
        """The FM-1's images carry Google's table, rows 4 and 6 included."""
        path = tmp_path / "app.bin"
        path.write_bytes(self.image())
        assert self.mod.main(["check", str(path)]) == 0
        out = capsys.readouterr().out
        assert "file offset 0x3E8" in out and "32/32 rows identical" in out

    def test_finds_the_dexed_variant(self, tmp_path, capsys):
        path = tmp_path / "app.bin"
        path.write_bytes(self.image(variant=True))
        assert self.mod.main(["check", str(path)]) == 0
        assert "30/32 rows identical" in capsys.readouterr().out

    def test_reports_missing_table(self, tmp_path, capsys):
        path = tmp_path / "app.bin"
        path.write_bytes(b"\x00" * 4096)
        assert self.mod.main(["check", str(path)]) == 1
        assert "NOT found" in capsys.readouterr().out
