import json
import struct
import tempfile
import unittest
from pathlib import Path

from tools.native.analyze_ka6_wav import WaveError, analyze, compare_windows, inspect_wave, read_annotations

PCM_GUID = bytes.fromhex("0100000000001000800000aa00389b71")


def make_wav(path, frames, extensible=False, channels=6, rate=48000, bits=32,
             valid_bits=32, subtype=PCM_GUID, truncate_data=0):
    align = channels * (bits // 8)
    if extensible:
        fmt = struct.pack("<HHIIHHHHI", 0xFFFE, channels, rate, rate * align,
                          align, bits, 22, valid_bits, 0x3f) + subtype
    else:
        fmt = struct.pack("<HHIIHH", 1, channels, rate, rate * align, align, bits)
    payload = b"".join(struct.pack("<6i", *frame) for frame in frames)
    if truncate_data:
        payload = payload[:-truncate_data]
    chunks = b"fmt " + struct.pack("<I", len(fmt)) + fmt
    if len(fmt) & 1:
        chunks += b"\0"
    chunks += b"data" + struct.pack("<I", len(payload)) + payload
    riff = b"WAVE" + chunks
    path.write_bytes(b"RIFF" + struct.pack("<I", len(riff)) + riff)


class Ka6WavAnalysisTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_pcm_channel_stats_clip_counts_and_one_second_windows(self):
        path = self.root / "capture.wav"
        frames = [(1000, -2000, 0, 0, 0, 0)] * 48001
        frames[0] = (0x7fffffff, -0x80000000, 0, 0, 0, 0)
        make_wav(path, frames)
        out = analyze(path)
        self.assertEqual(out["data_frames"], 48001)
        self.assertEqual([w["channels"]["1"]["frames"] for w in out["windows"]], [48000, 1])
        self.assertEqual(out["channels"]["1"]["clipped_samples"], 1)
        self.assertEqual(out["channels"]["2"]["clipped_samples"], 1)
        self.assertAlmostEqual(out["windows"][0]["channels"]["1"]["peak"], 1.0, places=8)
        self.assertEqual(out["windows"][0]["channels"]["2"]["peak"], 1.0)

    def test_extensible_pcm_accepts_pcm_subformat(self):
        path = self.root / "extensible.wav"
        make_wav(path, [(4, -8, 0, 0, 0, 0)], extensible=True)
        out = analyze(path)
        self.assertEqual(out["format"]["container"], "WAVE_FORMAT_EXTENSIBLE PCM")
        self.assertEqual(out["format"]["channel_mask"], 0x3f)

    def test_rejects_unexpected_channels_rate_bitdepth_and_subformat(self):
        for kwargs in ({"channels": 2}, {"rate": 44100}, {"bits": 16},
                       {"extensible": True, "subtype": b"X" * 16}):
            with self.subTest(kwargs=kwargs):
                p = self.root / "bad.wav"
                make_wav(p, [(0, 0, 0, 0, 0, 0)], **kwargs)
                with self.assertRaises(WaveError):
                    inspect_wave(p)

    def test_rejects_partial_frame_and_truncated_container(self):
        p = self.root / "bad.wav"
        make_wav(p, [(1, 2, 3, 4, 5, 6)], truncate_data=1)
        with self.assertRaises(WaveError):
            inspect_wave(p)
        p.write_bytes(b"RIFF\x20\x00\x00\x00WAVEfmt ")
        with self.assertRaises(WaveError):
            inspect_wave(p)

    def test_annotations_are_timing_only_and_validate_schema(self):
        p = self.root / "events.jsonl"
        p.write_text(json.dumps({"kind": "boot", "t_seconds": 0.4}) + "\n" +
                     json.dumps({"kind": "stimulus", "t_seconds": 1.2, "label": "C4"}) + "\n")
        result = read_annotations(p, 1.0)
        self.assertFalse(result[1]["within_capture"])
        self.assertIn("does not prove MIDI", result[0]["interpretation"])
        p.write_text('{"kind":"note-on","t_seconds":0}\n')
        with self.assertRaises(ValueError):
            read_annotations(p, 1.0)

    def test_baseline_comparison_pairs_only_shared_windows(self):
        a = self.root / "a.wav"
        b = self.root / "b.wav"
        make_wav(a, [(100, 200, 0, 0, 0, 0)] * 48001)
        make_wav(b, [(50, 100, 0, 0, 0, 0)] * 48000)
        now, before = analyze(a), analyze(b)
        cmp = compare_windows(now, before)
        self.assertEqual(cmp["matched_windows"], 1)
        self.assertAlmostEqual(cmp["windows"][0]["channels"]["1"]["rms_delta"],
                               now["windows"][0]["channels"]["1"]["rms"] -
                               before["windows"][0]["channels"]["1"]["rms"])
        with self.assertRaises(WaveError):
            compare_windows(now, analyze(a) | {"format": {"sample_rate": 44100}})


if __name__ == "__main__":
    unittest.main()
