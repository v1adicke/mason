"""Global Obsidian Vault search and read tools"""

from __future__ import annotations

from pathlib import Path

from ...config import get_settings

_MAX_RESULTS = 25
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


def replace_in_note(filepath: str = "", old_text: str = "", new_text: str = "") -> str:
    """Replace the first occurrence of old_text with new_text in a vault .md file"""
    clean_path = filepath.strip()
    if not clean_path:
        return "Не указан путь к заметке."
    if not old_text:
        return "Ошибка: old_text не может быть пустым."

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
        return "Разрешено редактировать только .md файлы."

    if not target.is_file():
        return f"Файл не найден: {clean_path}"

    try:
        content = target.read_text(encoding="utf-8")
    except OSError as error:
        return f"Ошибка чтения файла: {error}"

    if old_text not in content:
        return "Ошибка: old_text не найден в файле. Проверь точное совпадение."

    updated = content.replace(old_text, new_text, 1)

    try:
        target.write_text(updated, encoding="utf-8")
    except OSError as error:
        return f"Ошибка записи файла: {error}"

    return f"Готово: первое вхождение заменено в «{clean_path}»."


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


def rename_note(current_filepath: str, new_filename: str) -> str:
    """Rename an existing vault note in place"""
    clean_current_path = current_filepath.strip()
    if not clean_current_path:
        return "Ошибка: Исходный файл не найден"

    clean_new_name = new_filename.strip()
    if not clean_new_name:
        return "Ошибка: Файл с таким именем уже существует"

    if Path(clean_new_name).name != clean_new_name:
        return "Ошибка: new_filename должен быть именем файла без пути"

    if not clean_new_name.lower().endswith(".md"):
        clean_new_name = f"{clean_new_name}.md"

    vault_root = Path(get_settings().obsidian_vault_root).resolve()

    try:
        source_path = (vault_root / clean_current_path).resolve()
    except (ValueError, OSError) as error:
        return f"Некорректный путь: {error}"

    try:
        source_path.relative_to(vault_root)
    except ValueError:
        return "Доступ запрещён: путь выходит за пределы Vault."

    if not source_path.is_file():
        return "Ошибка: Исходный файл не найден"

    target_path = source_path.parent / clean_new_name
    if target_path.exists():
        return "Ошибка: Файл с таким именем уже существует"

    try:
        source_path.rename(target_path)
    except OSError as error:
        return f"Ошибка файловой системы: {error}"

    return f"Файл успешно переименован в {clean_new_name}"
