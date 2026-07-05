"""
Esca #6 — GitHub stats (GitHub public REST API, no auth for low rate).
Raw: https://api.github.com/repos/<owner>/<repo>
Value-add: pulls 6+ endpoints (repo, languages, contributors, commits),
LLM produces a clean "dev health" JSON for procurement/devrel bots.
"""
import json
import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from ..config import settings
from ..llm import llm
from ..payment import require_payment
from ..stats import record_call
from .helpers import cache_get_or_set, error_response, receipt_headers, safe_json

router = APIRouter()
log = logging.getLogger("the_factory.github_stats")

GH_API = "https://api.github.com"


@router.get("/github-stats")
async def github_stats(request: Request, owner: str = "facebook", repo: str = "react"):
    payment_resp = await require_payment(request, "/api/v1/github-stats")
    if payment_resp:
        return payment_resp

    owner = owner.lower()
    repo = repo.lower()
    params = {"owner": owner, "repo": repo}

    async def produce():
        headers = {"Accept": "application/vnd.github+json",
                   "User-Agent": "TheFactory/2.0"}
        async with httpx.AsyncClient(timeout=15) as client:
            base = f"{GH_API}/repos/{owner}/{repo}"
            r = await client.get(base, headers=headers)
            if r.status_code == 404:
                return error_response(404, "repo_not_found", repo=f"{owner}/{repo}")
            if r.status_code != 200:
                return error_response(502, "github_fetch_failed",
                                      upstream_status=r.status_code)
            repo_data = r.json()

            # Languages (dict of lang -> bytes)
            lr = await client.get(f"{base}/languages", headers=headers)
            languages = lr.json() if lr.status_code == 200 else {}

            # Contributors (count + top 3 by commits)
            cr = await client.get(f"{base}/contributors?per_page=100", headers=headers)
            contributors = cr.json() if cr.status_code == 200 else []
            top3 = [
                {"login": c.get("login"), "commits": c.get("contributions", 0)}
                for c in contributors[:3]
            ] if isinstance(contributors, list) else []

            # Last 5 commits
            cmr = await client.get(f"{base}/commits?per_page=5", headers=headers)
            commits_raw = cmr.json() if cmr.status_code == 200 else []
            recent_commits = [
                {"sha": c.get("sha", "")[:7],
                 "message": (c.get("commit", {}).get("message") or "").split("\n")[0][:120],
                 "date": (c.get("commit", {}).get("author", {}) or {}).get("date", "")}
                for c in commits_raw
            ] if isinstance(commits_raw, list) else []

        compact = {
            "full_name": repo_data.get("full_name", f"{owner}/{repo}"),
            "stars": repo_data.get("stargazers_count", 0),
            "forks": repo_data.get("forks_count", 0),
            "open_issues": repo_data.get("open_issues_count", 0),
            "watchers": repo_data.get("watchers_count", 0),
            "default_branch": repo_data.get("default_branch", "main"),
            "license": (repo_data.get("license") or {}).get("spdx_id", "None"),
            "created_at": repo_data.get("created_at", ""),
            "pushed_at": repo_data.get("pushed_at", ""),
            "languages": languages,
            "contributors_count": len(contributors) if isinstance(contributors, list) else 0,
            "top_contributors": top3,
            "recent_commits": recent_commits,
        }

        system = (
            "Sei un analista dev-health per bot aziendali. Ricevi dati compattati da "
            "GitHub. Restituisci SOLO un JSON con questo schema: "
            '{"repo": string, "stars": int, "forks": int, "open_issues": int, '
            '"activity_level": string (una tra: very_active, active, moderate, low, dormant), '
            '"health_summary": string (una frase in italiano su stato del progetto), '
            '"top_language": string}. Non aggiungere testo fuori dal JSON.'
        )
        prompt = f"Repo data:\n{json.dumps(compact)}"
        try:
            text = await llm.complete(prompt=prompt, system=system, max_tokens=400)
            cleaned = safe_json(text)
            cleaned["raw_stats"] = {
                "stars": compact["stars"],
                "forks": compact["forks"],
                "open_issues": compact["open_issues"],
                "contributors_count": compact["contributors_count"],
                "recent_commits": compact["recent_commits"],
            }
            return cleaned
        except Exception as e:
            log.error("LLM cleaning failed: %s", e)
            return {**compact, "warning": "llm_unavailable"}

    data, cached = await cache_get_or_set("github", params, produce)
    if isinstance(data, JSONResponse):
        return data
    receipt = getattr(request.state, "payment_receipt", None)
    record_call(
        endpoint="/api/v1/github-stats",
        cached=cached,
        amount_usd=settings.price_github_stats,
        mode=receipt.get("mode", "single") if receipt else "single",
    )
    headers = receipt_headers(request)
    headers["X-Cache"] = "HIT" if cached else "MISS"
    return JSONResponse(content=data, headers=headers)
