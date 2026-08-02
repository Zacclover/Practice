-- ============================================================
-- 来源采集浏览器访问授权修复：RLS 已限定为同工作区成员，
-- 仍须授予 authenticated 基础表权限，PostgREST 才能进入 RLS 策略。
-- 不改变 service role 权限，也不放宽行级访问范围。
-- ============================================================
grant select, insert, update, delete on table public.competitor_sources to authenticated;
grant select, insert, update, delete on table public.source_capture_runs to authenticated;
grant select, insert, update, delete on table public.source_capture_snapshots to authenticated;
grant select, insert, update, delete on table public.source_capture_candidates to authenticated;
