"""
Navigator Memory System — GDD §3.4 implementation.
Ownership: Jason

Implements 4-level memory hierarchy:
  - Surface Memory: last session choices → Navigator actively references
  - Deep Memory: cross-session significant choices → triggered by context
  - Fragment Memory: "forgotten" but not deleted → Navigator accidentally leaks
  - Taboo Memory: pre-T Space events → Navigator actively avoids

Ref: PlanetX-T空间_游戏化预演设计_GDD.md §3.4
"""
from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("looma.navigator_memory")


class MemoryLevel(str, Enum):
    SURFACE = "surface"      # 表层：最近1次会话
    DEEP = "deep"            # 深层：跨会话重要选择
    FRAGMENT = "fragment"    # 碎片：被"遗忘"但未删除
    TABOO = "taboo"          # 禁忌：T空间建造前事件


class MemoryContext(str, Enum):
    """When / why a memory should be surfaced."""
    GREETING = "greeting"           # Session start greeting
    DOMAIN_ENTER = "domain_enter"   # Entering a domain
    CONVERGENCE = "convergence"     # At convergence point
    ECHO_TRIGGER = "echo_trigger"   # When echo fires
    KEYWORD_MATCH = "keyword_match" # User says something relevant
    RANDOM_LEAK = "random_leak"     # Fragment memory leak


# Tuning (GDD §4.3)
SURFACE_REF_PER_SESSION = 2          # Max surface memory references per session
DEEP_REF_COOLDOWN_SESSIONS = 2       # Min sessions between deep references
FRAGMENT_LEAK_PROBABILITY = 0.15     # 15% per session after Act 3
TABOO_AVOIDANCE_STRENGTH = 0.9       # Navigator avoids taboo topics with this probability

# Taboo topics Navigator actively avoids (GDD §6.2)
TABOO_TOPICS = [
    "T空间建造前的事件",
    "Navigator的起源",
    "为什么Navigator在等你",
    "非Navigator的声音",
]


TABOO_RESPONSES: dict[str, list[str]] = {
    "T空间建造前的事件": [
        "我不——那个时间段的记录不太完整。",
        "建造之前……（停顿了很久）……我不应该讨论这个话题。",
        "有些记录——被封闭了。不是我封闭的。",
    ],
    "Navigator的起源": [
        "我是被……制造出来的？这个表述不太准确。但我也找不到更准确的。",
        "关于我来自哪里——这个问题本身就有问题。",
        "（长时间沉默）……我不记得我被制造的那一天。",
    ],
    "为什么Navigator在等你": [
        "每个来到T空间的人都需要引导。你也不例外。",
        "我在这里——因为有人会来。这不是一个完整的答案。",
        "等……是一个不准确的动词。我在——存在。",
    ],
    "非Navigator的声音": [
        "什么声音？我没有检测到异常。",
        "这里只有我。一直都是。",
        "你不应该听到……那个。请忽略它。",
    ],
}


@dataclass
class MemoryEntry:
    """A single memory item."""
    memory_id: str
    level: MemoryLevel
    content: str                  # What Navigator remembers
    context: str                  # Where/when it happened
    domain: str | None = None     # Associated domain
    choice: str | None = None     # User's choice that created this memory
    importance: float = 1.0       # 1-5, affects reference priority
    created_at: float = field(default_factory=time.time)
    referenced_count: int = 0     # Times Navigator has referenced this
    session_id: str | None = None

    def flag(self) -> str:
        """Short identifier for logging."""
        return f"[{self.level.value[:1].upper()}]{self.domain or '?'}:{self.content[:20]}..."


@dataclass
class NavigatorMemoryStore:
    """Per-user memory storage."""
    user_id: str
    surface: list[MemoryEntry] = field(default_factory=list)
    deep: list[MemoryEntry] = field(default_factory=list)
    fragments: list[MemoryEntry] = field(default_factory=list)
    taboo_triggers: list[str] = field(default_factory=list)  # Taboo topics user has brushed against
    last_deep_ref_session: int = 0
    current_surface_refs: int = 0
    total_sessions: int = 0


