-- ============================================================
-- 仅供受控 Worker 的服务角色访问采集管线。
-- 浏览器继续只使用 authenticated + RLS；不得向 anon/authenticated 扩权。
-- ============================================================
grant usage on schema public to service_role;

grant select, insert, update on table public.competitor_sources to service_role;
grant select on table public.workspace_members to service_role;
grant select, insert, update on table public.source_capture_runs to service_role;
grant select, insert on table public.source_capture_snapshots to service_role;
grant select, insert on table public.source_capture_candidates to service_role;
