import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from tools.make_snapshot import MANIFEST_NAME, create_snapshot


class MakeSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / "project"
        self.root.mkdir()
        self.output = self.base / "out"
        self._write("README.md", b"project readme\n")
        self._write("pyproject.toml", b"[project]\n")
        self._write("run.py", b"print('run')\n")
        self._write("allmynd/mind.py", b"class AllMynd: pass\n")
        self._write("allmynd/bridge.py", b"class Bridge: pass\n")
        self._write("semantic_engine/quantum.py", b"class QuantumState: pass\n")
        self._write("semantic_engine/word_vectors.bin.gz", b"compressed asset")
        self._write("tests/test_sample.py", b"assert True\n")
        self._write("tools/make_snapshot.py", b"# snapshot builder\n")

    def _write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        return path

    def test_archive_contains_source_and_checksums_but_excludes_runtime_data(self):
        excluded = [
            "allmynd/allmynd_v1.json",
            "allmynd/allmynd_v1.json.emergency",
            "allmynd/mind_log.jsonl",
            "allmynd/old.bak.py",
            "allmynd/.env.local.py",
            "allmynd/notes.json",
            "allmynd/.env.local",
            "allmynd/__pycache__/mind.cpython-311.pyc",
            "allmynd/__pycache__/generated.py",
            "allmynd/vessels/private.py",
            "allmynd/mind_maps/generated.py",
            "vessels/node_id.txt",
            "vessels/private.json",
            "mind_maps/mind_map_latest.html",
            ".env",
            "recording.wav",
        ]
        for name in excluded:
            self._write(name, b"must not be archived")
        self._write("allmynd/helper.py", b"def helper(): return 1\n")

        archive_path, count = create_snapshot(self.root, self.output, "snapshot.zip")
        self.assertEqual(count, 10)
        with zipfile.ZipFile(archive_path) as archive:
            names = set(archive.namelist())
            self.assertIn("allmynd/mind.py", names)
            self.assertIn("semantic_engine/word_vectors.bin.gz", names)
            self.assertIn("tests/test_sample.py", names)
            self.assertIn("tools/make_snapshot.py", names)
            self.assertIn(MANIFEST_NAME, names)
            for name in excluded:
                self.assertNotIn(name, names)
            manifest = json.loads(archive.read(MANIFEST_NAME))
            indexed = {item["path"]: item for item in manifest["files"]}
            self.assertEqual(set(indexed), names - {MANIFEST_NAME})
            payload = archive.read("allmynd/mind.py")
            self.assertEqual(indexed["allmynd/mind.py"]["size_bytes"], len(payload))
            self.assertEqual(indexed["allmynd/mind.py"]["sha256"], hashlib.sha256(payload).hexdigest())
            self.assertEqual(manifest["schema_version"], 1)
            self.assertIn("not a runtime-state backup", manifest["purpose"])

    def test_identical_source_produces_identical_zip_bytes(self):
        first, _ = create_snapshot(self.root, self.output, "one.zip")
        second, _ = create_snapshot(self.root, self.output, "two.zip")
        self.assertEqual(first.read_bytes(), second.read_bytes())

    def test_existing_archive_is_never_overwritten(self):
        self.output.mkdir()
        existing = self.output / "snapshot.zip"
        existing.write_bytes(b"user data")
        with self.assertRaises(FileExistsError):
            create_snapshot(self.root, self.output, "snapshot.zip")
        self.assertEqual(existing.read_bytes(), b"user data")

    def test_missing_required_file_fails_before_creating_archive(self):
        (self.root / "allmynd/bridge.py").unlink()
        with self.assertRaisesRegex(ValueError, "missing: allmynd/bridge.py"):
            create_snapshot(self.root, self.output, "snapshot.zip")
        self.assertFalse(self.output.exists())

    def test_output_name_must_be_a_plain_zip_filename(self):
        for name in ("../outside.zip", "not-a-zip.txt", "bad name.zip"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                create_snapshot(self.root, self.output, name)
        self.assertFalse(self.output.exists())

    def test_symlinked_source_file_is_skipped(self):
        target = self.base / "outside.py"
        target.write_text("private = True\n", encoding="utf-8")
        link = self.root / "allmynd" / "linked.py"
        link.symlink_to(target)
        archive_path, _ = create_snapshot(self.root, self.output, "snapshot.zip")
        with zipfile.ZipFile(archive_path) as archive:
            self.assertNotIn("allmynd/linked.py", archive.namelist())


if __name__ == "__main__":
    unittest.main()
