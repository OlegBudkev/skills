#!/usr/bin/env python3
import os
import sys
import re
import math

# Набор опасных ключевых слов и регулярных выражений для проверки
SUSPICIOUS_PATTERNS = {
    "shell_exec": {
        "title": "Выполнение команд оболочки / процессов",
        "patterns": [
            (r"os\.system\s*\(", "Python: os.system()"),
            (r"os\.popen\s*\(", "Python: os.popen()"),
            (r"subprocess\.(?:Popen|run|call|check_output|check_call)\s*\(", "Python: subprocess call"),
            (r"pty\.spawn\s*\(", "Python: pty.spawn()"),
            (r"\beval\s*\(", "Вызов eval() (динамическое выполнение кода)"),
            (r"\bexec\s*\(", "Вызов exec() (динамическое выполнение кода)"),
            (r"child_process\.(?:exec|spawn|fork|execFile|execSync|spawnSync)", "JS/TS: child_process call"),
            (r"new\s+Function\s*\(", "JS/TS: new Function() (динамический код)"),
            (r"\bpowershell\b", "Упоминание PowerShell"),
            (r"\bcmd\.exe\b", "Упоминание cmd.exe"),
            (r"/bin/(?:sh|bash|zsh)", "Путь к Unix shell"),
        ]
    },
    "network": {
        "title": "Сетевая активность",
        "patterns": [
            (r"\brequests\.(?:get|post|put|delete|patch|head|options|request)\s*\(", "Python: requests API call"),
            (r"\burllib\.request", "Python: urllib.request"),
            (r"\bhttp\.client\b", "Python: http.client"),
            (r"\bsocket\b", "Python: библиотека socket"),
            (r"\bhttpx\.(?:get|post|put|delete|client|Client|AsyncClient)\b", "Python: httpx API call"),
            (r"\baxios\b", "JS/TS: библиотека axios"),
            (r"\bfetch\s*\(", "JS/TS: вызов fetch()"),
            (r"\bhttp\.get\b|\bhttp\.request\b|\bhttps\.get\b|\bhttps\.request\b", "JS/TS: http/https modules"),
            (r"curl\s+", "Команда curl"),
            (r"wget\s+", "Команда wget"),
            (r"https?://(?:[0-9]{1,3}\.){3}[0-9]{1,3}", "Прямой URL с IP-адресом"),
            (r"https?://(?:pastebin|githubusercontent|ngrok|webhook|temp-mail|tempurl)", "Подозрительный хост или файлообменник"),
        ]
    },
    "secrets_and_sensitive_files": {
        "title": "Доступ к секретам и чувствительным путям",
        "patterns": [
            (r"\.env\b", "Упоминание файла .env"),
            (r"\.ssh\b|id_rsa|id_dsa|authorized_keys", "Доступ к SSH ключам"),
            (r"\.git\b", "Доступ к директории .git"),
            (r"\bos\.environ\b|\bos\.getenv\b", "Python: Доступ к переменным окружения"),
            (r"process\.env\b", "JS/TS: Доступ к переменным окружения"),
            (r"\b(?:secret|private|token|api_key|apikey|passwd|password)\b\s*[:=]\s*['\"][a-zA-Z0-9_\-]{8,}['\"]", "Возможный захардкоженный секрет/ключ"),
        ]
    }
}

# Расчет энтропии Шеннона для обнаружения обфусцированных/закодированных строк
def calculate_entropy(text):
    if not text:
        return 0
    entropy = 0
    for x in range(256):
        p_x = float(text.count(chr(x)))/len(text)
        if p_x > 0:
            entropy += - p_x * math.log(p_x, 2)
    return entropy

def scan_file(file_path):
    findings = []
    
    # Игнорируем бинарные файлы
    if file_path.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz', '.mp4', '.mp3', '.woff', '.woff2', '.ttf')):
        return findings

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        return [{"category": "error", "description": f"Не удалось прочитать файл: {str(e)}", "line_num": 0, "line_content": ""}]

    for idx, line in enumerate(lines, 1):
        # 1. Проверка по регулярным выражениям
        for cat_name, cat_info in SUSPICIOUS_PATTERNS.items():
            for pattern, desc in cat_info["patterns"]:
                if re.search(pattern, line, re.IGNORECASE):
                    # Проверяем, не является ли это просто комментарием (простой эвристический фильтр)
                    is_comment = line.strip().startswith(('#', '//', '*', '<!--'))
                    findings.append({
                        "category": cat_name,
                        "category_title": cat_info["title"],
                        "description": desc,
                        "line_num": idx,
                        "line_content": line.strip(),
                        "is_comment": is_comment
                    })

        # 2. Проверка на длинные обфусцированные строки (base64, hex и т.д.)
        # Ищем длинные непрерывные строки без пробелов
        long_strings = re.findall(r"['\"][a-zA-Z0-9+/=]{60,}['\"]", line)
        for ls in long_strings:
            clean_str = ls.strip("'\"")
            entropy = calculate_entropy(clean_str)
            # Высокая энтропия обычно указывает на случайные байты/шифрование/кодирование
            if entropy > 4.0:
                findings.append({
                    "category": "obfuscation",
                    "category_title": "Потенциальная обфускация / кодирование данных",
                    "description": f"Длинная строка (длина {len(clean_str)}, энтропия {entropy:.2f})",
                    "line_num": idx,
                    "line_content": line.strip()[:100] + "...",
                    "is_comment": False
                })

    return findings

