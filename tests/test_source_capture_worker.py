import json
import subprocess
import textwrap
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "workers" / "source-capture.mjs"
WRANGLER = ROOT / "workers" / "wrangler.toml"


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
            "module.isSafePublicSourceUrl('https://100.64.0.1/private'), "
            "module.isSafePublicSourceUrl('https://224.0.0.1/private'), "
            "module.isSafePublicSourceUrl('https://user@www.notion.so/private')"
            "]"
        )
        self.assertEqual(result, [True, False, False, False, False, False, False])

    def test_scheduling_is_disabled_in_config_and_event_handler_is_a_noop(self):
        config = WRANGLER.read_text(encoding="utf-8")
        self.assertNotIn("crons", config)
        result = self.run_module(
            "async (module) => { let fetched = false; globalThis.fetch = async () => { fetched = true; }; "
            "const direct = await module.runScheduledCapture({}); let promised; "
            "await module.default.scheduled({}, {}, {waitUntil(value) { promised = value; }}); "
            "const event = await promised; return {direct, event, fetched}; }"
        )
        self.assertTrue(result["direct"]["disabled"])
        self.assertTrue(result["event"]["disabled"])
        self.assertFalse(result["fetched"])

    def test_only_changelog_source_types_enable_subpage_discovery(self):
        result = self.run_module(
            "(module) => ['changelog','release_notes','blog','product_page','help_center','pricing']"
            ".map((value) => module.supportsUpdateSubpageDiscovery(value))"
        )
        self.assertEqual(result, [True, True, False, False, False, False])

    def test_update_link_discovery_is_same_origin_depth_one_conservative_and_capped(self):
        result = self.run_module(
            "(module) => { const many = Array.from({length:25},(_,i)=>`<a href='/changelog/item-${i}'>x</a>`).join(''); "
            "const html = `<nav><a href='/changelog/nav-item'>nav</a></nav>"
            "<a href='/pricing'>pricing</a><a href='/changelog/one'>one</a>"
            "<a href='/changelog/one/deep'>deep</a><a href='https://other.example/changelog/two'>external</a>"
            "<a href='http://public.example/changelog/insecure'>http</a><a href='https://user@public.example/changelog/private'>credential</a>${many}`; "
            "const links = module.discoverUpdateLinks(html, 'https://public.example/changelog'); "
            "return {links, count: links.length}; }"
        )
        self.assertEqual(result["count"], 20)
        self.assertEqual(result["links"][0], "https://public.example/changelog/one")
        self.assertNotIn("https://public.example/pricing", result["links"])
        self.assertTrue(all("other.example" not in link and "/deep" not in link for link in result["links"]))

    def test_image_discovery_is_same_page_origin_conservative_unique_and_capped(self):
        result = self.run_module(
            "(module) => module.discoverFeatureImageUrls(`<main>"
            "<img src='/a.png'><img src='https://public.example/b.webp'><img src='/a.png'>"
            "<img srcset='/ignored.png 2x'><img src='data:image/png;base64,xx'>"
            "<img src='https://cdn.example/c.png'><img src='/vector.svg'>"
            "<iframe src='/frame.png'></iframe><script src='/script.png'></script>"
            "<div style=\"background:url('/background.png')\"></div>"
            "<img src='/c.gif'><img src='/d.jpg'></main>`, 'https://public.example/releases/item')"
        )
        self.assertEqual(result, [
            "https://public.example/a.png",
            "https://public.example/b.webp",
            "https://public.example/c.gif",
        ])

    def test_image_fetch_rejects_redirect_mime_and_size_and_accepts_only_valid_bytes(self):
        result = self.run_module(
            "async (module) => { const make=(status,type,body,length)=>async (_url,init)=>({status,ok:status>=200&&status<300,"
            "headers:new Headers({'content-type':type,...(length?{'content-length':length}:{})}),"
            "arrayBuffer:async()=>new TextEncoder().encode(body).buffer, redirectMode:init.redirect}); "
            "const run=async(fetcher,url='https://public.example/a.png')=>{try{return await module.fetchFeatureImage(url,'https://public.example/page',fetcher)}catch(e){return null}}; "
            "return {ok:await run(make(200,'image/png','bytes')),redirect:await run(make(302,'image/png','x')),"
            "mime:await run(make(200,'image/svg+xml','x')),declaredLarge:await run(make(200,'image/png','x','5242881')),"
            "actualLarge:await run(make(200,'image/png','x'.repeat(5242881))),svg:await run(make(200,'image/png','x'),'https://public.example/a.svg')}; }"
        )
        self.assertEqual(result["ok"]["mediaType"], "image/png")
        self.assertEqual(result["ok"]["byteSize"], 5)
        self.assertEqual(result["ok"]["redirectMode"], "manual")
        for key in ["redirect", "mime", "declaredLarge", "actualLarge", "svg"]:
            self.assertIsNone(result[key])

    def test_attachment_upload_uses_service_role_and_private_storage_endpoint(self):
        result = self.run_module(
            "async (module) => { const calls=[]; const fetcher=async(url,init)=>{calls.push({url:String(url),headers:Object.fromEntries(new Headers(init.headers)),method:init.method});return new Response(null,{status:200})};"
            "await module.uploadCandidateAttachment({SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'service-secret'},"
            "'candidate/id.png',new Uint8Array([1,2]),'image/png',fetcher);return calls[0]; }"
        )
        self.assertIn("/storage/v1/object/candidate-attachments/candidate/id.png", result["url"])
        self.assertEqual(result["headers"]["authorization"], "Bearer service-secret")
        self.assertEqual(result["headers"]["apikey"], "service-secret")
        self.assertEqual(result["headers"]["content-type"], "image/png")

    def test_candidate_attachment_delete_requires_auth_membership_and_deletes_candidate_only(self):
        result = self.run_module(
            "async (module) => { const calls=[]; globalThis.fetch=async(url,init={})=>{const value=String(url),method=init.method||'GET';calls.push({url:value,method,body:init.body?JSON.parse(init.body):null});"
            "if(value.endsWith('/auth/v1/user')) return Response.json({id:'22222222-2222-4222-8222-222222222222'});"
            "if(value.includes('/source_capture_candidates?')) return Response.json([{id:'11111111-1111-4111-8111-111111111111',workspace_id:'33333333-3333-4333-8333-333333333333'}]);"
            "if(value.includes('/workspace_members?')) return Response.json([{workspace_id:'33333333-3333-4333-8333-333333333333'}]);"
            "if(value.includes('/candidate_attachments?')&&method==='GET') return Response.json([{object_path:'111/a.png'}]);"
            "if(value.includes('/storage/v1/object/candidate-attachments')&&method==='DELETE') return new Response(null,{status:200});"
            "if(method==='DELETE') return new Response(null,{status:204});throw new Error('unexpected '+value)};"
            "const env={SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'service-secret',SUPABASE_PUBLISHABLE_KEY:'public'};"
            "const request=new Request('https://worker.example/candidate-attachments/11111111-1111-4111-8111-111111111111',{method:'DELETE',headers:{Authorization:'Bearer jwt'}});"
            "const response=await module.default.fetch(request,env,{});return {status:response.status,calls}; }"
        )
        self.assertEqual(result["status"], 200)
        urls = [call["url"] for call in result["calls"]]
        self.assertTrue(any("candidate_attachments?" in url for url in urls))
        self.assertTrue(any("source_capture_candidates?" in url and call["method"] == "DELETE" for url, call in zip(urls, result["calls"])))
        for forbidden in ["evidence", "matrix", "insights", "runs", "snapshots"]:
            self.assertFalse(any(forbidden in url for url in urls))

    def test_candidate_attachment_delete_rejects_missing_auth_before_data_access(self):
        result = self.run_module(
            "async (module) => { let fetched=false; globalThis.fetch=async()=>{fetched=true;throw new Error('must not fetch')};"
            "const env={SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'service',SUPABASE_PUBLISHABLE_KEY:'public'};"
            "const response=await module.default.fetch(new Request('https://worker.example/candidate-attachments/11111111-1111-4111-8111-111111111111',{method:'DELETE'}),env,{});"
            "return {status:response.status,body:await response.json(),fetched}; }"
        )
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["body"]["error"]["code"], "authentication_required")
        self.assertFalse(result["fetched"])

    def test_candidate_attachment_get_requires_bearer_auth_before_data_access(self):
        result = self.run_module(
            "async (module) => { let fetched=false; globalThis.fetch=async()=>{fetched=true;throw new Error('must not fetch')};"
            "const env={SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'service-secret',SUPABASE_PUBLISHABLE_KEY:'public'};"
            "const response=await module.default.fetch(new Request('https://worker.example/candidate-attachments/11111111-1111-4111-8111-111111111111/44444444-4444-4444-8444-444444444444'),env,{});"
            "return {status:response.status,body:await response.json(),fetched}; }"
        )
        self.assertEqual(result["status"], 401)
        self.assertEqual(result["body"]["error"]["code"], "authentication_required")
        self.assertFalse(result["fetched"])

    def test_candidate_attachment_get_enforces_workspace_boundary_before_attachment_lookup(self):
        result = self.run_module(
            "async (module) => { const calls=[]; globalThis.fetch=async(url,init={})=>{const value=String(url);calls.push(value);"
            "if(value.endsWith('/auth/v1/user')) return Response.json({id:'22222222-2222-4222-8222-222222222222'});"
            "if(value.includes('/source_capture_candidates?')) return Response.json([{id:'11111111-1111-4111-8111-111111111111',workspace_id:'33333333-3333-4333-8333-333333333333'}]);"
            "if(value.includes('/workspace_members?')) return Response.json([]);throw new Error('unexpected '+value)};"
            "const env={SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'service-secret',SUPABASE_PUBLISHABLE_KEY:'public'};"
            "const request=new Request('https://worker.example/candidate-attachments/11111111-1111-4111-8111-111111111111/44444444-4444-4444-8444-444444444444',{headers:{Authorization:'Bearer jwt'}});"
            "const response=await module.default.fetch(request,env,{});return {status:response.status,body:await response.json(),calls}; }"
        )
        self.assertEqual(result["status"], 403)
        self.assertEqual(result["body"]["error"]["code"], "workspace_access_denied")
        self.assertFalse(any("candidate_attachments?" in url for url in result["calls"]))
        self.assertFalse(any("/storage/v1/object/" in url for url in result["calls"]))

    def test_candidate_attachment_get_requires_attachment_to_belong_to_candidate(self):
        result = self.run_module(
            "async (module) => { const calls=[]; globalThis.fetch=async(url,init={})=>{const value=String(url);calls.push(value);"
            "if(value.endsWith('/auth/v1/user')) return Response.json({id:'22222222-2222-4222-8222-222222222222'});"
            "if(value.includes('/source_capture_candidates?')) return Response.json([{id:'11111111-1111-4111-8111-111111111111',workspace_id:'33333333-3333-4333-8333-333333333333'}]);"
            "if(value.includes('/workspace_members?')) return Response.json([{workspace_id:'33333333-3333-4333-8333-333333333333'}]);"
            "if(value.includes('/candidate_attachments?')) return Response.json([]);throw new Error('unexpected '+value)};"
            "const env={SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'service-secret',SUPABASE_PUBLISHABLE_KEY:'public'};"
            "const request=new Request('https://worker.example/candidate-attachments/11111111-1111-4111-8111-111111111111/44444444-4444-4444-8444-444444444444',{headers:{Authorization:'Bearer jwt'}});"
            "const response=await module.default.fetch(request,env,{});return {status:response.status,body:await response.json(),calls}; }"
        )
        self.assertEqual(result["status"], 404)
        self.assertEqual(result["body"]["error"]["code"], "attachment_not_found")
        attachment_query = next(url for url in result["calls"] if "candidate_attachments?" in url)
        self.assertIn("id=eq.44444444-4444-4444-8444-444444444444", attachment_query)
        self.assertIn("candidate_id=eq.11111111-1111-4111-8111-111111111111", attachment_query)
        self.assertIn("workspace_id=eq.33333333-3333-4333-8333-333333333333", attachment_query)
        self.assertFalse(any("/storage/v1/object/" in url for url in result["calls"]))

    def test_candidate_attachment_get_returns_safe_private_binary_without_service_key_leakage(self):
        result = self.run_module(
            "async (module) => { const calls=[]; globalThis.fetch=async(url,init={})=>{const value=String(url),headers=Object.fromEntries(new Headers(init.headers));calls.push({url:value,headers});"
            "if(value.endsWith('/auth/v1/user')) return Response.json({id:'22222222-2222-4222-8222-222222222222'});"
            "if(value.includes('/source_capture_candidates?')) return Response.json([{id:'11111111-1111-4111-8111-111111111111',workspace_id:'33333333-3333-4333-8333-333333333333'}]);"
            "if(value.includes('/workspace_members?')) return Response.json([{workspace_id:'33333333-3333-4333-8333-333333333333'}]);"
            "if(value.includes('/candidate_attachments?')) return Response.json([{id:'44444444-4444-4444-8444-444444444444',object_path:'111/image one.png',media_type:'image/png',byte_size:4}]);"
            "if(value.includes('/storage/v1/object/candidate-attachments/')) return new Response(new Uint8Array([137,80,78,71]),{headers:{'Content-Type':'image/png','Content-Length':'4'}});"
            "throw new Error('unexpected '+value)};"
            "const env={SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'service-secret',SUPABASE_PUBLISHABLE_KEY:'public'};"
            "const request=new Request('https://worker.example/candidate-attachments/11111111-1111-4111-8111-111111111111/44444444-4444-4444-8444-444444444444',{headers:{Authorization:'Bearer user-jwt',Origin:'https://zacclover-competitor.pages.dev'}});"
            "const response=await module.default.fetch(request,env,{});return {status:response.status,headers:Object.fromEntries(response.headers),bytes:Array.from(new Uint8Array(await response.arrayBuffer())),calls}; }"
        )
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["bytes"], [137, 80, 78, 71])
        self.assertEqual(result["headers"]["content-type"], "image/png")
        self.assertEqual(result["headers"]["cache-control"], "private, no-store")
        self.assertEqual(result["headers"]["x-content-type-options"], "nosniff")
        self.assertEqual(result["headers"]["access-control-allow-origin"], "https://zacclover-competitor.pages.dev")
        storage_call = next(call for call in result["calls"] if "/storage/v1/object/" in call["url"])
        self.assertIn("image%20one.png", storage_call["url"])
        self.assertEqual(storage_call["headers"]["authorization"], "Bearer service-secret")
        self.assertNotIn("service-secret", json.dumps({"headers": result["headers"], "bytes": result["bytes"]}))

    def test_candidate_attachment_get_rejects_unsafe_or_oversized_storage_response(self):
        result = self.run_module(
            "async (module) => { const run=async(storageType,storageBody)=>{globalThis.fetch=async(url,init={})=>{const value=String(url);"
            "if(value.endsWith('/auth/v1/user')) return Response.json({id:'22222222-2222-4222-8222-222222222222'});"
            "if(value.includes('/source_capture_candidates?')) return Response.json([{id:'11111111-1111-4111-8111-111111111111',workspace_id:'33333333-3333-4333-8333-333333333333'}]);"
            "if(value.includes('/workspace_members?')) return Response.json([{}]);"
            "if(value.includes('/candidate_attachments?')) return Response.json([{object_path:'111/a.png',media_type:'image/png',byte_size:storageBody.length}]);"
            "if(value.includes('/storage/v1/object/')) return new Response(storageBody,{headers:{'Content-Type':storageType}});throw new Error('unexpected')};"
            "const env={SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'secret',SUPABASE_PUBLISHABLE_KEY:'public'};"
            "const response=await module.default.fetch(new Request('https://worker.example/candidate-attachments/11111111-1111-4111-8111-111111111111/44444444-4444-4444-8444-444444444444',{headers:{Authorization:'Bearer jwt'}}),env,{});return {status:response.status,body:await response.json()}};"
            "return {mime:await run('image/svg+xml',new Uint8Array([1])),large:await run('image/png',new Uint8Array(5242881))}; }"
        )
        self.assertEqual(result["mime"]["status"], 415)
        self.assertEqual(result["large"]["status"], 415)
        self.assertEqual(result["mime"]["body"]["error"]["code"], "unsafe_attachment")
        self.assertEqual(result["large"]["body"]["error"]["code"], "unsafe_attachment")

    def test_declared_dates_filter_window_and_missing_dates_are_excluded(self):
        result = self.run_module(
            "async (module) => { const index = {canonicalUrl:'https://public.example/releases',html:"
            "`<a href='/releases/in'>in</a><a href='/releases/out'>out</a><a href='/releases/missing'>missing</a>`}; "
            "const pages = {"
            "'https://public.example/releases/in':'<title>Feature A</title><meta property=\"article:published_time\" content=\"2026-08-02T10:00:00Z\"><main>Feature A shipped.</main>',"
            "'https://public.example/releases/out':'<title>Old</title><time datetime=\"2026-07-01\">July 1</time><main>Old.</main>',"
            "'https://public.example/releases/missing':'<title>No date</title><main>Updated on 2026-08-02, but not declared.</main>'}; "
            "const fetcher = async (url, init) => new Response(pages[String(url)],{headers:{'content-type':'text/html'}}); "
            "const found = await module.discoverEligibleUpdates(index,{start:'2026-08-01T00:00:00Z',end:'2026-08-03T00:00:00Z'},fetcher); "
            "return found; }"
        )
        self.assertEqual([entry["title"] for entry in result["entries"]], ["Feature A"])
        self.assertEqual(result["missingDateCount"], 1)
        self.assertIn("Feature A shipped", result["entries"][0]["quotedText"])

    def test_semantic_entry_set_hash_is_order_independent_and_changes_with_entries(self):
        result = self.run_module(
            "async (module) => { const a={url:'https://e.example/releases/a',publishedAt:'2026-08-01T00:00:00.000Z'}; "
            "const b={url:'https://e.example/releases/b',publishedAt:'2026-08-02T00:00:00.000Z'}; "
            "return {first:await module.hashSelectedEntries([a,b]), reordered:await module.hashSelectedEntries([b,a]), single:await module.hashSelectedEntries([a]), "
            "newSet:await module.hashSelectedEntries([a,b,{url:'https://e.example/releases/c',publishedAt:'2026-08-03T00:00:00.000Z'}]), "
            "changedContent:await module.hashSelectedEntries([{...a,contentHash:'changed-body'}])}; }"
        )
        self.assertEqual(result["first"], result["reordered"])
        self.assertNotEqual(result["first"], result["newSet"])
        self.assertNotEqual(result["single"], result["changedContent"])

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

    def test_analysis_input_removes_navigation_duplicates_and_caps_unicode_characters(self):
        result = self.run_module(
            "(module) => { const text = '首页\\nMenu\\n关键更新\\n关键更新\\n' + '中'.repeat(7000); "
            "const cleaned = module.prepareAnalysisInput(text); "
            "return {cleaned, chars: Array.from(cleaned).length}; }"
        )
        self.assertNotIn("首页", result["cleaned"])
        self.assertNotIn("Menu", result["cleaned"])
        self.assertEqual(result["cleaned"].count("关键更新"), 1)
        self.assertEqual(result["chars"], 6000)

    def test_observation_window_requires_paired_ordered_non_future_times(self):
        result = self.run_module(
            "(module) => { const now = new Date('2026-08-03T12:00:00Z'); "
            "const values = [null, {start: '2026-08-01T00:00:00Z', end: '2026-08-02T00:00:00Z'}, "
            "{start: '2026-08-02T00:00:00Z'}, {start: 'August 2 2026', end: '2026-08-03T00:00:00Z'}, "
            "{start: '2026-08-02T00:00:00Z', end: '2026-08-01T00:00:00Z'}, "
            "{start: '2026-08-02T00:00:00Z', end: '2026-08-04T00:00:00Z'}]; "
            "return values.map((value) => { try { return module.validateObservationWindow(value, now); } "
            "catch (error) { return {code: error.code}; } }); }"
        )
        self.assertIsNone(result[0])
        self.assertEqual(result[1]["basis"], "explicit")
        self.assertEqual([item["code"] for item in result[2:]], ["invalid_observation_window"] * 4)

    def test_scheduled_window_uses_previous_success_finished_at_to_planned_time(self):
        result = self.run_module(
            "async (module) => { let url=''; globalThis.fetch=async (value) => { url=String(value); "
            "return Response.json([{finished_at:'2026-08-02T05:00:00Z'}]); }; "
            "const window=await module.deriveObservationWindow({SUPABASE_URL:'https://project.supabase.co',"
            "SUPABASE_SERVICE_ROLE_KEY:'secret'},'source-id',new Date('2026-08-03T06:00:00Z')); return {url,window}; }"
        )
        self.assertIn("status=eq.succeeded", result["url"])
        self.assertIn("order=finished_at.desc", result["url"])
        self.assertEqual(result["window"], {
            "start": "2026-08-02T05:00:00.000Z",
            "end": "2026-08-03T06:00:00.000Z",
            "basis": "prior_success",
        })

    def test_analysis_requires_chinese_feature_fields_and_only_grounds_verified_publication_time(self):
        result = self.run_module(
            "(module) => { const base = {feature_title:'自动化功能',feature_summary:'新增数据库自动化能力。',conclusion:'结论', facts:['事实一','事实二'], "
            "inference:{label:'推断',text:'可能'}, competitive_impact:{label:'竞争影响',text:'有限'}, "
            "confidence:'medium', publication_time:{status:'unverified',value:'2026-01-01',source_text:null}}; "
            "const valid = module.validateAnalysis(structuredClone(base), '发布时间：2026-08-02'); "
            "let englishRejected = false; try { const bad = structuredClone(base); bad.feature_title='Automation'; "
            "module.validateAnalysis(bad, '发布时间：2026-08-02'); } catch { englishRejected = true; } "
            "let ungroundedTimeRejected = false; try { const bad = structuredClone(base); "
            "bad.publication_time={status:'verified',value:'2026-08-02T00:00:00Z',source_text:'页面未出现'}; "
            "module.validateAnalysis(bad, '发布时间：2026-08-02'); } catch { ungroundedTimeRejected = true; } "
            "return {value: valid.publication_time.value, englishRejected, ungroundedTimeRejected, hasQuotes:'quotes' in valid}; }"
        )
        self.assertIsNone(result["value"])
        self.assertTrue(result["englishRejected"])
        self.assertTrue(result["ungroundedTimeRejected"])
        self.assertFalse(result["hasQuotes"])

    def test_daily_guard_blocks_provider_call_and_analysis_failure_stays_nonfatal(self):
        result = self.run_module(
            "async (module) => { const calls=[]; globalThis.fetch=async (url, init={}) => { calls.push({url:String(url),method:init.method||'GET'}); "
            "if (String(url).endsWith('/rpc/reserve_source_capture_ai_budget')) return Response.json(false); "
            "throw new Error('provider must not be called'); }; "
            "const env={SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'secret',GEMINI_API_KEY:'gemini-secret'}; "
            "await module.enrichCandidateWithAnalysis(env,'candidate-id',{title:'Title',canonicalUrl:'https://example.com'},'Original one\\nOriginal two'); "
            "return calls; }"
        )
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["url"].endswith("/rpc/reserve_source_capture_ai_budget"))

        failure_result = self.run_module(
            "async (module) => { const calls=[]; globalThis.fetch=async (url) => { calls.push(String(url)); "
            "if (String(url).endsWith('/rpc/reserve_source_capture_ai_budget')) return Response.json(true); "
            "return new Response('quota details must stay private',{status:429}); }; "
            "await module.enrichCandidateWithAnalysis({SUPABASE_URL:'https://project.supabase.co',"
            "SUPABASE_SERVICE_ROLE_KEY:'secret',GEMINI_API_KEY:'gemini-secret'},'candidate-id',"
            "{title:'Title',canonicalUrl:'https://example.com'},'Original one\\nOriginal two'); return calls; }"
        )
        self.assertEqual(len(failure_result), 2)
        self.assertTrue(any("generativelanguage.googleapis.com" in call for call in failure_result))

    def test_analysis_unavailability_diagnostics_are_classified_and_secret_free(self):
        result = self.run_module(
            "async (module) => { const logs=[]; console.warn=(value)=>logs.push(value); "
            "await module.enrichCandidateWithAnalysis({},'candidate-id',{title:'Secret title',canonicalUrl:'https://example.com/?token=secret'},'secret source text'); "
            "globalThis.fetch=async(url)=>String(url).endsWith('/rpc/reserve_source_capture_ai_budget')?Response.json(true):new Response('private provider body',{status:429}); "
            "await module.enrichCandidateWithAnalysis({SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'service-secret',GEMINI_API_KEY:'gemini-secret'},"
            "'candidate-id',{title:'Secret title',canonicalUrl:'https://example.com/?token=secret'},'secret source text'); return logs.map(JSON.parse); }"
        )
        self.assertEqual(result[0]["reason"], "missing_model_config")
        self.assertEqual(result[1], {
            "event": "candidate_analysis_unavailable", "reason": "model_discovery_unavailable", "http_status": 429,
        })
        serialized = json.dumps(result)
        for secret in ["gemini-secret", "service-secret", "Secret title", "token=secret", "secret source text", "private provider body"]:
            self.assertNotIn(secret, serialized)

    def test_gemini_key_is_server_header_strict_json_and_success_updates_candidate_only(self):
        result = self.run_module(
            "async (module) => { const calls=[]; const analysis={feature_title:'数据库自动化',feature_summary:'新增数据库任务自动化能力。',conclusion:'结论',facts:['事实一','事实二'],"
            "inference:{label:'推断',text:'可能'},competitive_impact:{label:'竞争影响',text:'有限'},"
            "confidence:'high',publication_time:{status:'not_found',value:null,source_text:null}}; "
            "globalThis.fetch=async (url,init={})=>{ const headers=new Headers(init.headers); const body=init.body?JSON.parse(init.body):null; "
            "calls.push({url:String(url),method:init.method||'GET',key:headers.get('x-goog-api-key'),body}); "
            "if(String(url).endsWith('/rpc/reserve_source_capture_ai_budget')) return Response.json(true); "
            "if(String(url).endsWith('/v1beta/models')) return Response.json({models:[{name:'models/gemini-2.5-flash-lite',supportedGenerationMethods:['generateContent']}]}); "
            "if(String(url).includes(':generateContent')) return Response.json({candidates:[{content:{parts:[{text:JSON.stringify(analysis)}]}}]}); "
            "if((init.method||'GET')==='PATCH') return new Response(null,{status:204}); throw new Error('unexpected'); }; "
            "const env={SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'service-secret',GEMINI_API_KEY:'gemini-secret'}; "
            "await module.enrichCandidateWithAnalysis(env,'candidate-id',{title:'Title',canonicalUrl:'https://example.com'},'Original one\\nOriginal two'); return calls; }"
        )
        discovery = next(call for call in result if call["url"].endswith("/v1beta/models"))
        provider = next(call for call in result if ":generateContent" in call["url"])
        self.assertEqual(discovery["key"], "gemini-secret")
        self.assertIsNone(discovery["body"])
        self.assertNotIn("gemini-secret", provider["url"])
        self.assertEqual(provider["key"], "gemini-secret")
        self.assertEqual(provider["body"]["generationConfig"]["responseMimeType"], "application/json")
        self.assertIn("responseJsonSchema", provider["body"]["generationConfig"])
        patch_call = next(call for call in result if call["method"] == "PATCH")
        self.assertIn("/source_capture_candidates?", patch_call["url"])
        self.assertEqual(patch_call["body"]["analysis_status"], "available")
        self.assertEqual(patch_call["body"]["title"], "数据库自动化")
        self.assertEqual(patch_call["body"]["summary"], "新增数据库任务自动化能力。")
        self.assertEqual(patch_call["body"]["quoted_text"], "")
        self.assertEqual(patch_call["body"]["analysis_model"], "gemini-2.5-flash-lite")
        schema = provider["body"]["generationConfig"]["responseJsonSchema"]
        self.assertIn("feature_title", schema["required"])
        self.assertIn("feature_summary", schema["required"])
        self.assertNotIn("quotes", schema["required"])
        self.assertNotIn("quotes", schema["properties"])

    def test_flash_lite_model_selection_prefers_gemini_2_5(self):
        result = self.run_module(
            "(module) => module.selectGeminiFlashLiteModel(["
            "{name:'models/gemini-2.0-flash-lite-001',supportedGenerationMethods:['generateContent']},"
            "{name:'models/gemini-2.5-flash-lite',supportedGenerationMethods:['countTokens','generateContent']}])"
        )
        self.assertEqual(result, "gemini-2.5-flash-lite")

    def test_flash_lite_model_selection_uses_deterministic_stable_fallback(self):
        result = self.run_module(
            "(module) => [module.selectGeminiFlashLiteModel(["
            "{name:'models/gemini-2.0-flash-lite-002',supportedGenerationMethods:['generateContent']},"
            "{name:'models/gemini-2.0-flash-lite-001',supportedGenerationMethods:['generateContent']},"
            "{name:'models/gemini-2.5-flash-lite-preview-06-17',supportedGenerationMethods:['generateContent']}]),"
            "module.selectGeminiFlashLiteModel(["
            "{name:'models/gemini-2.0-flash-lite-001',supportedGenerationMethods:['generateContent']},"
            "{name:'models/gemini-2.0-flash-lite-002',supportedGenerationMethods:['generateContent']}])]"
        )
        self.assertEqual(result, ["gemini-2.0-flash-lite-001", "gemini-2.0-flash-lite-001"])

    def test_flash_lite_model_selection_rejects_non_flash_lite_or_unsupported_options(self):
        result = self.run_module(
            "(module) => module.selectGeminiFlashLiteModel(["
            "{name:'models/gemini-2.5-flash',supportedGenerationMethods:['generateContent']},"
            "{name:'models/gemini-2.5-flash-lite',supportedGenerationMethods:['countTokens']},"
            "{name:'models/gemini-2.5-flash-lite-preview-06-17',supportedGenerationMethods:['generateContent']}])"
        )
        self.assertIsNone(result)

    def test_model_discovery_unavailable_is_fixed_and_does_not_leak_model_list(self):
        result = self.run_module(
            "async (module) => { const logs=[]; const calls=[]; console.warn=(value)=>logs.push(value); "
            "globalThis.fetch=async(url,init={})=>{const value=String(url);calls.push({url:value,method:init.method||'GET',body:init.body||null});"
            "if(value.endsWith('/rpc/reserve_source_capture_ai_budget')) return Response.json(true);"
            "if(value.endsWith('/v1beta/models')) return Response.json({models:[{name:'models/private-pro-model',description:'private-list-secret',supportedGenerationMethods:['generateContent']}]});"
            "throw new Error('generateContent must not run')};"
            "await module.enrichCandidateWithAnalysis({SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'service-secret',GEMINI_API_KEY:'gemini-secret'},"
            "'candidate-id',{title:'Private title',canonicalUrl:'https://example.com/?secret=1'},'Private input');"
            "return {logs:logs.map(JSON.parse),calls}; }"
        )
        self.assertEqual(result["logs"], [{
            "event": "candidate_analysis_unavailable", "reason": "flash_lite_model_unavailable",
        }])
        self.assertEqual(len(result["calls"]), 2)
        serialized = json.dumps(result)
        for secret in ["private-list-secret", "private-pro-model", "gemini-secret", "service-secret", "Private title", "Private input"]:
            self.assertNotIn(secret, serialized)

    def test_gemini_generated_fields_must_use_simplified_chinese(self):
        source = WORKER.read_text(encoding="utf-8")
        self.assertIn("feature_title 必须是简洁的简体中文功能主题", source)
        self.assertIn("feature_summary 必须是该具体功能的简洁简体中文摘要", source)
        self.assertNotIn("原文引文保持页面原始语言", source)

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
        self.assertEqual(result[1]["methods"], "GET, POST, DELETE")
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
            "competitor_id: '55555555-5555-4555-8555-8555-555555555555', source_type: 'changelog', url: 'https://public.example/page'}]); "
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

    def test_snapshot_write_uses_unique_conflict_target_so_unchanged_fetches_succeed(self):
        source = WORKER.read_text(encoding="utf-8")
        self.assertIn("source_capture_snapshots?on_conflict=source_id%2Ccontent_hash", source)

    def test_unchanged_manual_capture_upserts_snapshot_and_does_not_queue_candidate(self):
        result = self.run_module(
            "async (module) => { const calls = []; globalThis.fetch = async (url, init = {}) => { "
            "const value = String(url); const method = init.method || 'GET'; const body = init.body ? JSON.parse(init.body) : null; calls.push({url:value,method,body}); "
            "if (value.endsWith('/auth/v1/user')) return Response.json({id: '22222222-2222-4222-8222-222222222222'}); "
            "if (value.includes('/competitor_sources?') && method === 'GET') return Response.json([{id:'11111111-1111-4111-8111-111111111111',workspace_id:'33333333-3333-4333-8333-333333333333',tab_id:'44444444-4444-4444-8444-444444444444',competitor_id:'55555555-5555-4555-8555-8555-555555555555',source_type:'changelog',url:'https://public.example/page'}]); "
            "if (value.includes('/workspace_members?')) return Response.json([{workspace_id:'33333333-3333-4333-8333-333333333333'}]); "
            "if (value.includes('/source_capture_runs?') && method === 'GET') return Response.json([]); "
            "if (value.endsWith('/rest/v1/source_capture_runs') && method === 'POST') return Response.json([body]); "
            "if (value.includes('/source_capture_snapshots?source_id=') && method === 'GET') return Response.json([{id:'previous-snapshot',content_hash:'09d568da57f518ee045d424dbf2cea47245f2a358cf58baa5efbde04ad1dc57c'}]); "
            "if (value === 'https://public.example/page') return new Response('<title>Release</title><main>New release</main>', {headers:{'content-type':'text/html'}}); "
            "if (value.includes('/rest/v1/source_capture_snapshots?on_conflict=source_id%2Ccontent_hash') && method === 'POST') return Response.json([]); "
            "if (value.includes('/source_capture_candidates') && method === 'POST') throw new Error('candidate must not be created'); "
            "if (method === 'PATCH') return new Response(null,{status:204}); throw new Error('unexpected request '+value); }; "
            "const env={SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'service-secret',SUPABASE_PUBLISHABLE_KEY:'public-key'}; const response=await module.default.fetch(new Request('https://worker.example/manual-capture',{method:'POST',headers:{Origin:'https://zacclover-competitor.pages.dev',Authorization:'Bearer user-jwt','Content-Type':'application/json'},body:JSON.stringify({sourceId:'11111111-1111-4111-8111-111111111111'})}),env,{}); return {status:response.status,body:await response.json(),calls}; }"
        )
        self.assertEqual(result["status"], 200)
        self.assertFalse(result["body"]["result"]["candidateQueued"])
        snapshot_insert = next(call for call in result["calls"] if "/rest/v1/source_capture_snapshots?on_conflict=source_id%2Ccontent_hash" in call["url"] and call["method"] == "POST")
        self.assertEqual(snapshot_insert["body"]["content_hash"], "09d568da57f518ee045d424dbf2cea47245f2a358cf58baa5efbde04ad1dc57c")

    def test_successful_manual_capture_reuses_review_pipeline_with_manual_trigger(self):
        result = self.run_module(
            "async (module) => { const calls = []; globalThis.fetch = async (url, init = {}) => { "
            "const value = String(url); const method = init.method || 'GET'; const body = init.body ? JSON.parse(init.body) : null; "
            "calls.push({url: value, method, body, auth: new Headers(init.headers).get('authorization')}); "
            "if (value.endsWith('/auth/v1/user')) return Response.json({id: '22222222-2222-4222-8222-222222222222'}); "
            "if (value.includes('/competitor_sources?') && method === 'GET') return Response.json([{id: '11111111-1111-4111-8111-111111111111', "
            "workspace_id: '33333333-3333-4333-8333-333333333333', tab_id: '44444444-4444-4444-8444-444444444444', "
            "competitor_id: '55555555-5555-4555-8555-8555-555555555555', source_type: 'changelog', url: 'https://public.example/page'}]); "
            "if (value.includes('/workspace_members?')) return Response.json([{workspace_id: '33333333-3333-4333-8333-333333333333'}]); "
            "if (value.includes('/source_capture_runs?') && method === 'GET') return Response.json([]); "
            "if (value.endsWith('/rest/v1/source_capture_runs') && method === 'POST') return Response.json([body]); "
            "if (value.includes('/source_capture_snapshots?') && method === 'GET') return Response.json([]); "
            "if (value === 'https://public.example/page') return new Response('<title>Releases</title><main><a href=\"/updates/one\">更新一</a><a href=\"/updates/two\">更新二</a></main>', {headers: {'content-type': 'text/html'}}); "
            "if (value === 'https://public.example/updates/one') return new Response('<title>功能更新</title><time datetime=\"2026-08-01T00:00:00Z\">2026-08-01</time><main>新增数据库自动化。</main>', {headers:{'content-type':'text/html'}}); "
            "if (value === 'https://public.example/updates/two') return new Response('<title>权限更新</title><time datetime=\"2026-08-02T00:00:00Z\">2026-08-02</time><main>新增权限控制。</main>', {headers:{'content-type':'text/html'}}); "
            "if (value.includes('/source_capture_snapshots?on_conflict=') && method === 'POST') return Response.json([body]); "
            "if (value.includes('/source_capture_candidates?') && method === 'GET') return Response.json([]); "
            "if (value.includes('/source_capture_candidates?on_conflict=') && method === 'POST') return Response.json([body]); "
            "if (method === 'PATCH') return new Response(null, {status: 204}); throw new Error('unexpected request ' + value); }; "
            "const env = {SUPABASE_URL: 'https://project.supabase.co', SUPABASE_SERVICE_ROLE_KEY: 'service-secret', "
            "SUPABASE_PUBLISHABLE_KEY: 'public-key'}; const response = await module.default.fetch(new Request('https://worker.example/manual-capture', {method: 'POST', "
            "headers: {Origin: 'https://zacclover-competitor.pages.dev', Authorization: 'Bearer user-jwt', 'Content-Type': 'application/json'}, "
            "body: JSON.stringify({sourceId: '11111111-1111-4111-8111-111111111111', observationWindow:{start:'2026-07-01T00:00:00Z',end:'2026-08-03T12:00:00Z'}})}), env, {}); "
            "return {status: response.status, body: await response.json(), calls}; }"
        )
        self.assertEqual(result["status"], 200)
        self.assertTrue(result["body"]["ok"])
        self.assertTrue(result["body"]["result"]["candidateQueued"])
        candidate_inserts = [call for call in result["calls"] if "/source_capture_candidates?on_conflict=" in call["url"] and call["method"] == "POST"]
        self.assertEqual(result["body"]["result"]["candidateCount"], 2)
        self.assertEqual(len(candidate_inserts), 2)
        self.assertEqual([call["body"]["title"] for call in candidate_inserts], ["待分析功能更新", "待分析功能更新"])
        self.assertTrue(all(call["body"]["summary"] == "发现一项发布时间符合观察窗口的功能更新，具体内容请查看来源页面。" for call in candidate_inserts))
        self.assertTrue(all(call["body"]["quoted_text"] == "" for call in candidate_inserts))
        self.assertTrue(all(len(call["body"]["selected_entries"]) == 1 for call in candidate_inserts))
        self.assertEqual([call["body"]["source_url"] for call in candidate_inserts], [
            "https://public.example/updates/one", "https://public.example/updates/two",
        ])
        run_insert = next(call for call in result["calls"] if call["url"].endswith("/rest/v1/source_capture_runs") and call["method"] == "POST")
        self.assertEqual(run_insert["body"]["trigger_type"], "manual")
        service_calls = [call for call in result["calls"] if "/rest/v1/" in call["url"]]
        self.assertTrue(all(call["auth"] == "Bearer service-secret" for call in service_calls))

    def test_manual_capture_retries_existing_unavailable_candidate_without_duplicate(self):
        result = self.run_module(
            "async (module) => { const calls=[]; const analysis={feature_title:'数据库自动化',feature_summary:'新增数据库任务自动化能力。',conclusion:'结论',facts:['事实一','事实二'],inference:{label:'推断',text:'可能'},competitive_impact:{label:'竞争影响',text:'有限'},confidence:'high',publication_time:{status:'not_found',value:null,source_text:null}}; "
            "globalThis.fetch=async(url,init={})=>{const value=String(url),method=init.method||'GET',body=init.body?JSON.parse(init.body):null;calls.push({url:value,method,body});"
            "if(value.endsWith('/auth/v1/user'))return Response.json({id:'22222222-2222-4222-8222-222222222222'});"
            "if(value.includes('/competitor_sources?'))return Response.json([{id:'11111111-1111-4111-8111-111111111111',workspace_id:'33333333-3333-4333-8333-333333333333',tab_id:'44444444-4444-4444-8444-444444444444',competitor_id:'55555555-5555-4555-8555-555555555555',source_type:'changelog',url:'https://public.example/changelog'}]);"
            "if(value.includes('/workspace_members?'))return Response.json([{workspace_id:'33333333-3333-4333-8333-333333333333'}]);"
            "if(value.includes('/source_capture_runs?')&&method==='GET')return Response.json([]);if(value.endsWith('/rest/v1/source_capture_runs')&&method==='POST')return Response.json([body]);"
            "if(value.includes('/source_capture_snapshots?')&&method==='GET')return Response.json([]);"
            "if(value==='https://public.example/changelog')return new Response('<main><a href=\"/changelog/one\">one</a></main>',{headers:{'content-type':'text/html'}});"
            "if(value==='https://public.example/changelog/one')return new Response('<title>Feature</title><time datetime=\"2026-08-01T00:00:00Z\">2026-08-01</time><main>Original feature text</main>',{headers:{'content-type':'text/html'}});"
            "if(value.includes('/source_capture_snapshots?on_conflict=')&&method==='POST')return Response.json([body]);"
            "if(value.includes('/source_capture_candidates?')&&method==='GET')return Response.json([{id:'existing-candidate',workspace_id:'33333333-3333-4333-8333-333333333333',status:'pending',analysis_status:'unavailable'}]);"
            "if(value.includes('/candidate_attachments?')&&method==='GET')return Response.json([]);"
            "if(value.endsWith('/rpc/reserve_source_capture_ai_budget'))return Response.json(true);"
            "if(value.endsWith('/v1beta/models'))return Response.json({models:[{name:'models/gemini-2.5-flash-lite',supportedGenerationMethods:['generateContent']}]});"
            "if(value.includes(':generateContent'))return Response.json({candidates:[{content:{parts:[{text:JSON.stringify(analysis)}]}}]});"
            "if(method==='PATCH')return new Response(null,{status:204});if(method==='POST'&&value.includes('/source_capture_candidates'))throw new Error('duplicate candidate');throw new Error('unexpected '+value)};"
            "const env={SUPABASE_URL:'https://project.supabase.co',SUPABASE_SERVICE_ROLE_KEY:'service-secret',SUPABASE_PUBLISHABLE_KEY:'public-key',GEMINI_API_KEY:'gemini-secret'};"
            "const response=await module.default.fetch(new Request('https://worker.example/manual-capture',{method:'POST',headers:{Authorization:'Bearer jwt','Content-Type':'application/json'},body:JSON.stringify({sourceId:'11111111-1111-4111-8111-111111111111',observationWindow:{start:'2026-07-01T00:00:00Z',end:'2026-08-03T12:00:00Z'}})}),env,{});return {status:response.status,body:await response.json(),calls};}"
        )
        self.assertEqual(result["status"], 200)
        self.assertEqual(result["body"]["result"]["candidateCount"], 0)
        self.assertFalse(any(call["method"] == "POST" and "/source_capture_candidates" in call["url"] for call in result["calls"]))
        lookup = next(call for call in result["calls"] if "/source_capture_candidates?" in call["url"] and call["method"] == "GET")
        self.assertIn("workspace_id=eq.33333333-3333-4333-8333-333333333333", lookup["url"])
        self.assertIn("source_id=eq.11111111-1111-4111-8111-111111111111", lookup["url"])
        patch = next(call for call in result["calls"] if call["method"] == "PATCH" and "source_capture_candidates?id=eq.existing-candidate" in call["url"])
        self.assertEqual(patch["body"]["analysis_status"], "available")

    def test_manual_capture_skips_analysis_retry_for_available_candidate(self):
        result = self.run_module(
            "(module) => ({unavailable:module.shouldRetryExistingCandidate('manual',{status:'pending',analysis_status:'unavailable'}),"
            "available:module.shouldRetryExistingCandidate('manual',{status:'pending',analysis_status:'available'}),"
            "scheduled:module.shouldRetryExistingCandidate('scheduled',{status:'pending',analysis_status:'unavailable'}),"
            "reviewed:module.shouldRetryExistingCandidate('manual',{status:'accepted',analysis_status:'unavailable'})})"
        )
        self.assertEqual(result, {"unavailable": True, "available": False, "scheduled": False, "reviewed": False})


if __name__ == "__main__":
    unittest.main()
