#!/usr/bin/env python3
"""
Markdown Announcements → Embeddings → Qdrant (in-memory / local)
-----------------------------------------------------------------
Install (pas de compilation C++ nécessaire) :
    uv pip install qdrant-client sentence-transformers numpy

Usage:
    python embed_to_vectordb.py                        # lit ./annonces_md/*.md
    python embed_to_vectordb.py -i ./annonces_md       # dossier source
    python embed_to_vectordb.py --provider openai      # OpenAI embeddings
    python embed_to_vectordb.py --query "patch notes"  # recherche après ingestion
    python embed_to_vectordb.py --query "mise a jour" --reindex  # réindexe + recherche
"""

import os
import re
import sys
import glob
import json
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime


# ─────────────────────────────────────────────
# INSTALL AUTO
# ─────────────────────────────────────────────

def pip_install(pkg):
    os.system(f"{sys.executable} -m pip install {pkg} --quiet")

def ensure_deps(provider):
    try:
        from qdrant_client import QdrantClient
    except ImportError:
        print("📦 Installation de qdrant-client...")
        pip_install("qdrant-client")

    try:
        import numpy
    except ImportError:
        pip_install("numpy")

    if provider == "local":
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            print("📦 Installation de sentence-transformers...")
            pip_install("sentence-transformers")
    else:
        try:
            import openai
        except ImportError:
            print("📦 Installation de openai...")
            pip_install("openai")


# ─────────────────────────────────────────────
# PARSING MARKDOWN
# ─────────────────────────────────────────────

def parse_markdown_file(md_path: str) -> list:
    with open(md_path, "r", encoding="utf-8") as f:
        content = f.read()

    source_file = Path(md_path).name
    channel = ""

    h1 = re.search(r"^# (.+)$", content, re.MULTILINE)
    if h1:
        channel = h1.group(1).strip()

    chunks = []
    blocks = re.split(r"\n## \[(\d+)\]", content)

    i = 1
    while i < len(blocks) - 1:
        msg_num = blocks[i].strip()
        block   = blocks[i + 1] if i + 1 < len(blocks) else ""
        i += 2

        lines         = block.strip().split("\n")
        title         = ""
        author        = ""
        date          = ""
        content_lines = []
        in_content    = False

        for line in lines:
            if line.startswith("**Auteur :**"):
                author = line.replace("**Auteur :**", "").strip()
            elif line.startswith("**Date :**"):
                date = line.replace("**Date :**", "").strip()
            elif line.strip() == "---":
                continue
            elif author and date and not in_content and line.strip() == "":
                in_content = True
            elif in_content:
                content_lines.append(line)
            elif not author and not date and line.strip():
                title += line.strip() + " "

        text_content = "\n".join(content_lines).strip()
        text_content = re.sub(r"\n---\s*$", "", text_content).strip()

        if not text_content:
            continue

        full_text = ""
        if title.strip():
            full_text += f"Titre: {title.strip()}\n"
        full_text += f"Auteur: {author}\n"
        full_text += f"Channel: {channel}\n"
        full_text += f"Date: {date}\n"
        full_text += f"Contenu:\n{text_content}"

        chunks.append({
            "id":      f"{source_file}__msg{msg_num}",
            "text":    full_text,
            "channel": channel,
            "author":  author,
            "date":    date,
            "title":   title.strip(),
            "content": text_content,
            "source":  source_file,
        })

    return chunks


# ─────────────────────────────────────────────
# EMBEDDINGS
# ─────────────────────────────────────────────

MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"  # 384 dims, supporte FR

def embed_local(texts: list) -> list:
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_NAME)
    vecs  = model.encode(texts, show_progress_bar=True, normalize_embeddings=True)
    return vecs.tolist()

def embed_openai(texts: list) -> list:
    import openai
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY non définie.")
        print("   Windows PowerShell : $env:OPENAI_API_KEY='sk-...'")
        sys.exit(1)
    client  = openai.OpenAI(api_key=api_key)
    all_vecs = []
    batch   = 100
    for i in range(0, len(texts), batch):
        resp = client.embeddings.create(
            model="text-embedding-3-small",
            input=texts[i:i+batch]
        )
        all_vecs.extend([e.embedding for e in resp.data])
        print(f"   embedded {min(i+batch, len(texts))}/{len(texts)}")
    return all_vecs

def get_vector_size(provider: str) -> int:
    return 384 if provider == "local" else 1536


# ─────────────────────────────────────────────
# QDRANT
# ─────────────────────────────────────────────

COLLECTION = "discord_annonces"

def get_client(db_path: str):
    from qdrant_client import QdrantClient
    os.makedirs(db_path, exist_ok=True)
    return QdrantClient(path=db_path)  # stockage local sur disque

def create_collection(client, vector_size: int):
    from qdrant_client.models import Distance, VectorParams
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION in existing:
        client.delete_collection(COLLECTION)
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )

