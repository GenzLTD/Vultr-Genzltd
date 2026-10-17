-- ============================================================
-- gfcc 库 · memory 端口（recall）存储结构 v1
--
-- 契约真源：GenzLTD/gfcc@3dcb084 contracts/memory.v1.json（1.3.0）
--   store_slot.link = actor_sub
--   optional_adapters 含 gfcc："pgvector 库 gfcc。与 cortex-mcp 只通过 actor_sub 关联。"
--   recall = scope memory.read / min_role observer
--
-- 本文件只建 recall 需要的结构：
--   * 不装 vector 扩展，不做向量检索 —— 第一刀按 actor_sub + library 精确查询
--   * 不建 remember / observe / supersede 的写入面（put/supersede 先不挂入口）
--
-- 幂等：预发库是「已经 initdb 的卷」，docker-entrypoint-initdb.d 不会再跑，
--       所以由流水线每次显式执行本文件；重复执行不报错、不改已有数据。
-- ============================================================

CREATE TABLE IF NOT EXISTS public.memory_record (
    id            uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- 七库：与契约 library_enum 一致
    library       text        NOT NULL
                              CHECK (library IN ('issue', 'action', 'event', 'methodology_value',
                                                 'person', 'org', 'resource')),
    -- 仅 methodology_value 内有意义：method = how / value = why
    record_type   text        CHECK (record_type IN ('note', 'method', 'value')),
    circle_id     text,
    body          text        NOT NULL CHECK (length(btrim(body)) > 0),
    -- 相关七库记录 id，契约里「被引用」是「记得住」的度量
    refs          text[]      NOT NULL DEFAULT '{}',
    observed_at   timestamptz NOT NULL,
    observed_by   text        NOT NULL DEFAULT 'human'
                              CHECK (observed_by IN ('human', 'ai')),
    -- observed_by=ai 时必填：哪个模型/适配器给出的观察
    ai_source     text,
    -- 历史不删：改写走 supersede，只置位本列
    superseded_at timestamptz,
    -- 原始 claims.sub（不是 sha256）；与 X-User-Id 并存，两者不互替
    actor_sub     text        NOT NULL CHECK (length(btrim(actor_sub)) > 0),
    created_at    timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT memory_record_ai_source_required
        CHECK (observed_by <> 'ai' OR ai_source IS NOT NULL)
);

COMMENT ON TABLE public.memory_record IS
    'GFCC memory 端口记录（契约 memory.v1 1.3.0）。actor_sub = 原始 claims.sub；与 cortex-mcp 仅经 actor_sub 关联。';

-- recall 主路径：按人 + 时间倒序
CREATE INDEX IF NOT EXISTS memory_record_actor_observed_idx
    ON public.memory_record (actor_sub, observed_at DESC);

-- recall 过滤：按人 + 库
CREATE INDEX IF NOT EXISTS memory_record_actor_library_observed_idx
    ON public.memory_record (actor_sub, library, observed_at DESC);

-- 围坐（circle）范围读取
CREATE INDEX IF NOT EXISTS memory_record_circle_observed_idx
    ON public.memory_record (circle_id, observed_at DESC)
    WHERE circle_id IS NOT NULL;
