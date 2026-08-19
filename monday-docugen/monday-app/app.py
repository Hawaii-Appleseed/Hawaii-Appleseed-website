"""monday.com app backend for docugen.

Endpoints monday calls (JWT signed with the app's SIGNING SECRET):
  POST /monday/actions/generate     custom action Run URL — "generate a document"
  POST /monday/fields/templates     remote options — fills the template dropdown in the recipe

Endpoints the item view iframe calls (sessionToken, signed with the CLIENT SECRET):
  GET  /api/templates
  POST /api/generate
  GET  /api/jobs/<job_id>

Plus:
  GET  /            the item view itself
  GET  /health      liveness
"""

from __future__ import annotations

import os
import pathlib

from flask import Flask, jsonify, request, send_file, send_from_directory

import generator
import jobs
import oauth
from monday_auth import AuthError, verify_integration_request, verify_session_token

app = Flask(__name__, static_folder="static")
STATIC = pathlib.Path(__file__).parent / "static"


@app.errorhandler(AuthError)
def _auth_error(exc: AuthError):
    return jsonify({"error": str(exc)}), exc.status


@app.errorhandler(oauth.OAuthError)
def _oauth_error(exc: oauth.OAuthError):
    return jsonify({"error": str(exc)}), exc.status


@app.errorhandler(oauth.NeedsAuthError)
def _needs_auth(exc: oauth.NeedsAuthError):
    return jsonify({"error": str(exc), "needsAuth": True,
                    "installUrl": exc.install_url}), exc.status


@app.errorhandler(generator.GenerationError)
def _generation_error(exc: generator.GenerationError):
    return jsonify({"error": str(exc)}), exc.status


# ----------------------------------------------------------------- monday → app


@app.post("/monday/actions/generate")
def action_generate():
    """Custom action Run URL.

    Returns 200 immediately — monday times these out — and does the work in a job.
    """
    claims = verify_integration_request(request.headers.get("Authorization"),
                                        "/monday/actions/generate")
    body = request.get_json(silent=True) or {}
    payload = body.get("payload") or {}
    fields = payload.get("inputFields") or {}

    item_id = generator.extract_item_id(payload)
    if not item_id:
        # A 200 with an explanation avoids monday retrying a request that can never work.
        return jsonify({"error": "no item id in payload", "ignored": True}), 200

    def unwrap(value):
        return value.get("value") if isinstance(value, dict) else value

    job_id = jobs.submit(
        "action",
        generator.generate_for_item,
        token=oauth.resolve_api_token(claims),
        item_id=item_id,
        template=unwrap(fields.get("template")),
        output_format=(unwrap(fields.get("outputFormat")) or "docx"),
        files_column=unwrap(fields.get("filesColumn")),
        filename_pattern=unwrap(fields.get("filename")),
    )
    app.logger.info("action run queued job=%s item=%s account=%s",
                    job_id, item_id, claims.get("accountId"))
    return jsonify({"jobId": job_id}), 200


@app.post("/monday/fields/templates")
def field_templates():
    """Remote options for the recipe's template field."""
    verify_integration_request(request.headers.get("Authorization"),
                               "/monday/fields/templates")
    return jsonify({"options": generator.list_templates()}), 200


# ------------------------------------------------------------- item view → app


def _session_claims():
    return verify_session_token(request.headers.get("Authorization"))


@app.get("/api/templates")
def api_templates():
    _session_claims()
    return jsonify({"options": generator.list_templates()})


@app.post("/api/generate")
def api_generate():
    claims = _session_claims()
    body = request.get_json(silent=True) or {}
    item_id = str(body.get("itemId") or "")
    if not item_id:
        return jsonify({"error": "itemId is required"}), 400
    job_id = jobs.submit(
        "item-view",
        generator.generate_for_item,
        token=oauth.resolve_api_token(claims),
        item_id=item_id,
        template=body.get("template"),
        output_format=body.get("outputFormat", "docx"),
        files_column=body.get("filesColumn"),
        filename_pattern=body.get("filename"),
    )
    return jsonify({"jobId": job_id}), 202