def upsert_chunks(client, chunks: list, vectors: list):
    from qdrant_client.models import PointStruct
    points = []
    for i, (chunk, vec) in enumerate(zip(chunks, vectors)):
        points.append(PointStruct(
            id=i,
            vector=vec,
            payload={
                "id":      chunk["id"],
                "channel": chunk["channel"],
                "author":  chunk["author"],
                "date":    chunk["date"],
                "title":   chunk["title"],
                "content": chunk["content"][:1000],
                "source":  chunk["source"],
            }
        ))
    # batch upsert par 100
    batch = 100
    for start in range(0, len(points), batch):
        client.upsert(
            collection_name=COLLECTION,
            points=points[start:start+batch]
        )
        print(f"   💾 {min(start+batch, len(points))}/{len(points)} insérés")


def search_qdrant(client, query_vec: list, n: int = 5):
    results = client.search(
        collection_name=COLLECTION,
        query_vector=query_vec,
        limit=n,
    )
    return results


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Embed .md Discord → Qdrant (local)")
    parser.add_argument("-i", "--input-dir", default="annonces_md", help="Dossier des .md")
    parser.add_argument("-d", "--db-dir",    default="qdrant_db",   help="Dossier DB Qdrant")
    parser.add_argument("--provider",        default="local",       choices=["local", "openai"])
    parser.add_argument("--query",           default=None,          help="Recherche sémantique")
    parser.add_argument("-n", "--n-results", default=5, type=int)
    parser.add_argument("--reindex",         action="store_true",   help="Forcer la réindexation")
    args = parser.parse_args()

    ensure_deps(args.provider)

    from qdrant_client import QdrantClient

    client = get_client(args.db_dir)

    # ── Mode recherche seule ──
    existing = [c.name for c in client.get_collections().collections]
    if args.query and not args.reindex and COLLECTION in existing:
        count = client.count(COLLECTION).count
        print(f"✅ Collection chargée : {count} vecteurs\n")
        print("⚙️  Calcul embedding de la requête...")
        if args.provider == "local":
            qvec = embed_local([args.query])[0]
        else:
            qvec = embed_openai([args.query])[0]

        results = search_qdrant(client, qvec, args.n_results)
        print(f"🔍 Résultats pour : \"{args.query}\"\n")
        print("=" * 60)
        for rank, r in enumerate(results, 1):
            p = r.payload
            print(f"\n[{rank}] Score: {r.score:.3f}  |  {p['channel']}  |  {p['author']}  |  {p['date']}")
            if p.get("title"):
                print(f"    📌 {p['title']}")
            print(f"    {p['content'][:250].replace(chr(10), ' ')}...")
            print("-" * 40)
        return

    # ── Lecture des .md ──
    md_files = sorted(glob.glob(os.path.join(args.input_dir, "*.md")))
    md_files = [f for f in md_files if Path(f).name != "index.md"]

    if not md_files:
        print(f"❌ Aucun .md trouvé dans : {os.path.abspath(args.input_dir)}")
        sys.exit(1)

    print(f"📂 {len(md_files)} fichier(s) .md\n")

    all_chunks = []
    for md in md_files:
        c = parse_markdown_file(md)
        print(f"📄 {Path(md).name:40s} → {len(c)} chunks")
        all_chunks.extend(c)

    print(f"\n📊 Total : {len(all_chunks)} chunks\n")

    # ── Embeddings ──
    texts = [c["text"] for c in all_chunks]
    provider_label = f"sentence-transformers ({MODEL_NAME})" if args.provider == "local" else "OpenAI text-embedding-3-small"
    print(f"⚙️  Calcul des embeddings ({provider_label})...")

    if args.provider == "local":
        vectors = embed_local(texts)
    else:
        vectors = embed_openai(texts)

    # ── Collection Qdrant ──
    print(f"\n🗄️  Création de la collection Qdrant...")
    create_collection(client, get_vector_size(args.provider))
    upsert_chunks(client, all_chunks, vectors)

    count = client.count(COLLECTION).count
    print(f"\n✅ {count} vecteurs stockés dans {os.path.abspath(args.db_dir)}/")

    # Stats
    print("\n📊 Stats par channel :")
    channels = {}
    for c in all_chunks:
        channels[c["channel"]] = channels.get(c["channel"], 0) + 1
    for ch, n in sorted(channels.items()):
        print(f"   {ch:35s} {n} chunks")

    # ── Recherche optionnelle ──
    if args.query:
        if args.provider == "local":
            qvec = embed_local([args.query])[0]
        else:
            qvec = embed_openai([args.query])[0]
        results = search_qdrant(client, qvec, args.n_results)
        print(f"\n🔍 Résultats pour : \"{args.query}\"\n{'='*60}")
        for rank, r in enumerate(results, 1):
            p = r.payload
            print(f"\n[{rank}] Score: {r.score:.3f}  |  {p['channel']}  |  {p['author']}  |  {p['date']}")
            if p.get("title"):
                print(f"    📌 {p['title']}")
            print(f"    {p['content'][:250].replace(chr(10), ' ')}...")
            print("-" * 40)
    else:
        print(f'\n💡 Recherche : python embed_to_vectordb.py --query "ton texte"')


if __name__ == "__main__":
    main()
