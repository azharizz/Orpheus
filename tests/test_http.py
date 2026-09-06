"""Real loopback HTTP coverage, using disposable generated media only."""
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import httpx
from tests.support import load_case
from orpheus import web, projects


class HttpChecks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory(prefix='orpheus-http-')
        root = Path(cls.folder.name)
        cls.patches = [patch.object(projects, 'ROOT', root), patch.object(projects, 'PROJECTS', root/'projects')]
        for item in cls.patches:
            item.start()
        cls.server = ThreadingHTTPServer(('127.0.0.1',0), web.Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()
        cls.base = f'http://127.0.0.1:{cls.server.server_port}'
        cls.client = httpx.Client(base_url=cls.base,headers={'Origin':cls.base},trust_env=False,timeout=60)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        for item in reversed(cls.patches):
            item.stop()
        cls.folder.cleanup()

    def test_origin_routes_and_config(self):
        for route in ('/v1/','/v2/','/legacy-lab/','/sessions.sqlite','/.env'):
            self.assertEqual(self.client.get(route).status_code,404)
        self.assertEqual(self.client.get('/api/projects',headers={'Host':'evil.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/run',json={},headers={'Origin':'https://evil.example'}).status_code,403)
        self.assertEqual(self.client.post('/api/run',json=[]).status_code,400)
        response=self.client.get('/api/config')
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['storage'],'local')
        self.assertNotIn('key',response.text.lower())

    def test_prepare_take_and_seek_without_inference(self):
        case=load_case()
        files={'video':('scene.mp4',case['video_path'].read_bytes()),'sfx':('sound.wav',case['sfx_path'].read_bytes())}
        with patch.object(web,'start') as start:
            response=self.client.post('/api/projects',files=files,data={'context':'A synthetic test scene'})
            self.assertEqual(response.status_code,201,response.text)
            doc=response.json()['project'];pid=doc['id']
            self.assertEqual(doc['turns'],[])
            start.assert_not_called()
            for name in ('video.mp4','sfx.wav'):
                response=self.client.get(f'/projects/{pid}/{name}',headers={'Range':'bytes=0-99'})
                self.assertEqual(response.status_code,206)
                self.assertEqual(len(response.content),100)
            self.assertEqual(self.client.get(f'/projects/{pid}/video.mp4',headers={'Range':'bytes=-0'}).status_code,416)
            self.assertEqual(self.client.get(f'/projects/{pid}/originals/video.mp4').status_code,404)
            self.assertEqual(self.client.get(f'/projects/{pid}/poster.jpg').status_code,200)
            response=self.client.get('/api/waveform',params={'project_id':pid,'role':'sfx'})
            self.assertEqual(response.status_code,200,response.text)
            self.assertTrue(response.json()['peaks'])
            self.assertEqual(self.client.get('/api/snippet',params={'project_id':pid,'start':'nan','end':'1'}).status_code,400)
            response=self.client.post('/api/takes',data={'project_id':pid,'start_s':'0','brief':'New take'},files={'audio':('take.wav',case['sfx_path'].read_bytes())})
            self.assertEqual(response.status_code,201,response.text)
            tid=response.json()['id']
            self.assertEqual(self.client.get(f'/projects/{pid}/takes/{tid}.wav').status_code,200)
            self.assertEqual(len(self.client.get('/api/takes',params={'project_id':pid}).json()['takes']),1)
            start.assert_not_called()
            response=self.client.post('/api/run',json={'project_id':pid})
            self.assertEqual(response.status_code,202,response.text)
            start.assert_called_once()

    def test_duplicate_upload_field_rejected(self):
        response=self.client.post('/api/projects',files=[('video',('a.mp4',b'x')),('video',('b.mp4',b'x')),('sfx',('a.wav',b'x'))])
        self.assertEqual(response.status_code,400,response.text)

if __name__=='__main__':
    unittest.main()