def audit_directory(dir_path):
    all_findings = {}
    
    if not os.path.exists(dir_path):
        print(f"Ошибка: Путь {dir_path} не существует.")
        sys.exit(1)

    if os.path.isfile(dir_path):
        files_to_scan = [dir_path]
    else:
        files_to_scan = []
        for root, dirs, files in os.walk(dir_path):
            # Пропускаем служебные директории
            if '.git' in dirs:
                dirs.remove('.git')
            if 'node_modules' in dirs:
                dirs.remove('node_modules')
            if '__pycache__' in dirs:
                dirs.remove('__pycache__')
            
            for file in files:
                files_to_scan.append(os.path.join(root, file))

    for file_path in files_to_scan:
        rel_path = os.path.relpath(file_path, dir_path) if os.path.isdir(dir_path) else os.path.basename(file_path)
        # Пропускаем сам скрипт аудита, если он лежит в этой же директории
        if "audit_skill.py" in rel_path:
            continue
            
        file_findings = scan_file(file_path)
        if file_findings:
            all_findings[rel_path] = file_findings

    return all_findings

def print_report(findings, dir_path):
    print(f"# Отчет по безопасности для скилла: `{os.path.basename(os.path.abspath(dir_path))}`\n")
    
    if not findings:
        print("🟢 **Риск: LOW (Низкий)**")
        print("В ходе статического анализа подозрительных вызовов, секретов или признаков обфускации не обнаружено.")
        return

    # Подсчет количества находок по категориям
    counters = {"shell_exec": 0, "network": 0, "secrets_and_sensitive_files": 0, "obfuscation": 0, "error": 0}
    comment_count = 0
    
    for file, file_findings in findings.items():
        for f in file_findings:
            if f["is_comment"]:
                comment_count += 1
            else:
                counters[f["category"]] = counters.get(f["category"], 0) + 1

    # Определение уровня риска
    # shell_exec или obfuscation не в комментариях -> HIGH
    # network или secrets_and_sensitive_files не в комментариях -> MEDIUM
    # Только комментарии или отсутствие находок -> LOW (или LOW с примечанием)
    
    active_high = counters["shell_exec"] + counters["obfuscation"]
    active_medium = counters["network"] + counters["secrets_and_sensitive_files"]
    
    if active_high > 0:
        print("🔴 **Риск: HIGH (Высокий)**")
        print("Обнаружены опасные системные вызовы или потенциально обфусцированный код! **Крайне рекомендуется проверить исходный код вручную.**\n")
    elif active_medium > 0:
        print("🟡 **Риск: MEDIUM (Средний)**")
        print("Обнаружена сетевая активность или обращение к переменным окружения/конфигурационным файлам. Убедитесь, что это необходимо для работы скилла.\n")
    else:
        print("🟢 **Риск: LOW (Низкий)**")
        print("В ходе статического анализа подозрительного активного кода не обнаружено (найденные совпадения находятся в комментариях).\n")
        return

    # Сводная таблица
    print("## Сводка по категориям уязвимостей (активный код)")
    print("| Категория | Количество находок |")
    print("| :--- | :--- |")
    print(f"| Выполнение процессов / Shell | {counters['shell_exec']} |")
    print(f"| Сетевая активность | {counters['network']} |")
    print(f"| Доступ к секретам / файлам | {counters['secrets_and_sensitive_files']} |")
    print(f"| Подозрительные строки / Обфускация | {counters['obfuscation']} |")
    print(f"| Найдены в комментариях (проигнорировано) | {comment_count} |\n")

    print("## Детализация по файлам")
    for file, file_findings in findings.items():
        print(f"### Файл: `{file}`")
        print("| Строка | Категория | Описание | Содержимое | Статус |")
        print("| :--- | :--- | :--- | :--- | :--- |")
        for f in file_findings:
            escaped_content = f["line_content"].replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")
            # Обрезаем слишком длинное содержимое
            if len(escaped_content) > 80:
                escaped_content = escaped_content[:77] + "..."
            
            status = "💬 Комментарий" if f["is_comment"] else "⚠️ Активный код"
            print(f"| {f['line_num']} | {f['category_title']} | {f['description']} | `{escaped_content}` | {status} |")
        print()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python audit_skill.py <путь_к_папке_скилла>")
        sys.exit(1)
        
    target_path = sys.argv[1]
    findings = audit_directory(target_path)
    print_report(findings, target_path)
