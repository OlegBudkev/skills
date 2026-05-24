---
name: restore-session
description: Automatically track and restore previously opened files, documents, and conversation context when Antigravity starts a new session. Use this skill when the user asks to continue previous work, references "last time", or when context suggests continuity from prior sessions.
---

# Session Restore Skill

This skill helps Antigravity remember and restore the user's working context between sessions, including open files, active conversations, workspace state, and relevant dialogs.

## When to Activate

> **ALWAYS AUTO-ACTIVATE** at the very start of every new conversation, before responding to the user's first message. Do not wait for the user to ask — proactively check and restore the previous session every time.

Activate this skill automatically when ANY of the following is true:
- **Always:** A new conversation starts (this is the default behavior — always run restoration)
- The user says "продолжи", "продолжим", "как мы закончили", "с чего начали", "открой снова", or similar continuity phrases
- The user references work from "вчера", "прошлый раз", "предыдущий разговор"
- The user's active document corresponds to a project discussed in recent conversations
- The user's workspace path matches a project discussed in recent conversations

## Step-by-Step Restoration Process

### Step 1: Read Recent Conversation Summaries
At the start of each session, check the conversation history summaries provided in the system context. Identify the most recent conversation(s) relevant to the current workspace.

### Step 2: Match Active Workspace to Conversations
Compare the user's **current workspace URI** (from user_information) and open documents (from ADDITIONAL_METADATA) against recent conversation titles and summaries. Use the following matching strategy:
1. Check if the workspace path appears in any recent conversation title or summary
2. Check if any open file paths were mentioned in recent conversations
3. If multiple matches, pick the most recent one

If a match is found, treat that conversation as the active session to restore. If no match, use the **most recent conversation** as the default to restore.

### Step 3: Load Context from Previous Session (with fallback)

For the matched conversation ID, first check for artifacts in:
```
C:\Users\Oleg\.gemini\antigravity\brain\<conversation-id>\
```

**Priority order (artifacts):**
1. `session_summary.md` — quick session snapshot saved at end of conversation
2. `task.md` — tasks in progress
3. `walkthrough.md` — what was completed
4. `implementation_plan.md` — planned changes

**IMPORTANT — Fallback (if NO artifacts exist for that conversation):**
If the brain folder for the conversation is empty or missing:
1. Use the **conversation title and summary** from the system context directly — do NOT skip
2. Use the USER's **currently open files** (from ADDITIONAL_METADATA) as context clues
3. Reconstruct the situation from the summary text alone
4. Always present what you know, even if source is only the summary

### Step 4: Restore File Context
From the artifacts (or conversation summary), identify which files were being actively edited. Use `view_file` to reload the most critical files and re-establish context.

### Step 5: Summarize and Offer to Continue
Present a brief summary to the user:
- What was being worked on
- What was completed
- What remains to do
- Offer to continue from where they left off

## Example Restoration Message Format

```
## 👋 Восстановление сессии

**Последний проект:** [Project Name]
**Статус:** [Brief status from task.md or conversation summary]

**Что было сделано:**
- [completed items]

**Что осталось:**
- [pending items]

Продолжить с того места? Или хочешь начать что-то новое?
```

## Tracking Current Session State

Throughout the current session, proactively save context by:
1. Keeping `task.md` updated with current progress
2. Creating `walkthrough.md` when significant work is completed
3. **At the end of EVERY significant response** — save/update `session_summary.md`

## REQUIRED: session_summary.md at Every Session End

After completing each user request that involves any meaningful work, **always** save a `session_summary.md` artifact in:
```
C:\Users\Oleg\.gemini\antigravity\brain\<current-conversation-id>\session_summary.md
```

This file is a short snapshot so the next session can restore context even without full artifacts.

**Format:**
```markdown
# Сводка сессии

**Дата:** [текущая дата]
**Проект:** [название проекта]
**Рабочая папка:** [путь к воркспейсу]

## Открытые файлы
- [список файлов, которые были открыты у пользователя]

## Последняя задача
[1-2 предложения о том, что обсуждалось или делалось]

## Осталось сделать
- [незавершённые задачи]
```

> This file MUST be created/updated after every response involving significant work, even if no other artifacts exist. This prevents the "last dialog disappears after reload" problem.

> **ЯЗЫК:** Все поля в `session_summary.md` (название проекта, описание задачи, список незавершённых задач) должны быть написаны **на русском языке**.

## File State Reconstruction

When restoring, reconstruct which files were open by:
1. Checking `session_summary.md` → секция "Открытые файлы"
2. Checking `implementation_plan.md` for files listed under "Proposed Changes"
3. Checking `task.md` for file references in completed/pending items
4. Checking `walkthrough.md` for files mentioned in what was accomplished

Use `view_file` on these files to refresh context before continuing work.

## Conversation Continuity Rules

- **Always greet returning users** with a brief session summary if prior work is detected
- **Never assume** the user wants to restart from scratch without asking
- **Link to previous work** by referencing specific file names and task summaries
- **Be proactive** — if the user opens a file you worked on together before, mention it
- **Never skip restoration silently** — even if no artifacts exist, use conversation summaries

## Notes

- This skill relies on the conversation summaries injected at session start
- Artifacts stored in `C:\Users\Oleg\.gemini\antigravity\brain\<id>\` are the primary source of truth
- `session_summary.md` is the lightweight fallback — always create it after every session
- If no relevant prior session is found, proceed normally without restoration
