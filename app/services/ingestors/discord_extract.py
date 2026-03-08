#!/usr/bin/env python3
"""
Discord HTML Announcements → Markdown Extractor
------------------------------------------------
Usage:
    python discord_extract.py                  # traite tous les .html du dossier courant
    python discord_extract.py -i ./html_files  # dossier source personnalisé
    python discord_extract.py -o ./output_dir  # dossier de sortie personnalisé

Résultat :
    Un dossier "annonces_md/" contenant un fichier .md par fichier .html
    + un fichier index.md avec la table des matières
"""

import os
import sys
import glob
import argparse
from pathlib import Path
from datetime import datetime

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Installation de BeautifulSoup4...")
    os.system(f"{sys.executable} -m pip install beautifulsoup4 --quiet")
    from bs4 import BeautifulSoup


# ─────────────────────────────────────────────
# NOM DU CHANNEL DEPUIS LE NOM DE FICHIER
# ─────────────────────────────────────────────

def channel_from_filename(filepath: str) -> str:
    """Le nom du fichier (sans extension) = nom du channel."""
    return "#" + Path(filepath).stem


# ─────────────────────────────────────────────
# PARSING DES MESSAGES
# ─────────────────────────────────────────────

def extract_messages(html_path: str) -> list:
    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f, "html.parser")

    messages = []

    msg_groups = soup.select(
        ".chatlog__message-group, .message-group, [class*='messageGroup']"
    )
    if not msg_groups:
        msg_groups = soup.select(
            ".chatlog__message, .message, [class*='message_']"
        )

    for group in msg_groups:
        # Auteur
        author_tag = group.select_one(
            ".chatlog__author-name, .author, [class*='author'], [class*='username']"
        )
        author = author_tag.get_text(strip=True) if author_tag else "Inconnu"

        # Timestamp
        time_tag = group.select_one(
            "time, .chatlog__timestamp, [class*='timestamp'], [datetime]"
        )
        timestamp = ""
        if time_tag:
            timestamp = time_tag.get("datetime", "") or time_tag.get_text(strip=True)

        # Titre embed Discord
        embed_title = ""
        embed_tag = group.select_one(
            "[class*='embed-title'], [class*='embedTitle'], [class*='embed_title']"
        )
        if embed_tag:
            embed_title = embed_tag.get_text(strip=True)

        # Contenu
        content_tags = group.select(
            ".chatlog__content, .message-content, [class*='messageContent'], [class*='content_']"
        )
        if not content_tags:
            content_tags = [group]

        for ct in content_tags:
            text = ct.get_text(separator="\n", strip=True)
            if not text or len(text) < 2:
                continue
            messages.append({
                "author":    author,
                "timestamp": timestamp,
                "title":     embed_title,
                "content":   text,
            })

    return messages


# ─────────────────────────────────────────────
# FORMATAGE MARKDOWN — UN FICHIER PAR CHANNEL
# ─────────────────────────────────────────────

def format_timestamp(raw: str) -> str:
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y — %H:%M UTC")
    except Exception:
        return raw


def build_channel_markdown(channel: str, messages: list, source_file: str) -> str:
    lines = []

    lines.append(f"# {channel}")
    lines.append(f"**Source :** `{Path(source_file).name}`")
    lines.append(f"**Extraction :** {datetime.now().strftime('%d %b %Y à %H:%M')}")
    lines.append(f"**Messages :** {len(messages)}\n")
    lines.append("---\n")

    if not messages:
        lines.append("> ⚠️ Aucun message trouvé dans ce fichier.\n")
        return "\n".join(lines)

    for i, msg in enumerate(messages, 1):
        ts = format_timestamp(msg["timestamp"])

        # Titre du message
        heading = f"## [{i}]"
        if msg["title"]:
            heading += f" {msg['title']}"
        lines.append(heading)

        lines.append(f"**Auteur :** {msg['author']}")
        if ts:
            lines.append(f"**Date :** {ts}")
        lines.append("")

        # Contenu
        for line in msg["content"].split("\n"):
            lines.append(line)

        lines.append("\n---\n")

    return "\n".join(lines)


def build_index_markdown(entries: list) -> str:
    """Génère un index.md avec liens vers chaque fichier channel."""
    lines = []
    lines.append("# 📢 Annonces Discord — Index\n")
    lines.append(f"*Généré le {datetime.now().strftime('%d %b %Y à %H:%M')}*")
    lines.append(f"*{len(entries)} channel(s) exporté(s)*\n")
    lines.append("---\n")
    lines.append("| Channel | Fichier | Messages |")
    lines.append("|---------|---------|----------|")
    for e in entries:
        lines.append(f"| {e['channel']} | [{e['md_file']}]({e['md_file']}) | {e['count']} |")
    lines.append("")
    return "\n".join(lines)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extrait les annonces Discord de fichiers HTML → un .md par channel"
    )
    parser.add_argument("files", nargs="*", help="Fichiers HTML à traiter")
    parser.add_argument("-i", "--input-dir", default="annonces", help="Dossier source")
    parser.add_argument("-o", "--output-dir", default="annonces_md", help="Dossier de sortie")
    args = parser.parse_args()

    # Résolution des fichiers
    if args.files:
        html_files = []
        for pattern in args.files:
            html_files.extend(glob.glob(pattern))
    else:
        html_files = (
            glob.glob(os.path.join(args.input_dir, "*.html")) +
            glob.glob(os.path.join(args.input_dir, "*.HTML"))
        )

    html_files = sorted(set(html_files))

    if not html_files:
        print("❌ Aucun fichier .html trouvé.")
        print(f"   Dossier cherché : {os.path.abspath(args.input_dir)}")
        sys.exit(1)

    # Création du dossier de sortie
    out_dir = args.output_dir
    os.makedirs(out_dir, exist_ok=True)
    print(f"📁 Dossier de sortie : {os.path.abspath(out_dir)}")
    print(f"📂 {len(html_files)} fichier(s) trouvé(s)\n")

    index_entries = []

    for html_file in html_files:
        channel = channel_from_filename(html_file)
        stem    = Path(html_file).stem
        md_name = stem + ".md"
        md_path = os.path.join(out_dir, md_name)

        print(f"🔍 {channel}  ←  {Path(html_file).name}")

        try:
            messages = extract_messages(html_file)
            print(f"   ✅ {len(messages)} message(s)  →  {md_name}")
        except Exception as e:
            print(f"   ❌ Erreur : {e}")
            messages = []

        # Écriture du fichier individuel
        md_content = build_channel_markdown(channel, messages, html_file)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        index_entries.append({
            "channel":  channel,
            "md_file":  md_name,
            "count":    len(messages),
        })

    # Écriture de l'index
    index_path = os.path.join(out_dir, "index.md")
    with open(index_path, "w", encoding="utf-8") as f:
        f.write(build_index_markdown(index_entries))

    print(f"\n✅ Terminé !")
    print(f"   📁 Dossier  : {os.path.abspath(out_dir)}/")
    print(f"   📄 Index    : index.md")
    for e in index_entries:
        print(f"   📄 {e['md_file']}  ({e['count']} messages)")


if __name__ == "__main__":
    main()
