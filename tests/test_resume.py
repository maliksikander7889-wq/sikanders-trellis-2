import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import mesh_runner


class ResumeTests(unittest.TestCase):
    def test_hybrid_keeps_shape_and_materials_after_decode_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            image=root/'source.png'
            image.write_bytes(b'input')
            output=root/'run'
            calls=[]
            artifacts={
                'generate':['shape_latents.npz'],
                'materials':['generated_latents.npz'],
                'decode':['raw.ply','generation-metadata.json','texture_volume.npz'],
                'repair':['final.ply','final.glb','mesh-audit.json'],
                'texture':['textured.glb','lowpoly.glb','texture-audit.json'],
                'bake':['game_ready.glb','game-ready-audit.json']}
            def worker(command):
                stage=command[3]
                calls.append(stage)
                if stage=='decode' and calls.count('decode')==1:
                    raise RuntimeError('simulated decoder failure')
                for filename in artifacts[stage]: (output/filename).write_bytes(b'checkpoint')
            argv=['mesh_runner.py','image',str(image),'--output',str(output),
                  '--engine','pixal3d','--resolution','1024','--texture']
            with patch.object(mesh_runner,'configure'),patch.object(mesh_runner,'validate_hardware'),patch.object(mesh_runner,'run_worker',side_effect=worker):
                with patch.object(sys,'argv',argv),self.assertRaisesRegex(RuntimeError,'decoder failure'):
                    mesh_runner.main()
                self.assertEqual(json.loads((output/'stages.json').read_text()),['generate','materials'])
                # CLI defaults must not replace the original engine or texture setting.
                with patch.object(sys,'argv',['mesh_runner.py','image',str(image),'--output',str(output),'--resume']):
                    mesh_runner.main()
                self.assertEqual(calls,['generate','materials','decode','decode','repair','texture','bake'])
                (output/'generated_latents.npz').unlink()
                with patch.object(sys,'argv',['mesh_runner.py','image',str(image),'--output',str(output),'--resume']):
                    mesh_runner.main()
            self.assertEqual(calls[-5:],['materials','decode','repair','texture','bake'])
            self.assertEqual(calls.count('generate'),1)
            self.assertEqual(json.loads((output/'run-settings.json').read_text())['engine'],'pixal3d')
