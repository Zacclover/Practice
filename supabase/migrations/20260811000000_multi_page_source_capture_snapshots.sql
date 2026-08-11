-- 一次来源抓取会保存入口页及其同源一层子页面；每页在当前 run 内独立可追溯。
-- Candidate 的 (source_id, content_hash) 去重不变，仍阻止本地总结重复创建待审核 Candidate。
alter table public.source_capture_snapshots
  drop constraint if exists source_capture_snapshots_source_id_content_hash_key;

alter table public.source_capture_snapshots
  add constraint source_capture_snapshots_run_id_canonical_url_content_hash_key
  unique (run_id, canonical_url, content_hash);

create index if not exists source_capture_snapshots_run_history_idx
  on public.source_capture_snapshots (run_id, fetched_at desc);