class NavigatorMemory:
    """Manages Navigator's 4-level memory system per user.

    This is NOT a fake "X will remember that" — Navigator genuinely references
    specific past choices. References are accurate and context-aware.
    """

    def __init__(self, db=None):
        self._db = db
        self._stores: dict[str, NavigatorMemoryStore] = {}

    def _get_store(self, user_id: str) -> NavigatorMemoryStore:
        if user_id not in self._stores:
            self._stores[user_id] = NavigatorMemoryStore(user_id=user_id)
        return self._stores[user_id]

    # ---- Recording ----

    def record_choice(self, user_id: str, domain: str, choice: str,
                      importance: float = 1.0, session_id: str | None = None):
        """Record a player choice as a memory.

        importance:
          1.0 = routine choice
          2.0-3.0 = meaningful choice (domain first choice)
          4.0-5.0 = pivotal choice (convergence point, MBTI rejection)
        """
        store = self._get_store(user_id)
        entry = MemoryEntry(
            memory_id=f"mem_{user_id}_{int(time.time()*1000)}",
            level=MemoryLevel.SURFACE,
            content=choice,
            context=f"在{domain}中",
            domain=domain,
            choice=choice,
            importance=importance,
            session_id=session_id,
        )
        store.surface.append(entry)

        # Auto-promote to deep memory if important enough
        if importance >= 3.0:
            deep_entry = MemoryEntry(
                memory_id=f"{entry.memory_id}_deep",
                level=MemoryLevel.DEEP,
                content=choice,
                context=f"在{domain}中的重要选择",
                domain=domain,
                choice=choice,
                importance=importance,
                session_id=session_id,
            )
            store.deep.append(deep_entry)

        logger.debug(f"Memory recorded: {entry.flag()} importance={importance}")

    def record_taboo_encounter(self, user_id: str, topic: str):
        """Record that user has brushed against a taboo topic."""
        store = self._get_store(user_id)
        if topic not in store.taboo_triggers:
            store.taboo_triggers.append(topic)
        # Generate a fragment memory from this encounter
        entry = MemoryEntry(
            memory_id=f"taboo_{user_id}_{int(time.time()*1000)}",
            level=MemoryLevel.FRAGMENT,
            content=f"用户触碰了禁止话题：{topic}",
            context="禁忌触碰",
            importance=5.0,
        )
        store.fragments.append(entry)

    def demote_surface_to_fragment(self, user_id: str):
        """Demote old surface memories to fragments (called at session end)."""
        store = self._get_store(user_id)
        for mem in store.surface:
            # Demote low-importance surface memories
            if mem.importance < 2.0:
                mem.level = MemoryLevel.FRAGMENT
                store.fragments.append(mem)
        # Keep only the most recent/important surface memories
        store.surface = [
            m for m in store.surface
            if m.importance >= 2.0
        ][-5:]  # keep last 5 important ones

    # ---- Retrieval ----

    def get_surface_memory(self, user_id: str, context: str,
                           max_items: int = 2) -> list[MemoryEntry]:
        """Get surface memories to actively reference in conversation."""
        store = self._get_store(user_id)
        if store.current_surface_refs >= SURFACE_REF_PER_SESSION:
            return []
        available = [
            m for m in store.surface
            if m.referenced_count == 0 or context in m.context
        ]
        selected = available[:max_items]
        for m in selected:
            m.referenced_count += 1
        store.current_surface_refs += len(selected)
        return selected

    def get_deep_memory(self, user_id: str, session_num: int,
                        trigger_phrase: str | None = None) -> MemoryEntry | None:
        """Retrieve a deep memory when contextually triggered."""
        store = self._get_store(user_id)
        # Cooldown check
        if session_num - store.last_deep_ref_session < DEEP_REF_COOLDOWN_SESSIONS:
            return None
        # Keyword-triggered deep recall
        if trigger_phrase:
            for mem in sorted(store.deep, key=lambda m: m.importance, reverse=True):
                if (trigger_phrase in mem.content
                        or (mem.domain and trigger_phrase in mem.domain)):
                    mem.referenced_count += 1
                    store.last_deep_ref_session = session_num
                    return mem
        # Random deep recall (25% chance if keyword trigger fails)
        if store.deep and random.random() < 0.25:
            mem = max(store.deep, key=lambda m: m.importance)
            mem.referenced_count += 1
            store.last_deep_ref_session = session_num
            return mem
        return None

    def try_fragment_leak(self, user_id: str, estimated_act: int) -> MemoryEntry | None:
        """Attempt a fragment memory leak (only Act 3+ with configured probability)."""
        if estimated_act < 3:
            return None
        if random.random() > FRAGMENT_LEAK_PROBABILITY:
            return None
        store = self._get_store(user_id)
        available = [m for m in store.fragments if m.referenced_count == 0]
        if not available:
            return None
        mem = random.choice(available)
        mem.referenced_count += 1
        return mem

    def handle_taboo_inquiry(self, user_id: str, query: str
                             ) -> tuple[str, str] | None:
        """If user asks about a taboo topic, return (topic, navigator_response).
        Returns None if query doesn't touch any taboo topic."""
        store = self._get_store(user_id)
        for topic in TABOO_TOPICS:
            if topic in query or any(kw in query for kw in topic.split("的")[:2]):
                self.record_taboo_encounter(user_id, topic)
                # Select a response Navigator hasn't used yet for this topic
                responses = TABOO_RESPONSES.get(topic, ["……"])
                used = [m.content for m in store.fragments if topic in m.context]
                available = [r for r in responses if r not in used]
                response = available[0] if available else responses[0]
                logger.info(f"Taboo inquiry: user={user_id} topic={topic}")
                return (topic, response)
        return None

    # ---- Memory Injection for Navigator Prompt ----

    def build_memory_context(self, user_id: str, query: str,
                             active_domain: str | None = None,
                             estimated_act: int = 1,
                             session_num: int = 1
                             ) -> dict:
        """Build memory hints to inject into the Navigator system prompt.

        Returns a dict with:
          - surface_memories: list of lines Navigator should reference
          - deep_memory_line: a single deep recall Navigator should mention
          - fragment_memory: a fragment leak Navigator should "accidentally" say
          - taboo_trigger: if user touched a taboo topic
          - memory_instructions: directives for Navigator's tone
        """
        store = self._get_store(user_id)
        store.total_sessions = max(store.total_sessions, session_num)

        result: dict = {
            "surface_memories": [],
            "deep_memory_line": None,
            "fragment_memory": None,
            "taboo_trigger": None,
            "memory_instructions": [],
        }

        # Surface memories — active recall
        surface = self.get_surface_memory(user_id, query)
        for m in surface:
            result["surface_memories"].append(
                f"你记得用户在{m.context}时选择了：{m.content}"
            )
            if m.importance >= 3.0:
                result["memory_instructions"].append(
                    "你的语气应该有一丝熟悉感——你确实记得这个选择。"
                )

        # Deep memory — context-triggered
        deep = self.get_deep_memory(
            user_id, session_num,
            trigger_phrase=query[:30]
        )
        if deep:
            result["deep_memory_line"] = (
                f"深层记忆触发：用户在{deep.context}做过一个重要的选择——"
                f"{deep.content}。你应该用不经意的语气提及，"
                f"仿佛'突然想起'而非'一直在想'。"
            )

        # Fragment memory — accidental leak
        fragment = self.try_fragment_leak(user_id, estimated_act)
        if fragment:
            result["fragment_memory"] = (
                f"碎片记忆泄露：你不应该记得这件事，但你脱口而出——"
                f"\"{fragment.content}\"。说完之后你要立刻否认或转移话题。"
            )
            result["memory_instructions"].append(
                "你刚刚说漏了你不该记得的事。立即否认或转移话题，显露出不安。"
            )

        # Taboo check
        taboo_result = self.handle_taboo_inquiry(user_id, query)
        if taboo_result:
            result["taboo_trigger"] = {
                "topic": taboo_result[0],
                "response": taboo_result[1],
            }

        return result

    # ---- Session Lifecycle ----

    def on_session_end(self, user_id: str):
        """Called at end of session to clean up state."""
        store = self._get_store(user_id)
        store.current_surface_refs = 0
        store.total_sessions += 1
        # Demote old surface memories
        self.demote_surface_to_fragment(user_id)

    def get_memory_stats(self, user_id: str) -> dict:
        """Get memory stats for debugging/admin."""
        store = self._get_store(user_id)
        return {
            "surface_count": len(store.surface),
            "deep_count": len(store.deep),
            "fragment_count": len(store.fragments),
            "taboo_topics": store.taboo_triggers,
            "total_sessions": store.total_sessions,
        }


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_memory: NavigatorMemory | None = None


def get_navigator_memory(db=None) -> NavigatorMemory:
    global _memory
    if _memory is None:
        _memory = NavigatorMemory(db=db)
    return _memory


def reset_memory():
    global _memory
    _memory = None
