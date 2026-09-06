from orpheus import workflow_common
from tests.support import load_case
'Synthetic controller/evidence fixtures test real ADK and real DSP, not model accuracy.'
import asyncio
import json
import tempfile
import unittest
import os
from pathlib import Path
from unittest.mock import patch
from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.adk.runners import Runner
from google.adk.sessions import DatabaseSessionService
from google.genai import types
from orpheus.projects import media
from orpheus import arrangement as a
from orpheus import perception as p
from orpheus.workflow import build

def fixture(case):
    evidence = {}
    ids = {}
    for role in ('target', 'source'):
        receipt, _, samples = p.window(case, role, 0, 2)
        raw = {'media_id': receipt['media_id'], 'duration_s': 2, 'audio_access': 'available', 'events': [{'kind': 'impulse', 'label': 'synthetic test event', 'onset_range_s': [0.1, 0.2], 'offset_range_s': [1.5, 1.6], 'evidence': 'Synthetic fixture, not a model conclusion'}]}
        key = p.digest(json.dumps({'receipt': receipt, 'model': p.MODEL, 'prompt': p.PROMPT, 'version': 1}, sort_keys=True).encode())
        ev = {'evidence_id': key, 'receipt': receipt, 'served_model': p.MODEL, 'inventory': p.validate_inventory(raw, receipt), 'measurements': p.measurements(samples, receipt)}
        evidence[key] = ev
        ids[role] = ev['inventory']['events'][0]['id']
    row = {'id': 'm1', 'target_id': ids['target'], 'source_id': ids['source'], 'target_range_s': [0.5, 1.1], 'source_range_s': [0.1, 0.7], 'kind': 'impact', 'anchor': 'start', 'disposition': 'use', 'confidence': 'uncertain', 'evidence': 'Synthetic fixture', 'gain_db': 0}
    return (evidence, row)

