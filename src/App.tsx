import {
  ArrowDown,
  ArrowLeft,
  CalendarDays,
  ChevronRight,
  Clock3,
  EyeOff,
  Inbox,
  MapPin,
  MessagesSquare,
  Search,
  ScanSearch,
  Settings,
  ShieldCheck,
  X,
} from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useState } from "react";

const MemoryWorld3D = lazy(() =>
  import("./MemoryWorld3D").then((module) => ({ default: module.MemoryWorld3D })),
);

type MemoryChapter = {
  id: string;
  memoryId: string;
  revision: number;
  proactiveConsent: boolean;
  crossSessionConsent: boolean;
  year: string;
  railLabel: string;
  period: string;
  title: string;
  summary: string;
  meaning: string;
  state: "recent" | "influence" | "open" | "settled";
  side: "left" | "right";
  y: number;
  memories: string[];
  sources: string[];
  tags: string[];
};

type MemoryDto = {
  id: string;
  kind: string;
  summary: string;
  epistemic_status: string;
  speech_act: string;
  time: Record<string, unknown>;
  sensitivity: string;
  intention_state: string | null;
  outcome: string | null;
  persist_consent: boolean;
  cross_session_consent: boolean;
  proactive_consent: boolean;
  revision: number;
  source_ids: string[];
  sources: Array<{
    id: string;
    conversation_id: string;
    turn_id: string;
    observed_at: string;
    timezone: string;
    role: string;
    excerpt: string;
  }>;
};

type CandidateDto = {
  id: string;
  observation_id: string;
  kind: string;
  summary: string;
  speech_act: string;
  status: string;
  confidence: number;
  time: Record<string, unknown>;
  sensitivity: string;
};

type StatusDto = {
  user_id: string;
  timezone: string;
  cross_session_internal_use: boolean;
  current_memories: number;
  pending_candidates: number;
};

type MemoryExplanationDto = {
  memory_id: string;
  source_ids: string[];
  events: Array<{ event_type: string; created_at: string; payload: Record<string, unknown> }>;
  governance_traces: Array<{
    id: string;
    reason_codes: string[];
    input_summary: string;
    created_at: string;
  }>;
};

type RecallPreviewDto = {
  package_id: string;
  purpose: string;
  issued_at: string;
  expires_at: string;
  items: Array<{
    memory_id: string;
    category: "allowed_to_use" | "internal_only" | "confirm_first";
    summary: string | null;
    display_summary: string;
    guidance: string | null;
    reason_codes: string[];
  }>;
  adapter_payload: {
    allowed_memories: Array<{ memory_id: string; summary: string }>;
    response_guidance: string[];
    confirmation_prompts: string[];
    response_constraints: string[];
  };
};

type ConversationSummaryDto = {
  conversation_id: string;
  source_kind: "adapter" | "import" | "observation" | "mixed";
  first_activity_at: string | null;
  last_activity_at: string | null;
  observation_count: number;
  candidate_count: number;
  pending_candidate_count: number;
  memory_count: number;
  adapter_event_count: number;
};

type ConversationDetailDto = ConversationSummaryDto & {
  observations: Array<{
    id: string;
    turn_id: string;
    observed_at: string;
    timezone: string;
    role: string;
    excerpt: string;
    speech_act: string;
    candidates: Array<{
      id: string;
      kind: string;
      summary: string;
      status: string;
      sensitivity: string;
    }>;
    memories: Array<{
      id: string;
      kind: string;
      summary: string;
      epistemic_status: string;
      current: boolean;
      revision: number;
    }>;
  }>;
  adapter_events: Array<{ turn_id: string; event_type: string; occurred_at: string }>;
};

type SceneState = {
  progress: number;
  activeIndex: number;
};

const stateCopy = {
  recent: "最近发生",
  influence: "仍在影响",
  open: "尚未结束",
  settled: "已经沉淀",
};

const API_BASE = import.meta.env.VITE_HTC_API_BASE ?? "/api";

async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...(options?.headers ?? {}) },
    });
  } catch {
    throw new Error("无法连接本地 HTC Core");
  }
  const payload = (await response.json().catch(() => ({}))) as {
    data?: T;
    error?: { message?: string };
  };
  if (!response.ok || !payload.data) {
    throw new Error(payload.error?.message ?? `Workbench API ${response.status}`);
  }
  return payload.data;
}

