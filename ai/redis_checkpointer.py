"""基于基础 Redis 命令实现的 langgraph checkpointer。

官方的 langgraph-checkpoint-redis 依赖 RediSearch 模块（FT.* 命令）建立索引，
普通 Redis 无法运行。这里只用 GET/SET/ZADD/HSET 等基础命令，复刻 InMemorySaver
的存储语义，让普通 Redis 也能持久化对话状态。

存储结构（key 前缀 ai:ckpt）：
    ai:ckpt:threads                     所有 thread_id 的集合
    ai:ckpt:ns:{tid}                    thread 下所有 checkpoint_ns
    ai:ckpt:cp:{tid}:{ns}:{cid}         单个 checkpoint（JSON）
    ai:ckpt:z:{tid}:{ns}                checkpoint_id 有序索引（ZSET，score=id 的序号）
    ai:ckpt:w:{tid}:{ns}:{cid}          pending writes（ZSET，按写入顺序）
    ai:ckpt:w:{tid}:{ns}:{cid}:seen     已写入的 (task_id, idx)，用于去重
    ai:ckpt:w:{tid}:{ns}:{cid}:seq      写入序号计数器
    ai:ckpt:b:{tid}:{ns}:{ch}:{ver}     channel 快照（blob）
    ai:ckpt:bk:{tid}                    该 thread 的所有 blob key，便于整体删除
"""

from __future__ import annotations

import base64
import json
import random
from collections.abc import AsyncIterator, Sequence
from typing import Any

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    SerializerProtocol,
    get_checkpoint_id,
    get_checkpoint_metadata,
)

PREFIX = "ai:ckpt"
EMPTY_BLOB = ("empty", b"")


def pack_typed(value: tuple[str, bytes]) -> list[str]:
    """把 serde 的 (类型, 字节) 转成 JSON 可存储的形式。"""
    type_, payload = value
    return [type_, base64.b64encode(payload).decode()]


def unpack_typed(value: Sequence[str]) -> tuple[str, bytes]:
    type_, payload = value
    return type_, base64.b64decode(payload)


def checkpoint_score(checkpoint_id: str) -> float:
    """checkpoint_id 形如 '0000...01.123'，取整数部分作为排序权重。"""
    try:
        return float(checkpoint_id.split(".")[0])
    except (ValueError, IndexError):
        return 0.0


