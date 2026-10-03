import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import library

class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        (self.root/"outputs/test").mkdir(parents=True)
        self.patch=patch.object(library,"ROOT",self.root)
        self.patch.start()
    def tearDown(self):
        self.patch.stop()
        self.temp.cleanup()
    def test_rejects_outside_output_folder(self):
        for name in ("../",str(self.root),"test/../.."):
            with self.assertRaises(ValueError): library.run_path(name)
    def test_variant_topology_does_not_inherit_high_poly_pass(self):
        path=self.root/"outputs/test"
        (path/"mesh-audit.json").write_text(json.dumps({"faces":300000,"watertight":True}))
        (path/"game-ready-audit.json").write_text(json.dumps({"faces":30088,"watertight_after_uv_weld":False}))
        self.assertIn("passed",library.describe(path,"final.glb"))
        self.assertIn("not watertight",library.describe(path,"game_ready.glb"))
    def test_only_asset_directories_are_listed(self):
        (self.root/"outputs/test/final.glb").touch()
        (self.root/"outputs/unfinished").mkdir()
        self.assertEqual([r["id"] for r in library.records()],["test"])
    def test_missing_audit_is_not_a_pass(self):
        self.assertIn("not verified",library.describe(self.root/"outputs/test","textured.glb"))

if __name__=="__main__": unittest.main()
