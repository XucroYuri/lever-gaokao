#!/usr/bin/env python3
"""Gaokao 数据层 v1：招生章程 Laws 式分块（文档 RAG 层的文本预处理）。

招生章程与中文法律文档结构同构（总则→组织机构→招生计划→录取规则→收费标准→
附则，第X章/第X条）。本模块实现设计文档"文档 RAG 设计"中指定的 RAGFlow Laws
式分块：按章节树切分，每个 chunk 保留"章节标题路径"作为检索上下文。

用法：
    python scripts/data_rag.py chunk --input 章程.txt --output chunks.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

import duckdb

# 向量维度（vss 要求固定尺寸 FLOAT[N]；由实际嵌入器决定）
_EMBEDDER = None   # fastembed TextEmbedding 实例或 None（哈希回退）
_EMBED_DIM = None  # 当前嵌入维度（BGE=512，哈希=384）

# 章节/条款标记（与 RAGFlow laws.py 的正则一致）
_CHAPTER_RE = re.compile(r"第[零一二三四五六七八九十百千0-9]+章")
_ARTICLE_RE = re.compile(r"第[零一二三四五六七八九十百千0-9]+条")
_CN_DIGIT = {"零": 0, "一": 1, "二": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def _cn_to_int(text: str) -> int:
    """把中文数字（一、十二、二十三）转 int，用于章节排序。"""
    text = text.strip()
    if text.isdigit():
        return int(text)
    if "十" in text:
        parts = text.split("十")
        tens = _CN_DIGIT.get(parts[0], 1) if parts[0] else 1
        ones = _CN_DIGIT.get(parts[1], 0) if len(parts) > 1 and parts[1] else 0
        return tens * 10 + ones
    return _CN_DIGIT.get(text, 0)


def chunk_zhengcheng(text: str) -> list[dict]:
    """把招生章程文本按 第X章/第X条 分块，输出带章节路径的 chunk 列表。

    返回：[{"section_path": "第三章/第十二条", "chapter": "第三章 招生计划",
           "content": "...", "chunk_type": "article"}]
    """
    lines = text.splitlines()
    chunks: list[dict] = []
    cur_chapter: str | None = None
    cur_article: str | None = None
    buf: list[str] = []

    def flush() -> None:
        nonlocal buf, cur_chapter, cur_article
        content = "\n".join(buf).strip()
        if content and cur_article:
            path = f"{cur_chapter}/{cur_article}" if cur_chapter else cur_article
            chunks.append({
                "section_path": path,
                "chapter": cur_chapter or "",
                "article": cur_article,
                "content": content,
                "chunk_type": "article",
            })
        buf = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        m_ch = _CHAPTER_RE.search(stripped)
        m_ar = _ARTICLE_RE.search(stripped)
        if m_ch and (not m_ar or m_ch.start() <= m_ar.start()):
            flush()
            cur_chapter = stripped
            cur_article = None
        elif m_ar:
            # 条款：第X条（正文可能同行）
            flush()
            cur_article = stripped[:m_ar.end()].strip()
            rest = stripped[m_ar.end():].strip()
            if rest:
                buf.append(rest)
        else:
            if cur_article is not None:
                buf.append(stripped)
            elif cur_chapter is not None:
                # 章节标题下的引导性正文（无条款号），挂到章节级 chunk
                buf.append(stripped)
    flush()
    return chunks


def chunk_cmd(args: argparse.Namespace) -> None:
    text = Path(args.input).read_text(encoding="utf-8", errors="ignore")
    chunks = chunk_zhengcheng(text)

    # 统计章节与条款
    chapters = sorted({c["chapter"] for c in chunks if c["chapter"]},
                      key=lambda s: _cn_to_int(_CHAPTER_RE.search(s).group(0)[1:-1]))
    out = {
        "input": args.input,
        "chunk_count": len(chunks),
        "chapters": chapters,
        "chunks": chunks,
    }
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"分块完成: {len(chunks)} 个 chunk，{len(chapters)} 章 -> {out_path}")
    print(f"章节: {' / '.join(chapters)}")


def _hash_embed(text: str, dim: int = 384) -> list[float]:
    """确定性特征哈希嵌入（字符二元组 -> 固定维度向量，L2 归一化）。

    作为 fastembed BGE 模型不可用时的离线回退：字符二元组捕获一定的中文词汇
    相似性，能跑通"嵌入 -> 存储 -> 检索"全链路。
    """
    vec = [0.0] * dim
    for i in range(len(text) - 1):
        bigram = text[i:i + 2]
        h = int.from_bytes(hashlib.md5(bigram.encode("utf-8")).digest()[:4], "little")
        idx = h % dim
        sign = 1.0 if (h >> 12) & 1 else -1.0
        vec[idx] += sign
    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        vec = [x / norm for x in vec]
    return vec


def _vec_literal(vec: list[float], dim: int | None = None) -> str:
    """把向量格式化为 DuckDB FLOAT[N] 字面量。"""
    if dim is None:
        dim = _EMBED_DIM or 384
    return "[" + ",".join(f"{x:.6f}" for x in vec) + f"]::FLOAT[{dim}]"


def _init_embedder() -> int:
    """初始化嵌入器：优先 fastembed BGE-small-zh（512 维），失败回退哈希（384 维）。"""
    global _EMBEDDER, _EMBED_DIM
    if _EMBED_DIM is not None:
        return _EMBED_DIM
    try:
        from fastembed import TextEmbedding
        m = TextEmbedding(model_name="BAAI/bge-small-zh-v1.5")
        _EMBEDDER = m
        _EMBED_DIM = 512
        print("[embedder] BGE-small-zh-v1.5（512 维，语义嵌入）")
    except Exception as exc:
        _EMBEDDER = None
        _EMBED_DIM = 384
        print(f"[embedder] BGE 模型不可用，回退哈希占位嵌入（384 维）: {exc}")
    return _EMBED_DIM


def _embed(text: str) -> list[float]:
    """用当前嵌入器嵌入单段文本；BGE 失败时回退哈希。"""
    _init_embedder()
    if _EMBEDDER is not None:
        try:
            v = list(_EMBEDDER.embed([text]))[0]
            return [float(x) for x in v]
        except Exception:
            pass  # 回退哈希
    return _hash_embed(text, _EMBED_DIM)


def _vss_setup(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("INSTALL vss")
    con.execute("LOAD vss")
    con.execute("SET hnsw_enable_experimental_persistence = true")


def embed_cmd(args: argparse.Namespace) -> None:
    """把章程文本分块 + 嵌入 + 存 DuckDB vss（HNSW 索引）。"""
    dim = _init_embedder()
    text = Path(args.input).read_text(encoding="utf-8", errors="ignore")
    chunks = chunk_zhengcheng(text)
    if not chunks:
        raise SystemExit("未分块出任何条款，请检查输入文本是否为招生章程格式")

    db_path = Path(args.db)
    con = duckdb.connect(str(db_path))
    _vss_setup(con)

    con.execute(
        f"CREATE OR REPLACE TABLE zhengcheng_chunks ("
        f"id INTEGER, section_path VARCHAR, chapter VARCHAR, article VARCHAR, "
        f"content VARCHAR, vec FLOAT[{dim}])"
    )
    for i, c in enumerate(chunks):
        vec = _embed(c["content"])
        con.execute(
            f"INSERT INTO zhengcheng_chunks VALUES (?,?,?,?,?,{_vec_literal(vec)})",
            [i, c["section_path"], c["chapter"], c["article"], c["content"]],
        )
    try:
        con.execute("CREATE INDEX IF NOT EXISTS zhengcheng_hnsw ON zhengcheng_chunks USING HNSW (vec)")
        indexed = True
    except Exception:
        indexed = False
    con.close()

    embedder_name = "BGE-small-zh-v1.5（语义）" if _EMBEDDER else "特征哈希（占位）"
    print(f"嵌入完成: {len(chunks)} 个 chunk（{dim} 维，{embedder_name}）")
    print(f"HNSW 索引: {'已建立' if indexed else '建立失败（退回暴力检索）'}")


def search_cmd(args: argparse.Namespace) -> None:
    """用查询向量检索最相似的章程条款（top-k）。"""
    dim = _init_embedder()
    db_path = Path(args.db)
    con = duckdb.connect(str(db_path), read_only=True)
    _vss_setup(con)
    q_vec = _embed(args.query)
    rows = con.execute(
        f"SELECT section_path, content, array_cosine_distance(vec, {_vec_literal(q_vec, dim)}) AS dist "
        f"FROM zhengcheng_chunks ORDER BY dist LIMIT ?",
        [args.top_k],
    ).fetchall()
    con.close()

    embedder_name = "BGE-small-zh-v1.5（语义）" if _EMBEDDER else "特征哈希（占位）"
    print(f"查询: {args.query}（top-{args.top_k}，{embedder_name}，cosine 距离越小越相似）\n")
    for i, (path, content, dist) in enumerate(rows, 1):
        print(f"#{i} [{path}] 距离={dist:.4f}")
        print(f"   {content[:80]}{'...' if len(content) > 80 else ''}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="招生章程 Laws 式分块 + RAG 检索")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("chunk", help="对章程文本做章节树分块")
    p.add_argument("--input", required=True)
    p.add_argument("--output", default="data/reports/chunks.json")
    p.set_defaults(func=chunk_cmd)

    p_embed = sub.add_parser("embed", help="分块 + 嵌入 + 存 vss 向量库")
    p_embed.add_argument("--input", required=True, help="章程文本文件")
    p_embed.add_argument("--db", default="data/gaokao.duckdb")
    p_embed.set_defaults(func=embed_cmd)

    p_search = sub.add_parser("search", help="检索最相似章程条款")
    p_search.add_argument("--query", required=True)
    p_search.add_argument("--db", default="data/gaokao.duckdb")
    p_search.add_argument("--top-k", default=5, type=int)
    p_search.set_defaults(func=search_cmd)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
