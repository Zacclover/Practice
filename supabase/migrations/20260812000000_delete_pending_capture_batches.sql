-- ============================================================
-- 待审核抓取批次删除：仅允许服务端删除尚未采纳为正式证据的整批 run。
-- 若批次包含已采纳 Candidate，Worker 必须拒绝删除，保护正式证据链。
-- ============================================================
grant select, delete on table public.source_capture_runs to service_role;
grant select, delete on table public.source_capture_snapshots to service_role;
grant select, delete on table public.source_capture_snapshot_images to service_role;
grant select, delete on table public.candidate_attachments to service_role;
