from orpheus import workflow_common
from tests.support import load_case
'Offline boundary checks; ORPHEUS_LIVE_MCP=1 additionally tests real local MCP in ADK.'
import asyncio
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import httpx
from orpheus import observability as o
from orpheus import projects
from orpheus import takes

class EvidenceChecks(unittest.TestCase):

    def test_redaction_idempotence_outage_and_signal(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(o, 'STORE', Path(tmp)), patch.object(o, 'DB', Path(tmp) / 'db'), patch.object(o, 'config', return_value={'loki_url': 'http://127.0.0.1:1', 'tempo_url': 'http://127.0.0.1:1'}):
            fields = {'requested_model': 'test/model', 'prompt': 'secret-credential', 'response': {'error': 'secret-credential'}, 'metrics': {'integrated_lufs': -23, 'invalid': float('nan')}, 'source_path': 'private.wav'}
            one = o.emit('1234567890abcdef', 'tool_result', fields, 'turn', 1000)
            self.assertEqual(one, o.emit('1234567890abcdef', 'tool_result', fields, 'turn', 1000))
            self.assertEqual(o.pending(), 1)
            with o.connect() as db:
                raw = db.execute('SELECT payload FROM events').fetchone()[0]
            self.assertNotIn('secret', raw)
            self.assertNotIn('private', raw)
            self.assertNotIn('NaN', raw)
            self.assertTrue(json.loads(raw)['tool_error'])
            self.assertTrue(o.flush()['errors'])
            self.assertEqual(o.pending(), 1)
            profile = o.sound_profile(load_case()['sfx_path'])
            self.assertLessEqual(len(profile['envelope']), 120)
            self.assertGreater(profile['duration_s'], 0)
            with self.assertRaises(ValueError):
                o.enqueue('../', 'bad')
            with patch.object(httpx.Client, 'post', return_value=httpx.Response(204, request=httpx.Request('POST', 'http://local'))):
                self.assertEqual(o.flush()['pending'], 0)

    @unittest.skipUnless(os.environ.get('ORPHEUS_LIVE_MCP') == '1', 'Opt-in real local services; no paid model')
    def test_real_adk_mcp_take_experiment(self):
        from google.adk.models.base_llm import BaseLlm
        from google.adk.models.llm_response import LlmResponse
        from google.adk.runners import Runner
        from google.adk.sessions import DatabaseSessionService
        from google.genai import types
        from orpheus import workflow
        calls = []
        results = []
        with tempfile.TemporaryDirectory() as tmp, patch.object(projects, 'PROJECTS', Path(tmp)):
            doc = projects.create(load_case()['video_path'], load_case()['sfx_path'], context='Synthetic controller integration; not a recorded human performance')
            pid = doc['id']
            source = projects.load(pid)['sfx_path']
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            first = takes.add_take(pid, source, 'Imported existing SFX, validation fixture')
            second = takes.add_take(pid, source, 'Same recording, storage comparison fixture; not an independent take')
            child = takes.fitting_project(pid, first['id'])
            self.assertNotEqual(child['id'], pid)
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
            proposal = {'take_id': first['id'], 'change': 'Move microphone farther away in the NEXT human recording', 'expected_effect': 'Test whether body level decreases; maintain recorder gain', 'reason': 'Controlled test proposal; identical fixture takes cannot establish perceptual improvement'}

            class Scripted(BaseLlm):
                model: str = 'scripted-local-mcp-integration-no-provider'

                async def generate_content_async(self, llm_request, stream=False):
                    n = len(calls)
                    calls.append(n)
                    actions = [('query_grafana', {'topic': 'takes', 'candidate_id': ''}), ('propose_take_experiment', {'proposal_json': json.dumps(proposal)}), ('query_grafana', {'topic': 'runtime', 'candidate_id': ''})]
                    if n < len(actions):
                        name, args = actions[n]
                        part = types.Part(function_call=types.FunctionCall(name=name, args=args, id=str(n)))
                    else:
                        part = types.Part(text='Integration complete. No sound-quality judgment.')
                    yield LlmResponse(content=types.Content(role='model', parts=[part]))

            async def run():
                folder = projects.project_dir(child['id'])
                case = projects.load(child['id'])
                service = DatabaseSessionService(db_url='sqlite+aiosqlite:///' + str(Path(tmp) / 'sessions.sqlite'))
                await service.create_session(app_name='test', user_id='local', session_id='mcp', state={'cycle': 0, 'notes': []})
                with patch.object(workflow, 'ControllerModel', return_value=Scripted()):
                    agent = workflow.build(case, folder, lambda *a, **kw: None)
                runner = Runner(app_name='test', agent=agent, session_service=service)
                async for ev in runner.run_async(user_id='local', session_id='mcp', new_message=types.Content(role='user', parts=[types.Part(text='Verify MCP and one take proposal only.')])):
                    for part in ev.content.parts if ev.content else []:
                        if part.function_response:
                            results.append({'name': part.function_response.name, 'response': part.function_response.response})
                session = await service.get_session(app_name='test', user_id='local', session_id='mcp')
                self.assertEqual(session.state['grafana_receipts']['takes:']['status'], 'ok')
                self.assertGreaterEqual(session.state['grafana_receipts']['takes:']['evidence_count'], 2)
                self.assertEqual(session.state['grafana_receipts']['runtime:']['status'], 'ok')
                self.assertEqual(len(list(projects.project_dir(pid).glob('*-experiment.json'))), 1)
                self.assertTrue(all(('error' not in r['response'] for r in results)), results)
                await runner.close()
                await service.close()
            asyncio.run(run())
            projects.atomic(projects.ROOT / 'diagnostics/LOCAL_GRAFANA_ADK_VERIFICATION.json', {'controller': 'scripted; no paid inference or quality claim', 'real_adk': True, 'real_official_mcp': True, 'separate_fitting_project': True, 'original_preserved': True, 'tool_results': results})
if __name__ == '__main__':
    unittest.main()
