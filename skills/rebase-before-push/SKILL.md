---
name: rebase-before-push
description: |
  推送代码前先 rebase 到最新远端主线，避免 push 被 reject。
  当即将执行 git push、或刚执行完 git commit 准备推送时调用。
  适用于 llm-harness-py-wheels（即 Senza）仓库。
  触发词："推上去"、"push"、"提交并推送"、或 codex 即将运行 git push。
---

# 推送前先 Rebase

## 铁律

**任何 `git push` 之前，必须先 `git pull --rebase`。没有例外。**

## 标准流程

```bash
# 1. 提交本地改动
git add -A
git commit -m "<message>"

# 2. rebase 到最新远端主线（一步到位）
git pull --rebase

# 3. 如果有冲突，解决后继续
#    git add <冲突文件>
#    git rebase --continue
#    放弃：git rebase --abort

# 4. 推送
git push
```

## 为什么要这样

- 远端 main 可能有别人推的新提交
- 直接 push 会被 reject（non-fast-forward）
- `git pull --rebase` 把本地 commit 搬到远端最新之上，历史保持线性

## 常见错误

| 错误 | 后果 |
|------|------|
| commit 后直接 push | 被 reject，浪费时间 |
| push reject 后 `git pull` 产生 merge commit | 历史分叉，不干净 |
| rebase 冲突后 `--abort` 丢失改动 | 需要重新做 |

## 仓库信息

- 仓库：`llm-harness-py-wheels`（即将改名 `senza`）
- 远端：`origin` → `https://github.com/oh-my-harness/llm-harness-py-wheels.git`
- 主线分支：`main`