function chapterFromMemory(memory: MemoryDto, index: number): MemoryChapter {
  const dateValue = ["occurred_at", "start_at", "expected_at", "anchor_time"]
    .map((key) => memory.time[key])
    .find((value) => typeof value === "string") as string | undefined;
  const date = dateValue ? new Date(dateValue) : null;
  const validDate = date && !Number.isNaN(date.getTime()) ? date : null;
  const year = validDate ? String(validDate.getFullYear()) : "未定";
  const railLabel = validDate
    ? new Intl.DateTimeFormat("zh-CN", { month: "short", day: "numeric", timeZone: "Asia/Shanghai" }).format(validDate)
    : "时间未定";
  const period = validDate
    ? new Intl.DateTimeFormat("zh-CN", { year: "numeric", month: "long", day: "numeric", timeZone: "Asia/Shanghai" }).format(validDate)
    : "时间尚未确定";
  const state: MemoryChapter["state"] = memory.intention_state === "planned"
    ? "open"
    : memory.outcome === "unknown"
      ? "influence"
      : memory.epistemic_status === "current"
        ? "recent"
        : "settled";
  const stateMeaning = memory.proactive_consent
    ? "这条记忆已经由 HTC Core 治理，可以由你决定它如何参与未来的对话。"
    : "这条记忆仍然保存着，但已关闭主动提及。"
  return {
    id: memory.id,
    memoryId: memory.id,
    revision: memory.revision,
    proactiveConsent: memory.proactive_consent,
    crossSessionConsent: memory.cross_session_consent,
    year,
    railLabel,
    period,
    title: memory.kind,
    summary: memory.summary,
    meaning: stateMeaning,
    state,
    side: index % 2 === 0 ? "left" : "right",
    y: 470 + index * 650,
    memories: [memory.summary],
    sources: memory.sources.length
      ? memory.sources.map((source) => `${formatLocalTime(source.observed_at)} · ${source.excerpt}`)
      : memory.source_ids,
    tags: [memory.kind, memory.sensitivity, memory.proactive_consent ? "允许主动提及" : "不主动提"],
  };
}