@app.get("/api/jobs/<job_id>")
def api_job(job_id: str):
    _session_claims()
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "unknown job"}), 404
    job.pop("traceback", None)
    return jsonify(job)


@app.get("/api/jobs/<job_id>/download")
def api_download(job_id: str):
    """Dev convenience: fetch the generated file directly.

    In production the file lives on the monday item (Files column) — this route mainly
    exists so you can eyeball output while building.
    """
    _session_claims()
    job = jobs.get(job_id)
    if not job or job.get("status") != "done":
        return jsonify({"error": "job not finished"}), 404
    path = pathlib.Path(job["result"]["file"]).resolve()
    if not path.is_relative_to(generator.OUTPUT_DIR.resolve()) or not path.exists():
        return jsonify({"error": "file unavailable"}), 404
    return send_file(path, as_attachment=True, download_name=path.name)


# ------------------------------------------------------------------------ OAuth


@app.get("/oauth/install")
def oauth_install():
    """Kick off the connection: mint state + PKCE verifier, bounce to monday."""
    from flask import redirect
    return redirect(oauth.authorize_url(subdomain=request.args.get("subdomain")), code=302)


@app.get("/oauth/callback")
def oauth_callback():
    """monday sends the user back here with ?code=&state=."""
    if request.args.get("error"):
        return _oauth_page("Connection refused",
                           request.args.get("error_description")
                           or request.args["error"], ok=False), 400

    code, state = request.args.get("code"), request.args.get("state")
    if not code or not state:
        return _oauth_page("Missing code or state",
                           "monday did not send back what we need.", ok=False), 400

    pending = oauth._claim_pending(state)  # single-use; raises on replay
    tokens = oauth.exchange_code(code, pending["verifier"])
    who = oauth.identify(tokens["access_token"])
    oauth.store.save(who["account_id"], tokens,
                     {"account_name": who["account_name"],
                      "user_id": who["user_id"], "user_name": who["user_name"]})
    app.logger.info("connected account %s (%s)", who["account_id"], who["account_name"])
    return _oauth_page(
        "Connected",
        f"{who['account_name'] or 'This account'} is connected. "
        "You can close this tab and generate documents.", ok=True)


@app.get("/oauth/status")
def oauth_status():
    claims = verify_session_token(request.headers.get("Authorization"))
    return jsonify(oauth.status_for(claims.get("accountId")))


@app.post("/oauth/disconnect")
def oauth_disconnect():
    claims = verify_session_token(request.headers.get("Authorization"))
    account_id = str(claims.get("accountId") or "")
    record = oauth.store.get(account_id)
    revoked = False
    if record and record.get("refresh_token"):
        try:
            revoked = oauth.revoke(record["refresh_token"])
        except Exception as exc:  # noqa: BLE001 — forget locally even if revoke fails
            app.logger.warning("revoke failed for %s: %s", account_id, exc)
    return jsonify({"forgotten": oauth.store.forget(account_id), "revoked": revoked})


def _oauth_page(heading: str, message: str, ok: bool = True) -> str:
    colour = "#00854d" if ok else "#d83a52"
    return (
        '<!doctype html><meta charset="utf-8"><title>docugen</title>'
        '<body style="font:15px/1.6 Figtree,system-ui,sans-serif;padding:40px;'
        'max-width:34rem;margin:0 auto;color:#323338">'
        f'<h1 style="font-size:19px;color:{colour};margin:0 0 8px">{heading}</h1>'
        f"<p>{message}</p></body>"
    )


# ------------------------------------------------------------------------ views


@app.get("/")
def item_view():
    return send_from_directory(STATIC, "item-view.html")


@app.get("/health")
def health():
    return jsonify({
        "ok": True,
        "templates": [t["value"] for t in generator.list_templates()],
        "pdf_supported": bool(__import__("docugen").find_soffice()),
        "fake_monday": generator.FAKE,
        "recent_jobs": len(jobs.recent()),
        "oauth": {
            "configured": bool(os.environ.get("MONDAY_CLIENT_ID")),
            "flow": "legacy" if oauth.legacy() else "pkce",
            "connected_accounts": len(oauth.store.accounts()),
        },
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8302)), debug=False)
