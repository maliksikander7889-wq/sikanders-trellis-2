import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient
import app
import library

class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        (self.root/"outputs/demo").mkdir(parents=True)
        (self.root/"outputs/demo/final.glb").write_bytes(b'glTF')
        (self.root/"private.txt").write_text('private')
        self.patches=[patch.object(app,'ROOT',self.root),patch.object(library,'ROOT',self.root)]
        for p in self.patches:p.start()
        self.client=TestClient(app.app)
    def tearDown(self):
        self.client.close()
        for p in self.patches:p.stop()
        self.temp.cleanup()
    def test_library_and_download(self):
        response=self.client.get('/api/library')
        self.assertEqual(response.status_code,200)
        data=response.json()
        self.assertEqual(data[0]['id'],'demo')
        self.assertIsNone(data[0]['versions'][0]['watertight'])
        self.assertEqual(self.client.get(data[0]['versions'][0]['url']).content,b'glTF')
    def test_asset_path_cannot_escape(self):
        with self.assertRaises(app.HTTPException): app.asset_path('demo','../../private.txt')
    def test_rejects_cross_origin_start(self):
        response=self.client.post('/api/jobs',headers={'Origin':'https://elsewhere.example'})
        self.assertEqual(response.status_code,403)
    def test_rejects_unsupported_settings(self):
        response=self.client.post('/api/jobs',data={'resolution':123},files={'file':('test.png',b'bad','image/png')})
        self.assertEqual(response.status_code,422)
        self.assertIsNone(app.active_id)
    def test_invalid_image_releases_slot(self):
        with TestClient(app.app,raise_server_exceptions=False) as client:
            response=client.post('/api/jobs',files={'file':('bad.png',b'not an image','image/png')})
            self.assertEqual(response.status_code,422)
        self.assertIsNone(app.active_id)

    def test_rejects_large_resolution_before_starting_worker(self):
        with patch('resource_guard.gpu_info',return_value={'total_gib':11.94}):
            response=self.client.post('/api/jobs',data={'resolution':2048},files={'file':('test.png',b'bad','image/png')})
        self.assertEqual(response.status_code,422)
        self.assertIn('memory limit',response.json()['detail'])
        self.assertIsNone(app.active_id)

    def test_pixal_requires_downloads(self):
        response=self.client.post('/api/jobs',data={'engine':'pixal3d'},files={'file':('test.png',b'bad','image/png')})
        self.assertEqual(response.status_code,422)
        self.assertIn('Run.exe → Setup & download',response.json()['detail'])
        self.assertIsNone(app.active_id)

    def test_invalid_engine(self):
        response=self.client.post('/api/jobs',data={'engine':'unknown'},files={'file':('test.png',b'bad','image/png')})
        self.assertEqual(response.status_code,422)

    def test_recovery_cannot_escape_outputs(self):
        with self.assertRaises(app.HTTPException): app.resume_run('..')

    def test_worker_success_releases_slot_and_saves_status(self):
        import sys,time
        job={'id':'demo','name':'Test','state':'running','started':time.time(),'message':'Working'}
        app.active_id='demo'
        with patch.object(app,'blender_path',side_effect=RuntimeError('No preview renderer')):
            app.execute_job(job,[sys.executable,'-c',"print('worker completed')"])
        self.assertEqual(job['state'],'complete')
        self.assertIsNone(app.active_id)
        self.assertTrue((self.root/'outputs/demo/job-status.json').exists())

    def test_worker_failure_is_not_reported_as_complete(self):
        import sys,time
        job={'id':'demo','name':'Test','state':'running','started':time.time(),'message':'Working'}
        app.active_id='demo'
        app.execute_job(job,[sys.executable,'-c','raise SystemExit(2)'])
        self.assertEqual(job['state'],'failed')
        self.assertIsNone(app.active_id)

if __name__=='__main__': unittest.main()
