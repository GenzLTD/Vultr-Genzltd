"""
社交图谱构建器 — 从现有数据库表构建用户社交网络邻接表

数据来源（不新建表，纯读现有数据）:
  1. invite_codes: created_by → used_by 形成推荐边（有向 → 无向）
  2. fleet_members: 同舰队的用户之间形成共属边
  3. enterprise_users: 同企业的用户之间形成共属边

输出: {user_id: set(neighbor_user_ids)} 邻接表
"""
from __future__ import annotations
from typing import Dict, Set
from collections import defaultdict


def build_social_graph(db) -> Dict[str, Set[str]]:
    """
    从数据库构建社交图谱邻接表。

    Args:
        db: DatabaseManager 实例（looma-zervi 的 db manager）

    Returns:
        {user_id: {neighbor_id, ...}} 无向图邻接表
    """
    adj: Dict[str, Set[str]] = defaultdict(set)

    with db.get_conn() as conn:
        # 1. 推荐边：invite_codes.created_by ↔ used_by
        rows = conn.execute(
            """SELECT created_by, used_by FROM invite_codes
               WHERE created_by IS NOT NULL AND used_by IS NOT NULL"""
        ).fetchall()
        for row in rows:
            creator = row["created_by"]
            consumer = row["used_by"]
            if creator and consumer:
                adj[creator].add(consumer)
                adj[consumer].add(creator)

        # 2. 舰队共属边：同一 fleet 的所有成员互连
        fleet_rows = conn.execute(
            """SELECT fleet_id, user_id FROM fleet_members"""
        ).fetchall()
        fleet_groups: Dict[str, list] = defaultdict(list)
        for row in fleet_rows:
            fleet_groups[row["fleet_id"]].append(row["user_id"])

        for members in fleet_groups.values():
            for i, u1 in enumerate(members):
                for u2 in members[i + 1:]:
                    adj[u1].add(u2)
                    adj[u2].add(u1)

        # 3. 企业共属边：同一 enterprise 的所有成员互连
        ent_rows = conn.execute(
            """SELECT enterprise_id, user_id FROM enterprise_users"""
        ).fetchall()
        ent_groups: Dict[str, list] = defaultdict(list)
        for row in ent_rows:
            ent_groups[row["enterprise_id"]].append(row["user_id"])

        for members in ent_groups.values():
            for i, u1 in enumerate(members):
                for u2 in members[i + 1:]:
                    adj[u1].add(u2)
                    adj[u2].add(u1)

    # 确保所有用户都在图中（即使是孤立节点）
    return dict(adj)


def get_graph_stats(adj: Dict[str, Set[str]]) -> dict:
    """计算社交图谱的基本统计信息"""
    n = len(adj)
    if n == 0:
        return {"nodes": 0, "edges": 0, "avg_degree": 0, "isolated": 0}

    total_edges = sum(len(neighbors) for neighbors in adj.values()) // 2
    isolated = sum(1 for neighbors in adj.values() if len(neighbors) == 0)
    avg_degree = sum(len(neighbors) for neighbors in adj.values()) / n

    # 找 Hub 节点（度数最高的用户）
    degree_sorted = sorted(adj.items(), key=lambda x: len(x[1]), reverse=True)
    top_hubs = [
        {"user_id": uid, "degree": len(neighbors)}
        for uid, neighbors in degree_sorted[:10]
    ]

    return {
        "nodes": n,
        "edges": total_edges,
        "avg_degree": round(avg_degree, 2),
        "isolated": isolated,
        "top_hubs": top_hubs,
    }