export function App() {
  const [scene, setScene] = useState<SceneState>({
    progress: 0,
    activeIndex: 0,
  });
  const [selected, setSelected] = useState<MemoryChapter | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [memories, setMemories] = useState<MemoryDto[]>([]);
  const [candidates, setCandidates] = useState<CandidateDto[]>([]);
  const [candidateOpen, setCandidateOpen] = useState(false);
  const [recallOpen, setRecallOpen] = useState(false);
  const [conversationsOpen, setConversationsOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [status, setStatus] = useState<StatusDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [apiError, setApiError] = useState<string | null>(null);
  const [operationError, setOperationError] = useState<string | null>(null);
  const chapters = useMemo(
    () => memories.map((memory, index) => chapterFromMemory(memory, index)).reverse(),
    [memories],
  );
  const chapterProgress = useMemo(
    () => chapters.map((_, index) => (index + 1) / (chapters.length + 1)),
    [chapters.length],
  );
  const activeChapter = chapters[scene.activeIndex] ?? chapters[0];
  const currentDateLabel = useMemo(
    () =>
      new Intl.DateTimeFormat("zh-CN", {
        year: "numeric",
        month: "long",
        day: "numeric",
        timeZone: "Asia/Shanghai",
      }).format(new Date()),
    [],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    Promise.all([
      apiRequest<StatusDto>("/status"),
      apiRequest<{ memories: MemoryDto[] }>("/memories"),
      apiRequest<{ candidates: CandidateDto[] }>("/candidates?status=pending"),
    ])
      .then(([statusPayload, memoryPayload, candidatePayload]) => {
        if (cancelled) return;
        setStatus(statusPayload);
        setMemories(memoryPayload.memories);
        setCandidates(candidatePayload.candidates);
        setApiError(null);
      })
      .catch((error: unknown) => {
        if (!cancelled) setApiError(error instanceof Error ? error.message : "无法连接 HTC Core");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const maxScroll = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
        const progress = Math.min(1, Math.max(0, window.scrollY / maxScroll));
        const markers = chapterProgress.length ? chapterProgress : [0];
        const activeIndex = markers.reduce(
          (closest, marker, index) =>
            Math.abs(marker - progress) < Math.abs(markers[closest] - progress)
              ? index
              : closest,
          0,
        );
        setScene({ progress, activeIndex });
      });
    };
    update();
    window.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [chapterProgress]);

  useEffect(() => {
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setSelected(null);
        setSearchOpen(false);
        setCandidateOpen(false);
        setRecallOpen(false);
        setConversationsOpen(false);
        setSettingsOpen(false);
      }
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);

  const searchResults = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return chapters;
    return chapters.filter((chapter) =>
      [chapter.title, chapter.summary, chapter.period, chapter.year, ...chapter.tags]
        .join(" ")
        .toLowerCase()
        .includes(normalized),
    );
  }, [query]);

  async function refreshData() {
    const [statusPayload, memoryPayload, candidatePayload] = await Promise.all([
      apiRequest<StatusDto>("/status"),
      apiRequest<{ memories: MemoryDto[] }>("/memories"),
      apiRequest<{ candidates: CandidateDto[] }>("/candidates?status=pending"),
    ]);
    setStatus(statusPayload);
    setMemories(memoryPayload.memories);
    setCandidates(candidatePayload.candidates);
    setApiError(null);
  }

  function travelTo(index: number) {
    const maxScroll = document.documentElement.scrollHeight - window.innerHeight;
    window.scrollTo({ top: maxScroll * (chapterProgress[index] ?? 0), behavior: "smooth" });
    setSearchOpen(false);
  }

  async function suppressMemory(chapter: MemoryChapter) {
    await runOperation(async () => {
      await apiRequest(`/memories/${encodeURIComponent(chapter.memoryId)}/suppress`, {
        method: "POST",
        body: JSON.stringify({ expected_revision: chapter.revision }),
      });
      await refreshData();
      setSelected(null);
    });
  }

  async function reviseMemory(chapter: MemoryChapter, summary: string) {
    await runOperation(async () => {
      await apiRequest(`/memories/${encodeURIComponent(chapter.memoryId)}/revise`, {
        method: "POST",
        body: JSON.stringify({
          action: "correct",
          expected_revision: chapter.revision,
          summary,
        }),
      });
      await refreshData();
      setSelected(null);
    });
  }

  async function deleteMemory(chapter: MemoryChapter) {
    if (!window.confirm("从当前记忆中撤回这条内容？")) return;
    await runOperation(async () => {
      await apiRequest(`/memories/${encodeURIComponent(chapter.memoryId)}/delete`, {
        method: "POST",
        body: JSON.stringify({ expected_revision: chapter.revision }),
      });
      await refreshData();
      setSelected(null);
    });
  }

  async function decideCandidate(candidate: CandidateDto, decision: "accept" | "reject") {
    await runOperation(async () => {
      await apiRequest(`/candidates/${encodeURIComponent(candidate.id)}/decide`, {
        method: "POST",
        body: JSON.stringify({ decision }),
      });
      await refreshData();
    });
  }

  async function mergeCandidate(
    candidate: CandidateDto,
    memoryId: string,
    expectedRevision: number,
    summary: string,
  ) {
    await runOperation(async () => {
      await apiRequest(`/candidates/${encodeURIComponent(candidate.id)}/decide`, {
        method: "POST",
        body: JSON.stringify({
          decision: "accept",
          merge_into_memory_id: memoryId,
          expected_memory_revision: expectedRevision,
          summary,
        }),
      });
      await refreshData();
    });
  }

  async function updatePolicy(enabled: boolean) {
    await runOperation(async () => {
      await apiRequest("/policy", {
        method: "POST",
        body: JSON.stringify({ cross_session_internal_use: enabled }),
      });
      await refreshData();
    });
  }

  async function runOperation(operation: () => Promise<void>) {
    setOperationError(null);
    try {
      await operation();
    } catch (error) {
      setOperationError(error instanceof Error ? error.message : "操作没有完成");
    }
  }

  return (
    <main className="memory-timeline">
      <header className="timeline-toolbar">
        <button className="wordmark" onClick={() => travelTo(chapters.length - 1)} type="button" aria-label="回到现在">
          <span>HTC</span>
          <strong>Memory Timeline</strong>
        </button>
        <div className="timeline-actions">
          <button className="icon-button" onClick={() => setSearchOpen((open) => !open)} type="button" aria-label="搜索和跳转">
            <Search size={18} />
          </button>
          <button
            className="icon-button badge-button"
            onClick={() => setCandidateOpen(true)}
            type="button"
            aria-label={`待确认记忆，${candidates.length}条`}
          >
            <Inbox size={18} />
            {candidates.length ? <span>{candidates.length}</span> : null}
          </button>
          <button className="icon-button" onClick={() => setRecallOpen(true)} type="button" aria-label="召回预览">
            <ScanSearch size={18} />
          </button>
          <button className="icon-button" onClick={() => setConversationsOpen(true)} type="button" aria-label="来源会话">
            <MessagesSquare size={18} />
          </button>
          <button className="icon-button" onClick={() => setSettingsOpen(true)} type="button" aria-label="记忆设置">
            <Settings size={18} />
          </button>
        </div>
      </header>

      {loading ? <div className="api-status">正在连接本地 HTC Core…</div> : null}
      {apiError ? <div className="api-status error">{apiError} · 请先启动 `htc-workbench-api`</div> : null}
      {operationError ? <div className="api-status error">{operationError}</div> : null}

      {searchOpen ? (
        <section className="timeline-search" aria-label="搜索记忆">
          <div className="search-field">
            <Search size={18} />
            <input
              autoFocus
              onChange={(event) => setQuery(event.target.value)}
              placeholder="搜索人物、地点、事情或年份"
              value={query}
            />
            <button onClick={() => setSearchOpen(false)} type="button" aria-label="关闭搜索"><X size={18} /></button>
          </div>
          <div className="search-results">
            {searchResults.map((chapter) => {
              const index = chapters.findIndex((item) => item.id === chapter.id);
              return (
                <button key={chapter.id} onClick={() => travelTo(index)} type="button">
                  <span>{chapter.period}</span>
                  <strong>{chapter.title}</strong>
                  <ChevronRight size={16} />
                </button>
              );
            })}
            {searchResults.length === 0 ? <p>没有找到相符的记忆章节。</p> : null}
          </div>
        </section>
      ) : null}

      <section className="timeline-scroll" aria-label="从过去走向现在的记忆时间线">
        <div className="timeline-viewport">
          <div className="atmosphere">
            <Suspense fallback={<div className="scene-loading">记忆世界正在显影…</div>}>
              <MemoryWorld3D progress={scene.progress} activeChapter={scene.activeIndex} />
            </Suspense>
          </div>

          <section className={`present-summary ${scene.progress < 0.9 ? "receded" : ""}`}>
            <p className="present-time">{currentDateLabel} · 本地记忆</p>
            <h1>此刻的你，仍在向前。</h1>
            <div className="present-questions">
              <p><span>已治理记忆</span>{memories.length} 条 · 来自同一个人的多段经历。</p>
              <p><span>待你确认</span>{candidates.length} 条候选，不会自动成为记忆。</p>
              <p><span>控制权</span>所有主动提及、修改和撤回都由你决定。</p>
            </div>
            <div className="scroll-cue"><Clock3 size={16} /><span>你从过去走到了此刻</span></div>
          </section>

          <div className={`journey-start ${scene.progress > 0.08 ? "receded" : ""}`} aria-hidden="true">
            <ArrowDown size={16} />
            <span>从这里，走向现在</span>
          </div>

          {activeChapter ? <button
            className={`active-chapter ${activeChapter.side} ${scene.progress > 0.925 ? "at-present" : ""}`}
            onClick={() => setSelected(activeChapter)}
            type="button"
          >
            <span className="chapter-rule" />
            <span className="chapter-meta">
              {activeChapter.period}
              <b>{stateCopy[activeChapter.state]}</b>
            </span>
            <strong>{activeChapter.title}</strong>
            <span className="chapter-summary">{activeChapter.summary}</span>
            <span className="chapter-open">打开这一章 <ChevronRight size={15} /></span>
          </button> : <div className="empty-timeline">本地 HTC Core 中还没有已治理记忆。</div>}

          <div className="chapter-neighbors" aria-label="相邻记忆章节">
            {[-1, 1].map((offset) => {
              const index = scene.activeIndex + offset;
              const chapter = chapters[index];
              if (!chapter || scene.progress > 0.925) return null;
              return (
                <button
                  className={`chapter-neighbor ${chapter.side} ${offset < 0 ? "previous" : "next"}`}
                  key={chapter.id}
                  onClick={() => travelTo(index)}
                  type="button"
                >
                  <span>{chapter.period}</span>
                  <strong>{chapter.title}</strong>
                </button>
              );
            })}
          </div>

          <nav className="year-rail" aria-label="按年份跳转">
            {chapters.map((chapter, index) => (
              <button
                className={scene.activeIndex === index ? "active" : ""}
                key={chapter.id}
                onClick={() => travelTo(index)}
                type="button"
                aria-label={`跳到${chapter.period}`}
              >
                <span />
                {chapter.railLabel}
              </button>
            ))}
          </nav>
        </div>
      </section>

      {candidateOpen ? (
        <CandidateInbox
          candidates={candidates}
          memories={memories}
          onClose={() => setCandidateOpen(false)}
          onDecide={decideCandidate}
          onMerge={mergeCandidate}
        />
      ) : null}
      {settingsOpen ? (
        <SettingsDrawer
          status={status}
          onClose={() => setSettingsOpen(false)}
          onPolicyChange={updatePolicy}
        />
      ) : null}
      {recallOpen ? <RecallPreviewDrawer status={status} onClose={() => setRecallOpen(false)} /> : null}
      {conversationsOpen ? (
        <ConversationsDrawer
          onClose={() => setConversationsOpen(false)}
          onOpenMemory={(memoryId) => {
            const chapter = chapters.find((item) => item.memoryId === memoryId);
            if (chapter) {
              setConversationsOpen(false);
              setSelected(chapter);
            }
          }}
        />
      ) : null}
      {selected ? (
        <ChapterDrawer
          chapter={selected}
          onClose={() => setSelected(null)}
          onDelete={deleteMemory}
          onRevise={reviseMemory}
          onSuppress={suppressMemory}
        />
      ) : null}
    </main>
  );
}

