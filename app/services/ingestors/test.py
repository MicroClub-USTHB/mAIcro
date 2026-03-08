

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
# FORMATAGE MARKDOWN
# ─────────────────────────────────────────────

def format_timestamp(raw: str) -> str:
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%d %b %Y — %H:%M UTC")
    except Exception:
        return raw


def section_to_markdown(channel: str, messages: list) -> str:
    lines = []
    lines.append(f"# {channel}")
    lines.append(f"*{len(messages)} message(s)*\n")
    lines.append("---\n")

    if not messages:
        lines.append("> ⚠️ Aucun message trouvé.\n")
        return "\n".join(lines)

    for i, msg in enumerate(messages, 1):
        ts = format_timestamp(msg["timestamp"])

        heading = f"## [{i}]"
        if msg["title"]:
            heading += f" {msg['title']}"
        lines.append(heading)

        lines.append(f"**Auteur :** {msg['author']}")
        if ts:
            lines.append(f"**Date :** {ts}")
        lines.append("")

        for line in msg["content"].split("\n"):
            lines.append(line)

        lines.append("\n---\n")

    return "\n".join(lines)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Extrait les annonces Discord de fichiers HTML → Markdown"
    )
    parser.add_argument("files", nargs="*", help="Fichiers HTML à traiter")
    parser.add_argument("-i", "--input-dir", default=".", help="Dossier source")
    parser.add_argument("-o", "--output", default="discord_annonces.md", help="Fichier de sortie")
    args = parser.parse_args()

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

    print(f"📂 {len(html_files)} fichier(s) trouvé(s)\n")

    doc = []
    doc.append("# 📢 Annonces Discord\n")
    doc.append(f"*Généré le {datetime.now().strftime('%d %b %Y à %H:%M')} — {len(html_files)} channel(s)*\n")
    doc.append("---\n")

    # Table des matières
    doc.append("## 📋 Table des matières\n")
    for f in html_files:
        ch = channel_from_filename(f)
        doc.append(f"- [{ch}](#{ch[1:].lower()})")
    doc.append("\n---\n")

    # Une section par channel
    for html_file in html_files:
        channel = channel_from_filename(html_file)
        print(f"🔍 {channel}  ←  {html_file}")
        try:
            messages = extract_messages(html_file)
            print(f"   ✅ {len(messages)} message(s)")
        except Exception as e:
            print(f"   ❌ Erreur : {e}")
            messages = []

        doc.append(section_to_markdown(channel, messages))
        doc.append("\n\n")

    content = "\n".join(doc)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"\n✅ Fichier généré : {os.path.abspath(args.output)}")
    print(f"   Taille : {len(content):,} caractères")


if __name__ == "__main__":
    main()