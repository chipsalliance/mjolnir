# Licensed under the Apache-2.0 license
# SPDX-License-Identifier: Apache-2.0
"""Phase 0: Project-wide Exploration by the Project Expert Agent."""

import asyncio
from pathlib import Path
from typing import Any

from google.adk import Context
from google.adk.workflow import node

from constants import (
    PHASE_0_ID,
    PHASE_0_NAME,
    PROJECT_EXPERT_RUN_ID,
    PROJECT_EXPERT_SUMMARY_FILENAME,
    PROJECT_EXPLORATION_TASK_PROMPT,
)
from providers.adk.agents.project_expert import get_project_expert_agent
from providers.adk.utilities.async_runner import extract_agent_text, run_agent_node
from utilities.git import get_head_commit
from utilities.logger import logger


def _get_commit_cache_paths(code_dir: str, run_dir: str | None, commit: str) -> list[Path]:
    """Returns candidate cache file paths keyed by repository HEAD commit hash."""
    if not commit or commit in ("unknown", "local-untracked"):
        return []
    short_commit = commit.strip()[:12]
    paths: list[Path] = []
    if run_dir:
        project_runs_root = Path(run_dir).parent.parent
        paths.append(project_runs_root / ".cache" / f"project_expert_summary_{short_commit}.md")
    git_dir = Path(code_dir) / ".git"
    if git_dir.is_dir():
        paths.append(git_dir / f"mjolnir_project_expert_summary_{short_commit}.md")
    return paths


async def _load_cached_summary(cache_paths: list[Path]) -> tuple[str, Path | None]:
    """Loads the first available non-empty commit-cached exploration summary."""
    for path in cache_paths:
        if path.is_file():
            try:
                content = (await asyncio.to_thread(path.read_text, encoding="utf-8")).strip()
                if content:
                    return content, path
            except Exception as e:
                logger.debug(f"Could not read cached project summary at {path}: {e}")
    return "", None


async def _save_exploration_summary(
    run_dir: str | None,
    summary: str,
    cache_paths: list[Path] | None = None,
) -> None:
    """Writes the Project Expert exploration summary to the run directory and commit caches."""
    if not summary:
        return
    if run_dir:
        summary_path = Path(run_dir) / PROJECT_EXPERT_SUMMARY_FILENAME
        await asyncio.to_thread(summary_path.write_text, summary, encoding="utf-8")
        logger.info(f"Saved project expert summary to {summary_path}")

    for cache_path in cache_paths or []:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            await asyncio.to_thread(cache_path.write_text, summary, encoding="utf-8")
        except Exception as e:
            logger.debug(f"Could not write project expert commit cache to {cache_path}: {e}")


@node(rerun_on_resume=True)
async def project_exploration_phase(ctx: Context, node_input: Any) -> Any:
    """Phase 0: Project-wide Exploration.

    Initializes the Project Expert Agent, performs initial high-level reconnaissance
    over the target codebase (or reuses a commit-keyed cached summary), and stores
    the exploration summary in session state for downstream agents and `ask_project_expert`.
    """
    logger.info(f"Starting Phase {PHASE_0_ID}: {PHASE_0_NAME} (Project Expert)...")

    model = ctx.state["model"]
    code_dir = ctx.state["code_dir"]
    threat_model = ctx.state["threat_model_context"]
    run_dir = ctx.state.get("run_dir")

    commit = await asyncio.to_thread(get_head_commit, code_dir)
    cache_paths = _get_commit_cache_paths(code_dir, run_dir, commit)
    cached_summary, hit_path = await _load_cached_summary(cache_paths)
    if cached_summary:
        logger.info(
            f"Reusing cached Phase {PHASE_0_ID} Project Expert summary for commit "
            f"{commit[:12]} from {hit_path}"
        )
        ctx.state["project_expert_summary"] = cached_summary
        ctx.state["project_expert_qa_history"] = []
        await _save_exploration_summary(run_dir, cached_summary)
        return node_input

    expert_agent = get_project_expert_agent(model, threat_model)
    exploration_prompt = PROJECT_EXPLORATION_TASK_PROMPT.format(code_dir=code_dir)

    res = None
    try:
        res = await run_agent_node(
            ctx,
            expert_agent,
            node_input=exploration_prompt,
            run_id=PROJECT_EXPERT_RUN_ID,
        )
    except Exception as e:
        logger.warning(
            f"Project-wide exploration encountered an error ({e}). Proceeding with baseline state."
        )

    summary = extract_agent_text(res)
    ctx.state["project_expert_summary"] = summary
    ctx.state["project_expert_qa_history"] = []
    if summary:
        logger.info("Project-wide exploration complete. Architectural context cached.")
        await _save_exploration_summary(run_dir, summary, cache_paths=cache_paths)

    return node_input
