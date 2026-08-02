import json
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "workers" / "source-capture.mjs"


class SourceCaptureWorkerTests(unittest.TestCase):
    def run_module(self, expression):
        script = textwrap.dedent(
            f"""
            const module = await import({json.dumps(WORKER.as_uri())});
            const result = await ({expression})(module);
            console.log(JSON.stringify(result));
            """
        )
        completed = subprocess.run(
            ["node", "--input-type=module", "--eval", script],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(completed.stdout)

    def test_only_safe_public_https_urls_are_accepted_for_capture(self):
        result = self.run_module(
            "(module) => ["
            "module.isSafePublicSourceUrl('https://www.notion.so/releases'), "
            "module.isSafePublicSourceUrl('http://www.notion.so/releases'), "
            "module.isSafePublicSourceUrl('https://localhost/private'), "
            "module.isSafePublicSourceUrl('https://127.0.0.1/private'), "
            "module.isSafePublicSourceUrl('https://user@www.notion.so/private')"
            "]"
        )
        self.assertEqual(result, [True, False, False, False, False])

    def test_equivalent_text_has_one_fingerprint_and_changed_text_generates_review_candidate(self):
        result = self.run_module(
            "async (module) => { "
            "const first = await module.createSnapshot('  Update   shipped today.  '); "
            "const same = await module.createSnapshot('Update shipped today.'); "
            "const changed = await module.createSnapshot('Update shipped tomorrow.'); "
            "return {sameHash: first.contentHash === same.contentHash, "
            "sameCandidate: module.shouldQueueCandidate(first.contentHash, same.contentHash), "
            "changedCandidate: module.shouldQueueCandidate(first.contentHash, changed.contentHash), "
            "text: first.extractedText};"
            "}"
        )
        self.assertTrue(result["sameHash"])
        self.assertFalse(result["sameCandidate"])
        self.assertTrue(result["changedCandidate"])
        self.assertEqual(result["text"], "Update shipped today.")

    def test_worker_writes_review_pipeline_only_never_evidence_or_matrix_entities(self):
        source = WORKER.read_text(encoding="utf-8")
        self.assertIn("export default", source)
        self.assertIn("scheduled", source)
        self.assertIn("source_capture_candidates", source)
        self.assertIn("source_capture_snapshots", source)
        self.assertNotIn("/rest/v1/evidence", source)
        self.assertNotIn("/rest/v1/matrix_cells", source)
        self.assertNotIn("/rest/v1/insights", source)

    def test_manual_capture_route_and_cors_allow_only_pages_production_and_previews(self):
        result = self.run_module(
            "async (module) => { "
            "const handler = module.default.fetch; "
            "const env = {}; const ctx = {}; "
            "const call = async (method, path, origin) => { "
            "const response = await handler(new Request('https://worker.example' + path, {"
            "method, headers: origin ? {Origin: origin} : {}}), env, ctx); "
            "return {status: response.status, origin: response.headers.get('access-control-allow-origin'), "
            "methods: response.headers.get('access-control-allow-methods'), "
            "headers: response.headers.get('access-control-allow-headers')}; }; "
            "return ["
            "await call('GET', '/manual-capture', 'https://zacclover-competitor.pages.dev'), "
            "await call('OPTIONS', '/manual-capture', 'https://zacclover-competitor.pages.dev'), "
            "await call('OPTIONS', '/manual-capture', 'https://feature.zacclover-competitor.pages.dev'), "
            "await call('OPTIONS', '/manual-capture', 'https://zacclover-competitor.pages.dev.evil.example'), "
            "await call('POST', '/other', 'https://zacclover-competitor.pages.dev')]; }"
        )
        self.assertEqual(result[0]["status"], 405)
        self.assertEqual(result[1]["status"], 204)
        self.assertEqual(result[1]["origin"], "https://zacclover-competitor.pages.dev")
        self.assertEqual(result[1]["methods"], "POST")
        self.assertEqual(result[1]["headers"], "Authorization, Content-Type")
        self.assertEqual(result[2]["status"], 204)
        self.assertEqual(result[2]["origin"], "https://feature.zacclover-competitor.pages.dev")
        self.assertEqual(result[3]["status"], 403)
        self.assertIsNone(result[3]["origin"])
        self.assertEqual(result[4]["status"], 404)

    def test_manual_capture_rejects_bad_input_and_requires_verified_user_jwt(self):
        result = self.run_module(
            "async (module) => { const calls = []; globalThis.fetch = async (url, init = {}) => { "
            "calls.push({url: String(url), headers: Object.fromEntries(new Headers(init.headers))}); "
            "return new Response(JSON.stringify({message: 'invalid token'}), {status: 401, headers: {'content-type': 'application/json'}}); }; "
            "const env = {SUPABASE_URL: 'https://project.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'service-secret', "
            "SUPABASE_PUBLISHABLE_KEY: 'public-key'}; const origin = 'https://zacclover-competitor.pages.dev'; "
            "const invoke = (body, authorization = 'Bearer user-jwt', contentType = 'application/json') => "
            "module.default.fetch(new Request('https://worker.example/manual-capture', {method: 'POST', "
            "headers: {Origin: origin, Authorization: authorization, 'Content-Type': contentType}, body}), env, {}); "
            "const malformed = await invoke('{'); const missing = await invoke('{}'); "
            "const noBearer = await invoke(JSON.stringify({sourceId: '11111111-1111-4111-8111-111111111111'}), 'Basic nope'); "
            "const unverified = await invoke(JSON.stringify({sourceId: '11111111-1111-4111-8111-111111111111'})); "
            "return {statuses: [malformed.status, missing.status, noBearer.status, unverified.status], calls}; }"
        )
        self.assertEqual(result["statuses"], [400, 400, 401, 401])
        self.assertEqual(len(result["calls"]), 1)
        self.assertTrue(result["calls"][0]["url"].endswith("/auth/v1/user"))
        self.assertEqual(result["calls"][0]["headers"]["authorization"], "Bearer user-jwt")
        self.assertEqual(result["calls"][0]["headers"]["apikey"], "public-key")
        self.assertNotIn("service-secret", result["calls"][0]["headers"].values())

    def test_manual_capture_checks_membership_and_manual_run_cooldown(self):
        result = self.run_module(
            "async (module) => { const calls = []; const now = Date.now(); globalThis.fetch = async (url, init = {}) => { "
            "const value = String(url); calls.push(value); "
            "if (value.endsWith('/auth/v1/user')) return Response.json({id: '22222222-2222-4222-8222-222222222222'}); "
            "if (value.includes('/competitor_sources?')) return Response.json([{id: '11111111-1111-4111-8111-111111111111', "
            "workspace_id: '33333333-3333-4333-8333-333333333333', tab_id: '44444444-4444-4444-8444-444444444444', "
            "competitor_id: '55555555-5555-4555-8555-555555555555', url: 'https://example.com'}]); "
            "if (value.includes('/workspace_members?')) return Response.json([{workspace_id: '33333333-3333-4333-8333-333333333333'}]); "
            "if (value.includes('/source_capture_runs?') && (init.method || 'GET') === 'GET') "
            "return Response.json([{created_at: new Date(now - 60_000).toISOString()}]); "
            "throw new Error('unexpected request ' + value); }; "
            "const env = {SUPABASE_URL: 'https://project.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'service-secret', "
            "SUPABASE_PUBLISHABLE_KEY: 'public-key'}; const request = new Request('https://worker.example/manual-capture', {method: 'POST', "
            "headers: {Origin: 'https://preview.zacclover-competitor.pages.dev', Authorization: 'Bearer user-jwt', "
            "'Content-Type': 'application/json'}, body: JSON.stringify({sourceId: '11111111-1111-4111-8111-111111111111'})}); "
            "const response = await module.default.fetch(request, env, {}); return {status: response.status, body: await response.json(), calls}; }"
        )
        self.assertEqual(result["status"], 429)
        self.assertEqual(result["body"]["error"]["code"], "manual_capture_cooldown")
        cooldown_call = next(call for call in result["calls"] if "/source_capture_runs?" in call)
        self.assertIn("trigger_type=eq.manual", cooldown_call)
        self.assertIn("order=created_at.desc", cooldown_call)
        self.assertNotIn("last_fetched_at", cooldown_call)

    def test_successful_manual_capture_reuses_review_pipeline_with_manual_trigger(self):
        result = self.run_module(
            "async (module) => { const calls = []; globalThis.fetch = async (url, init = {}) => { "
            "const value = String(url); const method = init.method || 'GET'; const body = init.body ? JSON.parse(init.body) : null; "
            "calls.push({url: value, method, body, auth: new Headers(init.headers).get('authorization')}); "
            "if (value.endsWith('/auth/v1/user')) return Response.json({id: '22222222-2222-4222-8222-222222222222'}); "
            "if (value.includes('/competitor_sources?') && method === 'GET') return Response.json([{id: '11111111-1111-4111-8111-111111111111', "
            "workspace_id: '33333333-3333-4333-8333-333333333333', tab_id: '44444444-4444-4444-8444-444444444444', "
            "competitor_id: '55555555-5555-4555-8555-555555555555', url: 'https://public.example/page'}]); "
            "if (value.includes('/workspace_members?')) return Response.json([{workspace_id: '33333333-3333-4333-8333-333333333333'}]); "
            "if (value.includes('/source_capture_runs?') && method === 'GET') return Response.json([]); "
            "if (value.endsWith('/rest/v1/source_capture_runs') && method === 'POST') return Response.json([body]); "
            "if (value.includes('/source_capture_snapshots?') && method === 'GET') return Response.json([]); "
            "if (value === 'https://public.example/page') return new Response('<title>Release</title><main>New release</main>', {headers: {'content-type': 'text/html'}}); "
            "if (value.endsWith('/rest/v1/source_capture_snapshots') && method === 'POST') return Response.json([body]); "
            "if (value.endsWith('/rest/v1/source_capture_candidates') && method === 'POST') return Response.json([body]); "
            "if (method === 'PATCH') return new Response(null, {status: 204}); throw new Error('unexpected request ' + value); }; "
            "const env = {SUPABASE_URL: 'https://project.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'service-secret', "
            "SUPABASE_PUBLISHABLE_KEY: 'public-key'}; const response = await module.default.fetch(new Request('https://worker.example/manual-capture', {method: 'POST', "
            "headers: {Origin: 'https://zacclover-competitor.pages.dev', Authorization: 'Bearer user-jwt', 'Content-Type': 'application/json'}, "
            "body: JSON.stringify({sourceId: '11111111-1111-4111-8111-111111111111'})}), env, {}); "
            "return {status: response.status, body: await response.json(), calls}; }"
        )
        self.assertEqual(result["status"], 200)
        self.assertTrue(result["body"]["ok"])
        self.assertTrue(result["body"]["result"]["candidateQueued"])
        run_insert = next(call for call in result["calls"] if call["url"].endswith("/rest/v1/source_capture_runs") and call["method"] == "POST")
        self.assertEqual(run_insert["body"]["trigger_type"], "manual")
        service_calls = [call for call in result["calls"] if "/rest/v1/" in call["url"]]
        self.assertTrue(all(call["auth"] == "Bearer service-secret" for call in service_calls))


if __name__ == "__main__":
    unittest.main()
