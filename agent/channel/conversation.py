"""Conversation management endpoints — list, history, new, reset.

Split from langgraph_channel.py for better organization.
"""
import json, logging, os, time, traceback
from fastapi import APIRouter

router = APIRouter()
logger = logging.getLogger(__name__)


def _extract_msg_role_content(m) -> tuple[str, str]:
    """Extract (role, content) from a message — handles both dict {'role','content'}
    and LangChain objects with .type/.content attributes."""
    # Dict-style (initial checkpoint or JSON-serialized)
    if isinstance(m, dict):
        r = m.get("role", m.get("type", ""))
        c = str(m.get("content", ""))
        return (r, c)
    # LangChain message objects (checkpoint-deserialized)
    role = str(getattr(m, "type", ""))
    content = str(getattr(m, "content", ""))
    return (role, content)


def _extract_messages(checkpoint: dict) -> list:
    """Extract messages from a checkpoint — handles v2 messages channel and
    __start__ channel (initial state before first agent step)."""
    values = checkpoint.get("channel_values", {}) if isinstance(checkpoint, dict) else {}
    if not isinstance(values, dict):
        return []
    msgs = values.get("messages", []) or []
    # Fallback: initial checkpoint may store messages under __start__
    if not msgs and "__start__" in values:
        start_val = values["__start__"]
        if isinstance(start_val, dict):
            msgs = start_val.get("messages", []) or []
    return msgs


@router.get("/chat/conversations")
async def list_conversations(prefix: str = "t-"):
    """列出对话（按 persona 前缀过滤: t-教师 s-学生 p-家长, 支持逗号分隔多前缀如 t-,c）"""
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "chemai_checkpoints.db")
    if not os.path.exists(db_path):
        return {"conversations": [], "total": 0}

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    prefixes = [p.strip() for p in prefix.split(",") if p.strip()]
    clauses = " OR ".join(["thread_id LIKE ?" for _ in prefixes])
    params = [f"{p}%" for p in prefixes]
    cursor.execute(f"""
        SELECT DISTINCT thread_id FROM checkpoints
        WHERE {clauses}
        ORDER BY thread_id DESC LIMIT 200
    """, params)
    threads = [row[0] for row in cursor.fetchall()]
    conn.close()

    if not threads:
        return {"conversations": [], "total": 0}

    conversations = []
    from agent.langgraph_agent_v2 import _get_v2_checkpointer
    cp = await _get_v2_checkpointer()

    for tid in threads:
        try:
            ckpt = await cp.aget_tuple({"configurable": {"thread_id": tid}})
            if not ckpt:
                continue
            checkpoint = ckpt.checkpoint if hasattr(ckpt, 'checkpoint') else ckpt[0] if isinstance(ckpt, tuple) else ckpt
            if not isinstance(checkpoint, dict):
                continue
            msgs = _extract_messages(checkpoint)
            if not msgs:
                continue
            title = ""
            preview = ""
            msg_count = 0
            for m in msgs:
                role, content = _extract_msg_role_content(m)
                if role in ("human", "user"):
                    if not title:
                        title = content[:50]
                        preview = content[:100]
                    msg_count += 1
                elif role == "ai":
                    msg_count += 1
            last_at = str(ckpt.metadata.get("timestamp", "")) if hasattr(ckpt, 'metadata') and ckpt.metadata else ""
            conversations.append({
                "thread_id": tid, "title": title or "新对话", "preview": preview,
                "last_at": last_at, "message_count": msg_count,
            })
        except Exception:
            continue

    return {"conversations": conversations, "total": len(conversations)}


@router.get("/chat/history/{thread_id}")
async def get_conversation_history(thread_id: str):
    """获取指定对话的完整消息历史"""
    from agent.langgraph_agent_v2 import _get_v2_checkpointer
    cp = await _get_v2_checkpointer()

    try:
        ckpt = await cp.aget_tuple({"configurable": {"thread_id": thread_id}})
        if not ckpt:
            return {"messages": [], "thread_id": thread_id}
        checkpoint = ckpt.checkpoint if hasattr(ckpt, 'checkpoint') else ckpt[0] if isinstance(ckpt, tuple) else ckpt
        if not isinstance(checkpoint, dict):
            return {"messages": [], "thread_id": thread_id}

        msgs = _extract_messages(checkpoint)
        messages = []
        for m in msgs:
            role, content = _extract_msg_role_content(m)
            if role in ("human", "user"):
                messages.append({"role": "user", "content": content})
            elif role in ("ai", "assistant", "AIMessageChunk"):
                messages.append({"role": "assistant", "content": content})
        return {"messages": messages, "thread_id": thread_id}
    except Exception as e:
        logger.error(f"get_conversation_history({thread_id}): {e}\n{traceback.format_exc()}")
        return {"messages": [], "thread_id": thread_id, "error": str(e)}


@router.post("/chat/new")
async def new_conversation():
    """创建新对话，返回新的 thread_id"""
    return {"thread_id": f"m-{int(time.time() * 1000)}"}


@router.delete("/chat/conversations/{thread_id}")
async def delete_conversation(thread_id: str):
    """强制删除对话 — 从 checkpoint 数据库彻底清除"""
    import sqlite3
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "chemai_checkpoints.db")
    if not os.path.exists(db_path):
        return {"success": False, "message": "数据库不存在"}

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # Database has tables: checkpoints, writes
        cursor.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
        cursor.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        cursor.close()
        return {"success": True, "message": "已删除" if deleted else "未找到该对话"}
    except Exception as e:
        return {"success": False, "message": str(e)}
    finally:
        conn.close()


@router.post("/chat/langgraph/reset")
async def agent_chat_langgraph_reset(conversation_id: str):
    """重置对话"""
    from agent.channel.fastapi_sse import _conversations
    cleared_conv = False
    if conversation_id in _conversations:
        del _conversations[conversation_id]
        cleared_conv = True

    try:
        from agent.langgraph_agent import _get_checkpointer
        cp = await _get_checkpointer()
        config = {"configurable": {"thread_id": conversation_id}}
        await cp.aput(config, checkpoint={"messages": []}, metadata={}, new_versions={})
    except Exception:
        pass

    if cleared_conv:
        return {"success": True, "message": "对话已重置"}
    return {"success": False, "message": "对话不存在"}
