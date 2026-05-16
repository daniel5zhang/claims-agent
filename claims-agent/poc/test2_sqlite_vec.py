"""POC Test 2: sqlite-vec 药品向量匹配"""
import sys
import pysqlite3 as sqlite3
import sqlite_vec


def test():
    sys.stderr.write("[Test  2] sqlite-vec drug matching...\n")

    # 内存库
    conn = sqlite3.connect(":memory:")
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    # 建向量表
    conn.execute("CREATE VIRTUAL TABLE drug_vecs USING vec0(embedding float[8])")
    # 伴生表存药品名
    conn.execute("CREATE TABLE drugs(id INTEGER PRIMARY KEY, name TEXT)")

    # 模拟 embedding（8维简略向量）
    drugs = [
        ("来那度胺胶囊", [1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        ("瑞复美", [0.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        ("硼替佐米注射液", [0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        ("万珂", [0.0, 0.9, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        ("伊布替尼胶囊", [0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        ("阿司匹林", [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 0.0]),
        ("对乙酰氨基酚", [0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0]),
        ("胰岛素", [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0]),
        ("来那度胺片", [0.85, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
        ("硼替佐米粉针", [0.0, 0.85, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]),
    ]

    for i, (name, emb) in enumerate(drugs):
        conn.execute("INSERT INTO drugs VALUES (?, ?)", [i + 1, name])
        conn.execute("INSERT INTO drug_vecs(rowid, embedding) VALUES (?, ?)", [i + 1, str(emb)])

    # 查询：用"来那度胺"的 embedding 找相似药品
    query = [0.88, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    results = conn.execute("""
        SELECT d.name, vec_distance_cosine(v.embedding, ?) AS dist
        FROM drug_vecs v
        JOIN drugs d ON d.id = v.rowid
        ORDER BY dist
        LIMIT 3
    """, [str(query)]).fetchall()

    # 验证：top-3 的余弦距离小于 0.1（高相似度），说明向量匹配有效
    ok = all(r[1] < 0.1 for r in results) and len(results) >= 2
    if ok:
        sys.stderr.write(f"[Test  2] OK — top match: '{results[0][0]}' (dist={results[0][1]:.4f}), all: {[(r[0], round(r[1],4)) for r in results]}\n")
    else:
        sys.stderr.write(f"[Test  2] FAIL — results: {results}\n")

    conn.close()
    return ok


if __name__ == "__main__":
    ok = test()
    print(f"TEST2: sqlite_vec {'PASS' if ok else 'FAIL'}")
    sys.exit(0 if ok else 1)