class AsyncRedisCheckpointer(BaseCheckpointSaver[str]):
    def __init__(
        self,
        redis_client: Any,
        *,
        serde: SerializerProtocol | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        super().__init__(serde=serde)
        self.redis = redis_client
        self.ttl = ttl_seconds

    # ---------- key 构造 ----------

    def _threads_key(self) -> str:
        return f"{PREFIX}:threads"

    def _ns_key(self, thread_id: str) -> str:
        return f"{PREFIX}:ns:{thread_id}"

    def _cp_key(self, thread_id: str, ns: str, cid: str) -> str:
        return f"{PREFIX}:cp:{thread_id}:{ns}:{cid}"

    def _z_key(self, thread_id: str, ns: str) -> str:
        return f"{PREFIX}:z:{thread_id}:{ns}"

    def _w_key(self, thread_id: str, ns: str, cid: str) -> str:
        return f"{PREFIX}:w:{thread_id}:{ns}:{cid}"

    def _blob_key(self, thread_id: str, ns: str, channel: str, version: Any) -> str:
        return f"{PREFIX}:b:{thread_id}:{ns}:{channel}:{version}"

    def _blob_index_key(self, thread_id: str) -> str:
        return f"{PREFIX}:bk:{thread_id}"

    # ---------- 内部读写 ----------

    async def _load_blobs(
        self, thread_id: str, ns: str, versions: ChannelVersions
    ) -> dict[str, Any]:
        if not versions:
            return {}
        keys = [
            self._blob_key(thread_id, ns, channel, version)
            for channel, version in versions.items()
        ]
        raws = await self.redis.mget(keys)
        values: dict[str, Any] = {}
        for (channel, _), raw in zip(versions.items(), raws):
            if raw is None:
                continue
            type_, payload = unpack_typed(json.loads(raw))
            if type_ == EMPTY_BLOB[0]:
                continue
            values[channel] = self.serde.loads_typed((type_, payload))
        return values

    async def _load_writes(
        self, thread_id: str, ns: str, cid: str
    ) -> list[tuple[str, str, Any]]:
        items = await self.redis.zrange(self._w_key(thread_id, ns, cid), 0, -1)
        result = []
        for item in items:
            task_id, channel, packed, _task_path, _idx = json.loads(item)
            result.append((task_id, channel, self.serde.loads_typed(unpack_typed(packed))))
        return result

    async def _build_tuple(
        self, thread_id: str, ns: str, cid: str, raw: str, config: RunnableConfig
    ) -> CheckpointTuple:
        data = json.loads(raw)
        checkpoint_: Checkpoint = self.serde.loads_typed(unpack_typed(data["c"]))
        parent_id = data.get("p")
        return CheckpointTuple(
            config={
                "configurable": {
                    "thread_id": thread_id,
                    "checkpoint_ns": ns,
                    "checkpoint_id": cid,
                }
            },
            checkpoint={
                **checkpoint_,
                "channel_values": await self._load_blobs(
                    thread_id, ns, checkpoint_["channel_versions"]
                ),
            },
            metadata=self.serde.loads_typed(unpack_typed(data["m"])),
            pending_writes=await self._load_writes(thread_id, ns, cid),
            parent_config=(
                {
                    "configurable": {
                        "thread_id": thread_id,
                        "checkpoint_ns": ns,
                        "checkpoint_id": parent_id,
                    }
                }
                if parent_id
                else None
            ),
        )

    def _apply_ttl(self, pipe: Any, keys: Sequence[str]) -> None:
        if not self.ttl:
            return
        for key in keys:
            pipe.expire(key, self.ttl)

    # ---------- 必须实现的接口 ----------

    async def aget_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        thread_id = config["configurable"]["thread_id"]
        ns = config["configurable"].get("checkpoint_ns", "")
        cid = get_checkpoint_id(config)
        if cid is None:
            latest = await self.redis.zrevrange(self._z_key(thread_id, ns), 0, 0)
            if not latest:
                return None
            cid = latest[0]
        raw = await self.redis.get(self._cp_key(thread_id, ns, cid))
        if raw is None:
            return None
        return await self._build_tuple(thread_id, ns, cid, raw, config)

    async def alist(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ) -> AsyncIterator[CheckpointTuple]:
        if config:
            thread_ids = [config["configurable"]["thread_id"]]
            wanted_ns = config["configurable"].get("checkpoint_ns")
        else:
            thread_ids = list(await self.redis.smembers(self._threads_key()))
            wanted_ns = None
        wanted_cid = get_checkpoint_id(config) if config else None
        before_cid = get_checkpoint_id(before) if before else None

        for thread_id in thread_ids:
            namespaces = set(await self.redis.smembers(self._ns_key(thread_id)))
            if wanted_ns is not None:
                namespaces = {wanted_ns} if wanted_ns in namespaces else set()
            for ns in namespaces:
                cids = await self.redis.zrevrange(self._z_key(thread_id, ns), 0, -1)
                for cid in cids:
                    if wanted_cid and cid != wanted_cid:
                        continue
                    if before_cid and cid >= before_cid:
                        continue
                    raw = await self.redis.get(self._cp_key(thread_id, ns, cid))
                    if raw is None:
                        continue
                    item = await self._build_tuple(thread_id, ns, cid, raw, config or {})
                    if filter and not all(
                        item.metadata.get(key) == value for key, value in filter.items()
                    ):
                        continue
                    if limit is not None and limit <= 0:
                        break
                    if limit is not None:
                        limit -= 1
                    yield item

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        thread_id = config["configurable"]["thread_id"]
        ns = config["configurable"]["checkpoint_ns"]
        cid = checkpoint["id"]

        body = dict(checkpoint)
        values: dict[str, Any] = body.pop("channel_values")

        pipe = self.redis.pipeline()
        blob_keys = []
        for channel, version in new_versions.items():
            key = self._blob_key(thread_id, ns, channel, version)
            payload = (
                pack_typed(self.serde.dumps_typed(values[channel]))
                if channel in values
                else pack_typed(EMPTY_BLOB)
            )
            pipe.set(key, json.dumps(payload))
            pipe.sadd(self._blob_index_key(thread_id), key)
            blob_keys.append(key)

        cp_key = self._cp_key(thread_id, ns, cid)
        pipe.set(
            cp_key,
            json.dumps(
                {
                    "c": pack_typed(self.serde.dumps_typed(body)),
                    "m": pack_typed(
                        self.serde.dumps_typed(get_checkpoint_metadata(config, metadata))
                    ),
                    "p": config["configurable"].get("checkpoint_id"),
                }
            ),
        )
        pipe.zadd(
            self._z_key(thread_id, ns), {cid: checkpoint_score(cid)}
        )
        pipe.sadd(self._ns_key(thread_id), ns)
        pipe.sadd(self._threads_key(), thread_id)
        self._apply_ttl(
            pipe,
            [cp_key, self._z_key(thread_id, ns), self._ns_key(thread_id),
             self._threads_key(), *blob_keys],
        )
        await pipe.execute()

        return {
            "configurable": {
                "thread_id": thread_id,
                "checkpoint_ns": ns,
                "checkpoint_id": cid,
            }
        }

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        thread_id = config["configurable"]["thread_id"]
        ns = config["configurable"].get("checkpoint_ns", "")
        cid = config["configurable"]["checkpoint_id"]

        w_key = self._w_key(thread_id, ns, cid)
        seen_key = f"{w_key}:seen"
        seq_key = f"{w_key}:seq"

        for index, (channel, value) in enumerate(writes):
            slot = WRITES_IDX_MAP.get(channel, index)
            marker = f"{task_id}|{slot}"
            if slot >= 0 and await self.redis.sismember(seen_key, marker):
                continue
            seq = await self.redis.incr(seq_key)
            member = json.dumps(
                [
                    task_id,
                    channel,
                    pack_typed(self.serde.dumps_typed(value)),
                    task_path,
                    slot,
                ]
            )
            pipe = self.redis.pipeline()
            pipe.zadd(w_key, {member: seq})
            pipe.sadd(seen_key, marker)
            self._apply_ttl(pipe, [w_key, seen_key, seq_key])
            await pipe.execute()

    async def adelete_thread(self, thread_id: str) -> None:
        keys: list[str] = []
        namespaces = await self.redis.smembers(self._ns_key(thread_id))
        for ns in namespaces:
            cids = await self.redis.zrange(self._z_key(thread_id, ns), 0, -1)
            for cid in cids:
                w_key = self._w_key(thread_id, ns, cid)
                keys.extend(
                    [
                        self._cp_key(thread_id, ns, cid),
                        w_key,
                        f"{w_key}:seen",
                        f"{w_key}:seq",
                    ]
                )
            keys.append(self._z_key(thread_id, ns))
        keys.append(self._ns_key(thread_id))
        blob_keys = await self.redis.smembers(self._blob_index_key(thread_id))
        keys.extend(blob_keys)
        keys.append(self._blob_index_key(thread_id))

        if keys:
            await self.redis.delete(*keys)
        await self.redis.srem(self._threads_key(), thread_id)

    def get_next_version(self, current: str | None, channel: None) -> str:
        if current is None:
            current_v = 0
        elif isinstance(current, int):
            current_v = current
        else:
            current_v = int(str(current).split(".")[0])
        return f"{current_v + 1:032}.{random.random():016}"