function CandidateInbox({
  candidates,
  memories,
  onClose,
  onDecide,
  onMerge,
}: {
  candidates: CandidateDto[];
  memories: MemoryDto[];
  onClose: () => void;
  onDecide: (candidate: CandidateDto, decision: "accept" | "reject") => Promise<void>;
  onMerge: (candidate: CandidateDto, memoryId: string, expectedRevision: number, summary: string) => Promise<void>;
}) {
  return (
    <>
      <button className="drawer-backdrop" onClick={onClose} type="button" aria-label="关闭待确认记忆" />
      <aside className="chapter-drawer" aria-label="待确认记忆">
        <header>
          <div><p>Candidate Inbox</p><h2>等待你确认</h2></div>
          <button className="icon-button drawer-close" onClick={onClose} type="button" aria-label="关闭"><X size={20} /></button>
        </header>
        {candidates.length === 0 ? <p className="drawer-lead">目前没有待确认候选。</p> : candidates.map((candidate) => (
          <CandidateCard
            candidate={candidate}
            key={candidate.id}
            memories={memories}
            onDecide={onDecide}
            onMerge={onMerge}
          />
        ))}
      </aside>
    </>
  );
}

function CandidateCard({
  candidate,
  memories,
  onDecide,
  onMerge,
}: {
  candidate: CandidateDto;
  memories: MemoryDto[];
  onDecide: (candidate: CandidateDto, decision: "accept" | "reject") => Promise<void>;
  onMerge: (candidate: CandidateDto, memoryId: string, expectedRevision: number, summary: string) => Promise<void>;
}) {
  const [mergeOpen, setMergeOpen] = useState(false);
  const [target, setTarget] = useState(memories[0]?.id ?? "");
  const [summary, setSummary] = useState(memories[0]?.summary ?? "");
  const [busy, setBusy] = useState(false);

  async function decide(decision: "accept" | "reject") {
    setBusy(true);
    try {
      await onDecide(candidate, decision);
    } finally {
      setBusy(false);
    }
  }

  async function merge() {
    if (!target || !summary.trim()) return;
    const targetMemory = memories.find((memory) => memory.id === target);
    if (!targetMemory) return;
    setBusy(true);
    try {
      await onMerge(candidate, target, targetMemory.revision, summary.trim());
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="candidate-card">
      <p>{candidate.kind} · {Math.round(candidate.confidence * 100)}% · {candidate.sensitivity}</p>
      <strong>{candidate.summary}</strong>
      {mergeOpen ? (
        <div className="candidate-merge">
          <label>
            合并到
            <select
              disabled={busy}
              onChange={(event) => {
                const memory = memories.find((item) => item.id === event.target.value);
                setTarget(event.target.value);
                setSummary(memory?.summary ?? "");
              }}
              value={target}
            >
              {memories.map((memory) => <option key={memory.id} value={memory.id}>{memory.kind} · {memory.summary}</option>)}
            </select>
          </label>
          <label>
            合并后的记忆（默认保留原摘要）
            <textarea disabled={busy} onChange={(event) => setSummary(event.target.value)} value={summary} />
          </label>
          <div>
            <button className="quiet-action" disabled={busy} onClick={() => setMergeOpen(false)} type="button">取消</button>
            <button className="quiet-action primary" disabled={busy || !target || !summary.trim()} onClick={() => void merge()} type="button">确认合并</button>
          </div>
        </div>
      ) : (
        <div>
          <button className="quiet-action" disabled={busy} onClick={() => void decide("reject")} type="button">拒绝</button>
          {memories.length ? <button className="quiet-action" disabled={busy} onClick={() => setMergeOpen(true)} type="button">合并到已有记忆</button> : null}
          <button className="quiet-action primary" disabled={busy} onClick={() => void decide("accept")} type="button">接受为新记忆</button>
        </div>
      )}
    </article>
  );
}

const conversationKindCopy = {
  adapter: "Adapter 会话",
  import: "导入来源",
  observation: "本地 Observation",
  mixed: "Adapter + Observation",
};

function ConversationsDrawer({
  onClose,
  onOpenMemory,
}: {
  onClose: () => void;
  onOpenMemory: (memoryId: string) => void;
}) {
  const [conversations, setConversations] = useState<ConversationSummaryDto[]>([]);
  const [selected, setSelected] = useState<ConversationDetailDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiRequest<{ conversations: ConversationSummaryDto[] }>("/conversations")
      .then((payload) => {
        if (!cancelled) setConversations(payload.conversations);
      })
      .catch((requestError: unknown) => {
        if (!cancelled) setError(requestError instanceof Error ? requestError.message : "无法读取来源会话");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function openConversation(conversationId: string) {
    setLoading(true);
    setError(null);
    try {
      setSelected(await apiRequest<ConversationDetailDto>(`/conversations/${encodeURIComponent(conversationId)}`));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "无法读取会话详情");
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      <button className="drawer-backdrop" onClick={onClose} type="button" aria-label="关闭来源会话" />
      <aside className="chapter-drawer conversations-drawer" aria-label="来源会话审计">
        <header>
          <div>
            <p>{selected ? conversationKindCopy[selected.source_kind] : "Conversation Sources"}</p>
            <h2>{selected ? "这段会话留下了什么" : "来源会话"}</h2>
          </div>
          <button className="icon-button drawer-close" onClick={onClose} type="button" aria-label="关闭"><X size={20} /></button>
        </header>

        {selected ? (
          <>
            <button className="conversation-back" onClick={() => setSelected(null)} type="button"><ArrowLeft size={15} />返回会话列表</button>
            <p className="conversation-id">{selected.conversation_id}</p>
            <div className="conversation-metrics">
              <span>Observation <strong>{selected.observation_count}</strong></span>
              <span>Candidate <strong>{selected.candidate_count}</strong></span>
              <span>Memory <strong>{selected.memory_count}</strong></span>
              <span>Adapter Event <strong>{selected.adapter_event_count}</strong></span>
            </div>
            {selected.observations.map((observation) => (
              <article className="observation-card" key={observation.id}>
                <header>
                  <span>{formatLocalTime(observation.observed_at)}</span>
                  <small>{observation.role} · {observation.speech_act}</small>
                </header>
                <p>{observation.excerpt}</p>
                {observation.candidates.map((candidate) => (
                  <div className="source-link candidate" key={candidate.id}>
                    <span>Candidate · {candidate.status}</span>
                    <strong>{candidate.summary}</strong>
                  </div>
                ))}
                {observation.memories.map((memory) => (
                  <button
                    className="source-link memory"
                    disabled={!memory.current}
                    key={memory.id}
                    onClick={() => onOpenMemory(memory.id)}
                    type="button"
                  >
                    <span>Memory · {memory.epistemic_status} · r{memory.revision}</span>
                    <strong>{memory.summary}</strong>
                    {memory.current ? <small>打开 Memory Detail</small> : null}
                  </button>
                ))}
              </article>
            ))}
            {selected.adapter_events.length ? (
              <section className="adapter-events">
                <h3>Adapter 执行证据</h3>
                {selected.adapter_events.map((event, index) => (
                  <p key={`${event.turn_id}-${event.event_type}-${index}`}>
                    <span>{event.event_type}</span><strong>{formatLocalTime(event.occurred_at)}</strong>
                  </p>
                ))}
                <small>这里只显示事件类型和时间，不暴露 Adapter 的内部 payload。</small>
              </section>
            ) : null}
            {!selected.observations.length && !selected.adapter_events.length ? <p className="conversation-empty">这段会话目前没有可展示的本地证据。</p> : null}
          </>
        ) : (
          <>
            <p className="drawer-lead">会话只是来源容器。记忆仍属于同一个用户，不会被切回一个个聊天线程。</p>
            {loading ? <p className="conversation-empty">正在读取本地来源索引…</p> : null}
            {error ? <p className="recall-error">{error}</p> : null}
            <div className="conversation-list">
              {conversations.map((conversation) => (
                <button key={conversation.conversation_id} onClick={() => void openConversation(conversation.conversation_id)} type="button">
                  <span>{conversationKindCopy[conversation.source_kind]} · {conversation.last_activity_at ? formatLocalTime(conversation.last_activity_at) : "时间未知"}</span>
                  <strong>{conversation.conversation_id}</strong>
                  <small>{conversation.observation_count} Observation · {conversation.pending_candidate_count} 待确认 · {conversation.memory_count} Memory</small>
                  <ChevronRight size={17} />
                </button>
              ))}
              {!loading && !error && conversations.length === 0 ? <p className="conversation-empty">HTC Core 还没有记录任何来源会话。</p> : null}
            </div>
          </>
        )}
        {selected && loading ? <p className="conversation-empty">正在读取详情…</p> : null}
        {selected && error ? <p className="recall-error">{error}</p> : null}
      </aside>
    </>
  );
}

const recallCategoryCopy = {
  allowed_to_use: { title: "允许用于回答", note: "Adapter 会收到这条记忆的安全摘要。" },
  internal_only: { title: "只作内部引导", note: "Adapter 只会收到回应方式，不会收到记忆正文。" },
  confirm_first: { title: "需要先确认", note: "涉及敏感内容，聊天中应先询问你是否愿意谈。" },
};

function RecallPreviewDrawer({ status, onClose }: { status: StatusDto | null; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [purpose, setPurpose] = useState("reply");
  const [result, setResult] = useState<RecallPreviewDto | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [conversationId] = useState(() => `workbench-preview-${crypto.randomUUID()}`);

  async function preview() {
    if (!query.trim()) {
      setError("先写一句你准备在聊天里说的话。");
      return;
    }
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await apiRequest<RecallPreviewDto>("/recall-preview", {
        method: "POST",
        body: JSON.stringify({ query, purpose, conversation_id: conversationId }),
      }));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "召回预览没有完成");
    } finally {
      setLoading(false);
    }
  }

  const grouped = result
    ? Object.fromEntries(
        Object.keys(recallCategoryCopy).map((category) => [
          category,
          result.items.filter((item) => item.category === category),
        ]),
      ) as Record<keyof typeof recallCategoryCopy, RecallPreviewDto["items"]>
    : null;

  return (
    <>
      <button className="drawer-backdrop" onClick={onClose} type="button" aria-label="关闭召回预览" />
      <aside className="chapter-drawer recall-drawer" aria-label="召回预览">
        <header>
          <div><p>Recall Preview</p><h2>这一刻，会想起什么？</h2></div>
          <button className="icon-button drawer-close" onClick={onClose} type="button" aria-label="关闭"><X size={20} /></button>
        </header>
        <p className="drawer-lead">输入一句可能发送给 AI 的话。它不会被发送到聊天，只在本机生成一次短期 RecallPackage。</p>
        <div className="recall-form">
          <textarea
            onChange={(event) => setQuery(event.target.value)}
            placeholder="例如：你还记得示例导师吗？"
            value={query}
          />
          <div>
            <label>
              用途
              <select onChange={(event) => setPurpose(event.target.value)} value={purpose}>
                <option value="reply">准备回答</option>
                <option value="reflection">回顾梳理</option>
                <option value="planning">计划讨论</option>
              </select>
            </label>
            <button className="quiet-action primary" disabled={loading} onClick={() => void preview()} type="button">
              {loading ? "正在预览…" : "查看召回结果"}
            </button>
          </div>
        </div>
        {error ? <p className="recall-error">{error}</p> : null}
        {result ? (
          <section className="recall-result">
            <p className="recall-package">模拟会话 {conversationId.slice(-8)} · 短期包 {result.package_id.slice(-8)} · {formatLocalTime(result.expires_at)} 失效</p>
            {result.items.length === 0 ? (
              <p className="recall-empty">{status && !status.cross_session_internal_use
                ? "用户级跨会话记忆当前已关闭，因此 Core 没有检索任何 Memory。"
                : "没有匹配到可用于这句话的记忆。"}</p>
            ) : null}
            {(Object.keys(recallCategoryCopy) as Array<keyof typeof recallCategoryCopy>).map((category) => {
              const items = grouped?.[category] ?? [];
              if (!items.length) return null;
              return (
                <div className={`recall-group ${category}`} key={category}>
                  <header><h3>{recallCategoryCopy[category].title}</h3><span>{items.length}</span></header>
                  <p>{recallCategoryCopy[category].note}</p>
                  {items.map((item) => (
                    <article key={item.memory_id}>
                      <strong>{item.display_summary}</strong>
                      <small>{item.reason_codes.join(" · ")}</small>
                    </article>
                  ))}
                </div>
              );
            })}
            <div className="adapter-preview">
              <h3>Adapter 实际获得</h3>
              <p>允许摘要 {result.adapter_payload.allowed_memories.length} 条</p>
              {result.adapter_payload.response_guidance.map((value) => <code key={value}>{value}</code>)}
              {result.adapter_payload.confirmation_prompts.map((value) => <code key={value}>{value}</code>)}
              {result.adapter_payload.response_constraints.map((value) => <code key={value}>{value}</code>)}
              {!result.adapter_payload.response_guidance.length
                && !result.adapter_payload.confirmation_prompts.length
                && !result.adapter_payload.response_constraints.length
                ? <small>没有额外的回应约束。</small>
                : null}
            </div>
          </section>
        ) : null}
      </aside>
    </>
  );
}

function SettingsDrawer({
  status,
  onClose,
  onPolicyChange,
}: {
  status: StatusDto | null;
  onClose: () => void;
  onPolicyChange: (enabled: boolean) => Promise<void>;
}) {
  const [saving, setSaving] = useState(false);
  async function changePolicy(enabled: boolean) {
    setSaving(true);
    try {
      await onPolicyChange(enabled);
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      <button className="drawer-backdrop" onClick={onClose} type="button" aria-label="关闭记忆设置" />
      <aside className="chapter-drawer settings-drawer" aria-label="HTC Core 设置">
        <header>
          <div><p>Local Core</p><h2>记忆边界</h2></div>
          <button className="icon-button drawer-close" onClick={onClose} type="button" aria-label="关闭"><X size={20} /></button>
        </header>
        <p className="drawer-lead">Workbench 只管理本机 HTC Core 中属于当前用户的记忆。</p>
        <section className="settings-facts">
          <p><span>当前用户</span><strong>{status?.user_id ?? "未连接"}</strong></p>
          <p><span>时区</span><strong>{status?.timezone ?? "—"}</strong></p>
          <p><span>已治理记忆</span><strong>{status?.current_memories ?? 0}</strong></p>
          <p><span>待确认候选</span><strong>{status?.pending_candidates ?? 0}</strong></p>
        </section>
        <section className="policy-card">
          <div>
            <h3>允许跨会话内部使用</h3>
            <p>开启后，Adapter 可以在不同会话之间检索你已经授权的记忆。单条记忆仍受自己的权限控制。</p>
          </div>
          <button
            aria-checked={status?.cross_session_internal_use ?? false}
            className={`policy-switch ${status?.cross_session_internal_use ? "on" : ""}`}
            disabled={!status || saving}
            onClick={() => void changePolicy(!(status?.cross_session_internal_use ?? false))}
            role="switch"
            type="button"
          ><span /></button>
        </section>
        <blockquote>HTC 不读取 Codex、Claude 或 ChatGPT 的私有数据库；接入内容必须由 Adapter 或显式导入进入 Core。</blockquote>
      </aside>
    </>
  );
}

function ChapterDrawer({
  chapter,
  onClose,
  onSuppress,
  onRevise,
  onDelete,
}: {
  chapter: MemoryChapter;
  onClose: () => void;
  onSuppress: (chapter: MemoryChapter) => Promise<void>;
  onRevise: (chapter: MemoryChapter, summary: string) => Promise<void>;
  onDelete: (chapter: MemoryChapter) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [summary, setSummary] = useState(chapter.summary);
  const [explanation, setExplanation] = useState<MemoryExplanationDto | null>(null);
  const [explanationError, setExplanationError] = useState<string | null>(null);
  useEffect(() => {
    let cancelled = false;
    apiRequest<MemoryExplanationDto>(`/memories/${encodeURIComponent(chapter.memoryId)}/explain`)
      .then((value) => {
        if (!cancelled) setExplanation(value);
      })
      .catch((error: unknown) => {
        if (!cancelled) setExplanationError(error instanceof Error ? error.message : "无法读取记忆解释");
      });
    return () => {
      cancelled = true;
    };
  }, [chapter.memoryId]);
  return (
    <>
      <button className="drawer-backdrop" onClick={onClose} type="button" aria-label="关闭记忆章节" />
      <aside className="chapter-drawer" aria-label={`${chapter.title}详情`}>
        <header>
          <div>
            <p>{chapter.period} · {stateCopy[chapter.state]}</p>
            <h2>{chapter.title}</h2>
          </div>
          <button className="icon-button drawer-close" onClick={onClose} type="button" aria-label="关闭">
            <X size={20} />
          </button>
        </header>
        {editing ? (
          <div className="drawer-edit">
            <textarea value={summary} onChange={(event) => setSummary(event.target.value)} />
            <button className="quiet-action primary" onClick={() => void onRevise(chapter, summary)} type="button">保存修改</button>
          </div>
        ) : <p className="drawer-lead">{chapter.summary}</p>}
        <blockquote>{chapter.meaning}</blockquote>

        <section className="drawer-section">
          <h3><Clock3 size={17} />这一章保留了什么</h3>
          <ul>{chapter.memories.map((memory) => <li key={memory}>{memory}</li>)}</ul>
        </section>

        <section className="drawer-section">
          <h3><MapPin size={17} />来源脉络</h3>
          <div className="source-list">
            {chapter.sources.map((source) => <span key={source}>{source}</span>)}
          </div>
        </section>

        <section className="drawer-section">
          <h3><ShieldCheck size={17} />为什么这样记住</h3>
          {explanation ? (
            <div className="memory-explanation">
              {explanation.events.map((event, index) => (
                <p key={`${event.event_type}-${event.created_at}-${index}`}>
                  <span>{event.event_type}</span>
                  <strong>{formatLocalTime(event.created_at)}</strong>
                </p>
              ))}
              {explanation.governance_traces.flatMap((trace) => trace.reason_codes).map((reason) => (
                <p key={reason}><span>治理依据</span><strong>{reason}</strong></p>
              ))}
            </div>
          ) : <p className="explanation-status">{explanationError ?? "正在读取可解释记录…"}</p>}
        </section>

        <section className="drawer-section governance-note">
          <ShieldCheck size={18} />
          <div>
            <h3>由你决定如何被记住</h3>
            <p>这段记忆可以纠正、合并、隐藏或删除；敏感内容不会因为“相关”就被主动说出来。</p>
          </div>
        </section>

        <footer>
          <div className="chapter-tags">{chapter.tags.map((tag) => <span key={tag}>{tag}</span>)}</div>
          <div className="drawer-actions">
            <button className="quiet-action" onClick={() => setEditing((value) => !value)} type="button">{editing ? "取消修改" : "修改"}</button>
            <button className="quiet-action" onClick={() => void onSuppress(chapter)} type="button"><EyeOff size={16} />不要主动提</button>
            <button className="quiet-action danger" onClick={() => void onDelete(chapter)} type="button">撤回</button>
          </div>
        </footer>
      </aside>
    </>
  );
}

function formatLocalTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Shanghai",
  }).format(date);
}