class MappedWorkflow(unittest.TestCase):

    def test_stage_action_is_atomic_and_keeps_impact_gate(self):
        from types import SimpleNamespace
        case = {**load_case('shoes'), 'context': '', 'style': ''}
        evidence, row = fixture(case)
        row['kind'] = 'composite'
        phases = [{'kind': 'impact', 'target_range_s': [0.5, 0.8], 'source_range_s': [0.1, 0.4], 'target_anchor_s': 0.65, 'source_anchor_s': 0.2, 'evidence': 'Synthetic attack'}, {'kind': 'texture', 'target_range_s': [0.8, 1.1], 'source_range_s': [0.4, 0.7], 'target_anchor_s': 0.8, 'source_anchor_s': 0.4, 'evidence': 'Synthetic body'}]
        with tempfile.TemporaryDirectory() as d:
            tools = {t.__name__: t for t in build(case, Path(d), lambda *a, **kw: None).sub_agents[0].tools}
            ctx = SimpleNamespace(state={'audio_evidence': evidence}, actions=SimpleNamespace())
            saved = tools['save_arrangement'](json.dumps([row]), ctx)
            bad = [{**phases[0], 'source_range_s': [0, 0.4]}, phases[1]]
            self.assertIn('error', tools['stage_action']('m1', json.dumps(bad), ctx))
            self.assertEqual(ctx.state['arrangement']['id'], saved['id'])
            result = tools['stage_action']('m1', json.dumps(phases), ctx)
            self.assertNotIn('error', result)
            self.assertEqual(result['valid_mapping_ids'], ['m1-phase-1', 'm1-phase-2'])
            self.assertIn('impact evidence gate', tools['render_arrangement']('unfitted stages', ctx)['error'])

    def test_coverage_and_decoded_candidate_observer(self):
        from types import SimpleNamespace
        case = {**load_case('shoes'), 'context': '', 'style': ''}
        evidence, row = fixture(case)

        async def fake_request(observer, receipt, data):
            self.assertEqual(receipt['role'], 'candidate')
            self.assertTrue(data.startswith(b'RIFF'))
            raw = {'media_id': receipt['media_id'], 'duration_s': receipt['duration_s'], 'audio_access': 'available', 'events': []}
            return {'model': p.MODEL, 'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(raw)}}]}
        with tempfile.TemporaryDirectory() as d, patch.object(p.Perception, 'request', fake_request), patch.dict(os.environ, {'ORPHEUS_AUDIO_ENABLED': '1'}):
            folder = Path(d)
            logs = []
            tools = {t.__name__: t for t in build(case, folder, lambda event, **kw: logs.append(event)).sub_agents[0].tools}
            ctx = SimpleNamespace(state={'audio_evidence': evidence, 'cycle': 1, 'candidates': [], 'delivered_centers': [0.8], 'event_reviews': [{'center_s': 0.8, 'verdict': 'target', 'observation': 'Fixture'}]}, actions=SimpleNamespace())
            tools['save_arrangement'](json.dumps([row]), ctx)
            options = tools['inspect_mapping_source']('m1', ctx)
            self.assertTrue(options['options'])
            tools['fit_mapping_impact']('m1', 0, 0.8, 'Fixture', ctx)
            rendered = tools['render_arrangement']('Fixture', ctx)
            self.assertNotIn('error', rendered)
            measurement = tools['measure_candidate'](rendered['id'], ctx)
            self.assertEqual(measurement['coverage']['missing_output_ids'], [])
            self.assertTrue((folder / (rendered['id'] + '-measurement.json')).is_file())
            report = asyncio.run(tools['review_candidate_audio'](rendered['id'], 0, 1, ctx))
            self.assertEqual(report['status'], 'ok')
            self.assertEqual(report['receipt']['file_sha256'], p.digest((folder / (rendered['id'] + '.mp4')).read_bytes()))
            self.assertEqual(ctx.state['audio_evidence'], evidence)
            self.assertIn('candidate_audio_review', logs)
            cached = asyncio.run(tools['review_candidate_audio'](rendered['id'], 0, 1, ctx))
            self.assertTrue(cached['cache_hit'])
            catalog = a.catalog(case, evidence)['target']
            empty = a.coverage({'arrangement': {'rows': []}}, catalog, [{'center_s': 0.8, 'verdict': 'target'}])
            self.assertEqual(len(empty['unmapped_target_ids']), 1)
            self.assertEqual(empty['reviewed_contacts_without_output_s'], [0.8])

    def test_temporal_review_delivery_accumulates_across_windows(self):
        from types import SimpleNamespace
        case = {**load_case('shoes'), 'context': '', 'style': ''}
        with tempfile.TemporaryDirectory() as d:
            editor = build(case, Path(d), lambda *a, **kw: None).sub_agents[0]
            tools = {t.__name__: t for t in editor.tools}
            ctx = SimpleNamespace(state={'controller_calls': 0, 'reviewed': [], 'notes': [], 'candidates': [], 'audio_evidence': {}, 'delivered_centers': [], 'delivered_frame_receipts': []}, actions=SimpleNamespace())
            self.assertNotIn('error', tools['review_window'](0.8, 1.0, 0.1, [], ctx))
            editor.before_model_callback(ctx, SimpleNamespace(contents=[]))
            first = set(ctx.state['delivered_centers'])
            self.assertTrue(first)
            self.assertNotIn('error', tools['review_window'](1.2, 1.4, 0.1, [], ctx))
            editor.before_model_callback(ctx, SimpleNamespace(contents=[]))
            self.assertTrue(first <= set(ctx.state['delivered_centers']))
            with patch.object(p, 'window', side_effect=ValueError('Shorter original audio')):
                packet = tools['review_window'](1.5, 1.7, 0.1, [], ctx)
            self.assertNotIn('error', packet)
            self.assertEqual(packet['target_signal']['status'], 'unavailable')
            editor.before_model_callback(ctx, SimpleNamespace(contents=[]))
            self.assertTrue(any((t >= 1.5 for t in ctx.state['delivered_centers'])))

    def test_automatic_fitting_tools_persist_mapping(self):
        from types import SimpleNamespace
        case = {**load_case('shoes'), 'context': '', 'style': ''}
        evidence, row = fixture(case)
        with tempfile.TemporaryDirectory() as d:
            editor = build(case, Path(d), lambda *a, **kw: None).sub_agents[0]
            tools = {t.__name__: t for t in editor.tools}
            ctx = SimpleNamespace(state={'audio_evidence': evidence, 'reviewed': [], 'event_reviews': [], 'delivered_centers': [], 'cycle': 1}, actions=SimpleNamespace())
            self.assertNotIn('error', tools['save_arrangement'](json.dumps([row]), ctx))
            blocked = tools['render_arrangement']('before evidence', ctx)
            self.assertIn('impact evidence gate', blocked['error'])
            self.assertIn('inspect_mapping_source', tools['fit_mapping_impact']('m1', 0, 0.8, 'Missing source inspection', ctx)['error'])
            options = tools['inspect_mapping_source']('m1', ctx)
            self.assertGreater(options['total'], 0)
            result = tools['fit_mapping_impact']('m1', 0, 0.8, 'Synthetic integration target contact, not visual truth', ctx)
            self.assertNotIn('error', result)
            self.assertEqual(ctx.state['arrangement']['rows'][0]['target_anchor_s'], 0.8)
            self.assertEqual(ctx.state['arrangement']['rows'][0]['target_body_dbfs'], -22)
            blocked = tools['render_arrangement']('without temporal review', ctx)
            self.assertIn('temporal review', blocked['error'])
            ctx.state['delivered_centers'] = [0.8]
            ctx.state['event_reviews'] = [{'center_s': 0.8, 'verdict': 'target', 'observation': 'Synthetic temporal review'}]
            ready = tools['render_arrangement']('after contact, source and temporal evidence', ctx)
            self.assertNotIn('error', ready)
            self.assertIn('error', tools['fit_mapping_impact']('m1', 999, 0.8, 'invalid option test', ctx))
            unknown = tools['inspect_mapping_source']('arrangement-id-not-row', ctx)
            self.assertEqual(unknown['valid_mapping_ids'], ['m1'])
            self.assertEqual(len(list(Path(d).glob('arrangement-*.json'))), 2)

    def test_compact_mapping_context_separates_arrangement_and_row_ids(self):
        from types import SimpleNamespace
        case = {**load_case('shoes'), 'context': '', 'style': ''}
        evidence, row = fixture(case)
        second = {**row, 'id': 'm2', 'target_range_s': [1.1, 1.6], 'source_range_s': [0.1, 0.7], 'reuse_reason': 'Synthetic fixture reuses the same inspected source event'}
        with tempfile.TemporaryDirectory() as d:
            editor = build(case, Path(d), lambda *a, **kw: None).sub_agents[0]
            tools = {t.__name__: t for t in editor.tools}
            ctx = SimpleNamespace(state={'audio_evidence': evidence}, actions=SimpleNamespace())
            saved = tools['save_arrangement'](json.dumps([row, second]), ctx)
            self.assertNotIn('error', saved)
            context = tools['mapping_context'](ctx)
            self.assertEqual(context['arrangement_id'], saved['id'])
            self.assertEqual(context['valid_mapping_ids'], ['m1', 'm2'])
            self.assertEqual([r['mapping_id'] for r in context['rows']], ['m1', 'm2'])
            self.assertNotEqual(context['arrangement_id'], context['valid_mapping_ids'][0])

    def test_batch_inspection_and_fitting_preserve_per_row_receipts(self):
        from types import SimpleNamespace
        case = {**load_case('shoes'), 'context': '', 'style': ''}
        evidence, row = fixture(case)
        second = {**row, 'id': 'm2', 'target_range_s': [1.1, 1.6], 'source_range_s': [0.1, 0.7], 'reuse_reason': 'Synthetic fixture reuses the same inspected source event'}
        with tempfile.TemporaryDirectory() as d:
            editor = build(case, Path(d), lambda *a, **kw: None).sub_agents[0]
            tools = {t.__name__: t for t in editor.tools}
            ctx = SimpleNamespace(state={'audio_evidence': evidence}, actions=SimpleNamespace())
            self.assertNotIn('error', tools['save_arrangement'](json.dumps([row, second]), ctx))
            inspected = tools['inspect_mapping_sources'](['m1', 'm2', 'missing'], ctx)
            self.assertEqual(inspected['succeeded'], ['m1', 'm2'])
            self.assertEqual(inspected['failed'], ['missing'])
            self.assertEqual(set(ctx.state['source_option_reviews']), {'m1', 'm2'})
            specs = json.dumps([{'mapping_id': 'm1', 'source_option': 0, 'target_contact_s': 0.8, 'reason': 'Synthetic first contact'}, {'mapping_id': 'm2', 'source_option': 0, 'target_contact_s': 1.3, 'reason': 'Synthetic second contact'}, {'mapping_id': 'missing', 'source_option': 0, 'target_contact_s': 1.4, 'reason': 'Invalid row test'}])
            fitted = tools['fit_mapping_impacts'](specs, ctx)
            self.assertEqual(fitted['succeeded'], ['m1', 'm2'])
            self.assertEqual(fitted['failed'], ['missing'])
            self.assertEqual(set(ctx.state['impact_fit_receipts']), {'m1', 'm2'})
            ctx.state['delivered_centers'] = [0.8, 1.3]
            ctx.state['event_reviews'] = [{'center_s': 0.8, 'verdict': 'target', 'observation': 'Synthetic first contact'}, {'center_s': 1.3, 'verdict': 'target', 'observation': 'Synthetic second contact'}]
            rendered = tools['render_arrangement']('Batch evidence render', ctx)
            self.assertNotIn('error', rendered)
            measured = tools['measure_candidate'](rendered['id'], ctx)
            self.assertEqual(measured['timing_status'], 'measured')
            self.assertEqual([x['mapping_id'] for x in measured['fitted_impacts']], ['m1', 'm2'])
            self.assertEqual(measured['missing_fitted_impacts'], [])

    def test_controller_budget_and_candidate_strategy_guidance(self):
        from types import SimpleNamespace
        case = {**load_case('shoes'), 'context': '', 'style': ''}
        with tempfile.TemporaryDirectory() as d:
            editor = build(case, Path(d), lambda *a, **kw: None).sub_agents[0]
            instruction = str(editor.instruction)
            self.assertIn('40 controller calls', instruction)
            self.assertIn('structurally different', instruction)
            self.assertIn('measure_candidate', instruction)
            self.assertIn('VISUAL-FIRST ORDER', instruction)
            self.assertIn('first visual evidence operation', instruction)
            self.assertIn('wait for the next model request', instruction)
            ctx = SimpleNamespace(state={'controller_calls': 0, 'notes': [], 'candidates': [], 'audio_evidence': {}, 'arrangement': None}, actions=SimpleNamespace())
            request = SimpleNamespace(contents=[])
            editor.before_model_callback(ctx, request)
            text = '\n'.join((part.text or '' for content in request.contents for part in content.parts or []))
            self.assertIn('40 controller calls', text)
            self.assertIn('Candidate strategy reserve', text)

    def test_prompt_assets_are_owned_by_package(self):
        from orpheus import workflow
        prompt_dir = Path(workflow.__file__).parent / 'prompts'
        expected = ('controller-mapped.md', 'controller-fallback.md', 'perception.md', 'audio.md', 'runtime.md')
        self.assertEqual({p.name for p in prompt_dir.glob('*.md')}, set(expected))
        self.assertEqual(workflow.MAPPED_INSTRUCTION, (prompt_dir / 'controller-mapped.md').read_text())
        self.assertEqual(workflow.INSTRUCTION, (prompt_dir / 'controller-fallback.md').read_text())
        self.assertEqual(workflow.PERCEPTION_INSTRUCTION, (prompt_dir / 'perception.md').read_text())
        self.assertEqual(p.PROMPT, (prompt_dir / 'audio.md').read_text())

    def test_runtime_prompt_assets_render_context_and_frame_labels(self):
        from orpheus import workflow
        from string import Formatter
        self.assertEqual(set(workflow_common.RUNTIME_PROMPTS), {'project_state', 'completion_reserve', 'runtime_status', 'strategy_reserve_few', 'strategy_reserve_many', 'recovery', 'frame_label', 'user_request'})
        self.assertTrue(workflow_common.runtime_prompt('project_state', snapshot='{"ok":true}').startswith('Project state: '))
        self.assertIn('Remaining calls: 7', workflow_common.runtime_prompt('completion_reserve', remaining=7))
        self.assertEqual(workflow_common.runtime_prompt('frame_label', timestamp='1.2500'), 'Clipped-video frame timestamp 1.2500 seconds')
        values = {'project_state': {'snapshot': '{"notes":["{literal}"]}'}, 'completion_reserve': {'remaining': 7}, 'runtime_status': {'cycle': 2, 'renders': 1, 'notes': ['{literal}']}, 'strategy_reserve_few': {}, 'strategy_reserve_many': {'count': 2}, 'recovery': {'action': 'inspect row_1'}, 'frame_label': {'timestamp': '1.2500'}, 'user_request': {'feedback': 'Keep {literal} text', 'context': 'a machine', 'style': 'subtle', 'seconds': 30}}
        for name, args in values.items():
            with self.subTest(template=name):
                fields = {field for _, field, _, _ in Formatter().parse(workflow_common.RUNTIME_PROMPTS[name]) if field is not None}
                self.assertEqual(fields, set(args))
                rendered = workflow_common.runtime_prompt(name, **args)
                self.assertTrue(rendered)
        self.assertTrue(workflow_common.runtime_prompt('user_request', **values['user_request']).startswith('User request:'))
        self.assertIn('Keep {literal} text', workflow_common.runtime_prompt('user_request', **values['user_request']))
        with tempfile.NamedTemporaryFile(suffix='.jpg') as image:
            image.write(b'jpeg-fixture')
            image.flush()
            parts = workflow_common.frame_parts([(1.25, Path(image.name))])
            self.assertEqual(parts[0].text, 'Clipped-video frame timestamp 1.2500 seconds')
            self.assertEqual(parts[1].inline_data.data, b'jpeg-fixture')

    def test_40_call_budget_and_reserve(self):
        from orpheus import worker
        from orpheus import workflow
        from google.adk.agents.run_config import RunConfig
        self.assertEqual(RunConfig(max_llm_calls=worker.MAX_CONTROLLER_CALLS).max_llm_calls, 40)
        self.assertEqual(workflow_common.COMPLETION_WARNING_CALL, 25)
        self.assertEqual(workflow_common.INSPECTION_STOP_CALL, 30)
        self.assertEqual(workflow_common.MAX_REVIEW_BATCH_CENTERS, 5)
        self.assertEqual(workflow_common.MAX_REVIEW_CENTERS_PER_CYCLE, 20)
        self.assertEqual(workflow_common.MAX_REVIEW_CENTERS_PER_TURN, 100)
        self.assertEqual(workflow_common.MAX_ADAPTIVE_FRAMES_PER_CALL, 24)
        self.assertEqual(workflow_common.MAX_ADAPTIVE_FRAMES_PER_TURN, 96)
        self.assertEqual(workflow_common.MAX_WAVEFORM_CALLS, 20)
        self.assertEqual(workflow_common.MAX_BATCH_MAPPING_ROWS, 12)
        self.assertNotIn('70 model calls', workflow.INSTRUCTION)

    def test_unsuitable_sentinel_and_budget_callbacks(self):
        from types import SimpleNamespace
        case = {**load_case('shoes'), 'context': '', 'style': ''}
        with tempfile.TemporaryDirectory() as d:
            editor = build(case, Path(d), lambda *a, **kw: None).sub_agents[0]
            tools = {t.__name__: t for t in editor.tools}
            ctx = SimpleNamespace(state={'controller_calls': 29}, actions=SimpleNamespace(escalate=False, skip_summarization=False))
            self.assertIsNone(editor.before_tool_callback(SimpleNamespace(name='inspect_scene'), {}, ctx))
            ctx.state['controller_calls'] = 30
            self.assertIn('error', editor.before_tool_callback(SimpleNamespace(name='inspect_scene'), {}, ctx))
            self.assertIsNone(editor.before_tool_callback(SimpleNamespace(name='render_arrangement'), {}, ctx))
            for _ in range(3):
                r = editor.after_tool_callback(SimpleNamespace(name='save_arrangement'), {}, ctx, {'error': 'bad ID'})
            self.assertIn('recovery', r)
            result = tools['finish']('none', 'unsuitable', 'No suitable source content', [], ctx)
            self.assertNotIn('error', result)
            self.assertEqual(result['candidate_id'], '')
            self.assertTrue(ctx.actions.escalate)

    def test_empty_mapping_recovery_names_next_action(self):
        from types import SimpleNamespace
        case = {**load_case('shoes'), 'context': '', 'style': ''}
        evidence, row = fixture(case)
        with tempfile.TemporaryDirectory() as d:
            editor = build(case, Path(d), lambda *a, **kw: None).sub_agents[0]
            tools = {t.__name__: t for t in editor.tools}
            ctx = SimpleNamespace(state={'audio_evidence': evidence})
            tools['save_arrangement'](json.dumps([row]), ctx)
            result = tools['save_arrangement']('', ctx)
            self.assertEqual(result['next_step'].split()[0], 'Call')
            self.assertIn('m1', result['mapping_ids'])
            result = tools['save_arrangement']('', ctx)
            self.assertIn('Do not repeat', result['recovery'])

    def test_stale_evidence_and_level_only_reuse(self):
        case = load_case('shoes')
        evidence, row = fixture(case)
        one = a.bind([row], case, evidence)
        two = a.bind([{**row, 'gain_db': -3}], case, evidence)
        self.assertEqual(one['references'], two['references'])
        self.assertNotEqual(one['id'], two['id'])
        for ev in evidence.values():
            ev['served_model'] = 'wrong'
        with self.assertRaises(ValueError):
            a.bind([row], case, evidence)
        evidence, row = fixture(case)
        for ev in evidence.values():
            ev['receipt']['file_sha256'] = 'stale'
        with self.assertRaises(ValueError):
            a.bind([row], case, evidence)

    def test_real_adk_two_renders_resume_and_unsuitable(self):
        case = {**load_case('shoes'), 'context': 'synthetic integration', 'style': ''}
        evidence, row = fixture(case)
        calls = []
        logs = []

        class Scripted(BaseLlm):
            model: str = 'synthetic-controller-no-network'

            async def generate_content_async(self, llm_request, stream=False):
                n = len(calls)
                calls.append(n)
                candidates = [x for event, x in logs if event == 'candidate']
                actions = [('save_arrangement', {'rows_json': json.dumps([row])}), ('inspect_mapping_source', {'mapping_id': 'm1'}), ('fit_mapping_impact', {'mapping_id': 'm1', 'source_option': 0, 'target_contact_s': 0.8, 'reason': 'Synthetic contact alignment test'}), ('review_window', {'start_s': 0.7, 'end_s': 0.9, 'step_s': 0.1, 'crop': []}), ('record_event_review', {'center_s': 0.8, 'verdict': 'target', 'observation': 'Synthetic temporal review'}), ('render_arrangement', {'hypothesis': 'Synthetic baseline with automatic impact preparation'}), ('measure_candidate', {'candidate_id': candidates[-1]['id'] if candidates else ''}), None, ('revise_mapping_gain', {'mapping_id': 'm1', 'gain_db': -4, 'reason': 'Measured baseline needs lower level'}), ('render_arrangement', {'hypothesis': 'Lower gain, preserve mapping evidence'}), ('measure_candidate', {'candidate_id': candidates[-1]['id'] if candidates else ''}), ('finish', {'candidate_id': candidates[-1]['id'] if candidates else '', 'decision': 'needs_human_review', 'comparison': 'Synthetic -4dB revision measured; no listening claim', 'unresolved': ['Synthetic fixture does not establish semantic quality']})]
                action = actions[n] if n < len(actions) else None
                part = types.Part(text='Next cycle') if action is None else types.Part(function_call=types.FunctionCall(name=action[0], args=action[1], id=str(n)))
                yield LlmResponse(content=types.Content(role='model', parts=[part]))

        async def run(folder):
            service = DatabaseSessionService(db_url='sqlite+aiosqlite:///' + str(folder / 'test.sqlite'))
            await service.create_session(app_name='test', user_id='local', session_id='one', state={'audio_evidence': evidence, 'cycle': 0, 'notes': []})
            with patch('orpheus.workflow.ControllerModel', return_value=Scripted()):
                agent = build(case, folder, lambda event, **kw: logs.append((event, kw)))
            runner = Runner(app_name='test', agent=agent, session_service=service)
            async for _ in runner.run_async(user_id='local', session_id='one', new_message=types.Content(role='user', parts=[types.Part(text='User request: synthetic integration')])):
                pass
            session = await service.get_session(app_name='test', user_id='local', session_id='one')
            self.assertEqual(len(session.state['candidates']), 2)
            self.assertEqual(session.state['arrangement']['rows'][0]['target_anchor_s'], 0.8)
            self.assertEqual(session.state['arrangement']['rows'][0]['target_body_dbfs'], -22)
            self.assertEqual(session.state['selection']['decision'], 'needs_human_review')
            self.assertNotEqual(*[x['audio_sha256'] for x in session.state['candidates']])
            self.assertFalse(session.state['candidates'][1]['strategy']['distinct_from_prior'])
            await runner.close()
            await service.close()
            reopened = DatabaseSessionService(db_url='sqlite+aiosqlite:///' + str(folder / 'test.sqlite'))
            restored = await reopened.get_session(app_name='test', user_id='local', session_id='one')
            self.assertEqual(restored.state['arrangement']['rows'][0]['gain_db'], -4)
            fresh = await reopened.create_session(app_name='test', user_id='local', session_id='two', state={})
            self.assertNotIn('arrangement', fresh.state)
            await reopened.close()
        with tempfile.TemporaryDirectory() as d:
            asyncio.run(run(Path(d)))
        if os.environ.get('ORPHEUS_TEST_TRACE'):
            from orpheus.projects import atomic
            atomic(Path(os.environ['ORPHEUS_TEST_TRACE']), {'type': 'synthetic_controller_real_adk_real_dsp', 'model_accuracy_test': False, 'events': logs})
if __name__ == '__main__':
    unittest.main()
