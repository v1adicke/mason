"""Global Obsidian Vault search and read tools"""

from __future__ import annotations

from pathlib import Path

from ...config import get_settings

_MAX_RESULTS = 10
_SNIPPET_RADIUS = 100
_MAX_NOTE_CHARS = 50_000
_TRUNCATION_WARNING = "\n\n[...Заметка обрезана: превышен лимит в 50 000 символов...]"


def search_vault(query: str = "") -> str:
    """Search all .md files in the vault for query (filename + content, case-insensitive)"""
    clean_query = query.strip()
    if not clean_query:
        return "Не указан поисковый запрос."

    vault_root = Path(get_settings().obsidian_vault_root)
    if not vault_root.is_dir():
        return f"Vault root не найден: {vault_root}"

    lower_query = clean_query.lower()
    matches: list[str] = []

    try:
        for md_file in sorted(vault_root.rglob("*.md")):
            if len(matches) >= _MAX_RESULTS:
                break

            rel_path = md_file.relative_to(vault_root)
            rel_str = rel_path.as_posix()

            if lower_query in rel_str.lower():
                matches.append(f"📄 {rel_str}\n   (совпадение в пути)")
                continue

            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue

            lower_content = content.lower()
            idx = lower_content.find(lower_query)
            if idx == -1:
                continue

            start = max(0, idx - _SNIPPET_RADIUS)
            end = min(len(content), idx + len(clean_query) + _SNIPPET_RADIUS)
            snippet = content[start:end].replace("\n", " ").strip()
            if start > 0:
                snippet = "..." + snippet
            if end < len(content):
                snippet = snippet + "..."

            matches.append(f"📄 {rel_str}\n   «{snippet}»")

    except OSError as error:
        return f"Ошибка файловой системы при поиске: {error}"

    if not matches:
        return f"По запросу «{clean_query}» ничего не найдено."

    header = f"Найдено {len(matches)} результат(ов) по запросу «{clean_query}»:\n"
    return header + "\n\n".join(matches)


def read_note(filepath: str = "") -> str:
    """Read and return the content of a .md file relative to the vault root"""
    clean_path = filepath.strip()
    if not clean_path:
        return "Не указан путь к заметке."

    vault_root = Path(get_settings().obsidian_vault_root).resolve()

    try:
        target = (vault_root / clean_path).resolve()
    except (ValueError, OSError) as error:
        return f"Некорректный путь: {error}"

    try:
        target.relative_to(vault_root)
    except ValueError:
        return "Доступ запрещён: путь выходит за пределы Vault."

    if not target.suffix.lower() == ".md":
        return "Разрешено читать только .md файлы."

    if not target.is_file():
        return f"Файл не найден: {clean_path}"

    try:
        content = target.read_text(encoding="utf-8", errors="ignore")
    except OSError as error:
        return f"Ошибка чтения файла: {error}"

    if len(content) > _MAX_NOTE_CHARS:
        return content[:_MAX_NOTE_CHARS] + _TRUNCATION_WARNING

    return content
