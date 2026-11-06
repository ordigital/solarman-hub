"""Authenticated local control plane; no device reconfiguration or shell execution."""
import asyncio
import hmac
from importlib.resources import files
import os
from pathlib import Path
import secrets
import sqlite3
import time
import tempfile
from urllib.parse import urlsplit

from aiohttp import web
from pydantic import ValidationError

from .config import public_config
from .profiles import Profile
from .bundles import Bundle, preview as bundle_preview, install as bundle_install
from .guides import render_guide
from .auth import load_password, check_password

SESSION_KEY = web.RequestKey("hub_session")


def admin_token(data_dir: Path):
    path = data_dir/"admin-token.txt"
    configured = os.environ.get("HUB_ADMIN_TOKEN", "")
    if configured and len(configured) < 16:
        raise ValueError("HUB_ADMIN_TOKEN musi mieć co najmniej 16 znaków")
    if configured:
        token = configured
    elif path.exists():
        token = path.read_text().strip()
    else:
        token = secrets.token_urlsafe(32)
    if len(token) < 16:
        raise ValueError("Plik admin-token.txt jest nieprawidłowy: wymagane co najmniej 16 znaków. Przywróć kopię lub usuń uszkodzony plik, aby wygenerować nowy token.")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text().strip() == token:
        os.chmod(path, 0o600)
        return token
    descriptor, temporary = tempfile.mkstemp(prefix=".admin-token-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as stream:
            stream.write(token+"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return token


def create_app(runtime):
    token = admin_token(runtime.store.data_dir)
    password = load_password(runtime.store.data_dir)
    password_checks = asyncio.Semaphore(2)
    sessions = {}
    probe_lock = asyncio.Lock()
    resources = files("solarman_hub")

    def origin_check(request):
        origin = request.headers.get("Origin")
        if origin:
            parsed = urlsplit(origin)
            if parsed.scheme not in ("http", "https") or parsed.netloc != request.host:
                raise web.HTTPForbidden(text="Nieprawidłowe pochodzenie żądania")

    @web.middleware
    async def middleware(request, handler):
        try:
            protected = request.path.startswith("/api/") and request.path != "/api/login"
            bearer = request.headers.get("Authorization", "")
            bearer_ok = bearer.startswith("Bearer ") and hmac.compare_digest(bearer[7:].encode(), token.encode())
            session = sessions.get(request.cookies.get("hub_session", ""))
            if session and session["expires"] < time.time():
                session = None
            if protected and not bearer_ok and not session:
                raise web.HTTPUnauthorized(text="Sign in with your administrator token")
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                origin_check(request)
                if protected and not bearer_ok:
                    csrf = request.headers.get("X-CSRF-Token", "")
                    if not session or not hmac.compare_digest(csrf.encode(), session["csrf"].encode()):
                        raise web.HTTPForbidden(text="Brak prawidłowego tokenu CSRF")
                if request.content_type != "application/json":
                    raise web.HTTPUnsupportedMediaType(text="Wymagane application/json")
            request[SESSION_KEY] = session
            response = await handler(request)
        except ValidationError as error:
            response = web.json_response({"error": "Invalid input", "details": [
                {"field": ".".join(map(str, item["loc"])), "message": item["msg"]}
                for item in error.errors(include_input=False, include_url=False)]}, status=400)
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            response = web.json_response({"error": "Invalid request data" if isinstance(error, (KeyError, TypeError, AttributeError)) else str(error)}, status=400)
        except web.HTTPException as error:
            response = web.json_response({"error": error.text}, status=error.status)
        except RuntimeError:
            response = web.json_response({"error": "Sesje jeszcze się zamykają. Spróbuj ponownie za chwilę."}, status=503)
        except (OSError, sqlite3.Error):
            runtime.archive.event("web_storage_error", level="error")
            response = web.json_response({"error": "Błąd zapisu lub odczytu danych. Sprawdź wolumen i logi."}, status=503)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        if request.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    app = web.Application(middlewares=[middleware], client_max_size=512*1024)

    async def health(request):
        return web.json_response({"status": "ok"})

    async def login(request):
        data = await request.json()
        candidate = data.get("token", "")
        accepted = isinstance(candidate, str) and hmac.compare_digest(candidate.encode(), token.encode())
        if not accepted and password is not None:
            if password_checks.locked():
                raise web.HTTPTooManyRequests(text="Please wait and try again")
            async with password_checks:
                accepted = await asyncio.to_thread(check_password, candidate, password)
        if not accepted:
            raise web.HTTPUnauthorized(text="Invalid password or administrator token")
        for key in list(sessions):
            if sessions[key]["expires"] < time.time():
                sessions.pop(key)
        if len(sessions) >= 128:
            sessions.pop(next(iter(sessions)))
        identifier = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(24)
        sessions[identifier] = {"csrf": csrf, "expires": time.time()+8*3600}
        response = web.json_response({"csrf": csrf})
        response.set_cookie("hub_session", identifier, max_age=8*3600, httponly=True,
            samesite="Strict", secure=request.secure or os.environ.get("HUB_COOKIE_SECURE") == "1")
        return response

    async def session(request):
        return web.json_response({"csrf": request[SESSION_KEY]["csrf"] if request[SESSION_KEY] else ""})

    async def logout(request):
        sessions.pop(request.cookies.get("hub_session", ""), None)
        response = web.json_response({"ok": True})
        response.del_cookie("hub_session")
        return response

    async def status(request):
        return web.json_response(runtime.status())

    async def config(request):
        if request.method == "GET":
            return web.json_response({"config": public_config(runtime.store.load()),
                "revision": runtime.store.revision(runtime.profiles.documents())})
        data = await request.json()
        async with runtime.lock:
            current = runtime.store.revision(runtime.profiles.documents())
            if data.get("revision") != current:
                raise web.HTTPConflict(text="Configuration changed. Reload before saving.")
            candidate = runtime.store.candidate(data["config"])
            runtime.validate_references(candidate, runtime.profiles.load())
            await asyncio.to_thread(runtime.store.save, candidate)
            revision = runtime.store.revision(runtime.profiles.documents())
            runtime.archive.event("configuration_saved", revision=revision)
        return web.json_response({"ok": True, "revision": revision})

    async def apply(request):
        async with runtime.lock:
            await runtime.apply()
        return web.json_response({"ok": True, "status": runtime.status()})

    async def profiles(request):
        if request.method == "GET":
            return web.json_response({"profiles": [{**profile.model_dump(), "builtin": key in runtime.profiles.builtin,
                "revision": profile.revision} for key, profile in runtime.profiles.load().items()]})
        profile = Profile.model_validate(await request.json())
        async with runtime.lock:
            await asyncio.to_thread(runtime.profiles.save, profile)
            runtime.archive.event("profile_saved", profile=profile.id)
        return web.json_response({"ok": True, "profile": profile.id})

    async def delete_profile(request):
        identifier = request.match_info["identifier"]
        async with runtime.lock:
            if any(logger.profile == identifier for logger in runtime.store.load().loggers):
                raise web.HTTPConflict(text="Profil jest przypisany do loggera. Najpierw zmień konfigurację.")
            await asyncio.to_thread(runtime.profiles.delete, identifier)
        return web.json_response({"ok": True})

    async def preview(request):
        data = await request.json()
        profile = Profile.model_validate(data["profile"])
        from .protocol import Frame
        frame = Frame.parse(bytes.fromhex(data["hex"]))
        return web.json_response(profile.decode(frame, runtime.store.load().server.timezone))

    async def mqtt_test(request):
        from .mqtt_probe import probe
        data = await request.json()
        candidate = runtime.store.candidate(data["config"])
        if probe_lock.locked():
            raise web.HTTPConflict(text="An MQTT test is already running. Please wait.")
        async with probe_lock:
            result = await probe(candidate.mqtt)
        if not result["ok"]:
            result = {**result, "error": result["message"]}
        return web.json_response(result, status=200 if result["ok"] else 400)

    def selected_logger(request):
        serial = int(request.match_info["serial"])
        logger = next((item for item in runtime.active.loggers if item.serial == serial), None)
        if logger is None:
            raise web.HTTPNotFound(text="Unknown logger")
        return logger

    async def history(request):
        logger = selected_logger(request)
        end = request.query.get("to", time.time())
        start = request.query.get("from", float(end)-86400)
        result = await asyncio.to_thread(runtime.history.rows, logger.serial, start, end,
            request.query.get("limit", 50), request.query.get("before"))
        return web.json_response(result)

    async def series(request):
        logger = selected_logger(request)
        end = request.query.get("to", time.time())
        start = request.query.get("from", float(end)-86400)
        result = await asyncio.to_thread(runtime.history.series, logger.serial, request.query["field"],
            request.query["profile"], request.query["revision"], start, end, request.query.get("points", 600), logger.stale_after)
        return web.json_response(result)

    async def events(request):
        return web.json_response({"events": list(runtime.archive.events)[-200:]})

    async def reconnect(request):
        await runtime.reconnect(int(request.match_info["serial"]))
        return web.json_response({"ok": True})

    async def download(request):
        kind = request.match_info["kind"]
        if kind not in ("frames", "measurements", "events"):
            raise web.HTTPNotFound()
        path = runtime.archive.directory/(kind+".jsonl")
        if not path.is_file():
            raise web.HTTPNotFound(text="No archive file yet")
        response = web.FileResponse(path)
        response.headers["Content-Disposition"] = f'attachment; filename="{kind}.jsonl"'
        return response

    async def docs(request):
        return web.json_response(render_guide(request.query.get("lang","en")))

    async def import_preview(request):
        bundle=Bundle.model_validate(await request.json())
        return web.json_response(bundle_preview(runtime,bundle))

    async def import_bundle(request):
        data=await request.json()
        bundle=Bundle.model_validate(data["bundle"])
        async with runtime.lock:
            if data.get("revision")!=runtime.store.revision(runtime.profiles.documents()):
                raise web.HTTPConflict(text="Configuration changed; preview the import again")
            result=await asyncio.to_thread(bundle_install,runtime,bundle)
            runtime.archive.event("bundle_imported",profile=bundle.profile.id,serial=bundle.logger.serial)
        return web.json_response({"ok":True,"summary":result})

    async def firmware(request):
        name=request.match_info["name"]
        if name not in ("factory.bin","firmware.bin","SHA256SUMS","manifest.json"):
            raise web.HTTPNotFound()
        resource=resources.joinpath("firmware",name)
        if not resource.is_file():
            raise web.HTTPNotFound(text="Firmware artifact unavailable in this build")
        response=web.Response(body=resource.read_bytes(),content_type="application/octet-stream")
        response.headers["Content-Disposition"]=f'attachment; filename="{name}"'
        return response

    async def index(request):
        return web.Response(text=resources.joinpath("static/index.html").read_text(), content_type="text/html")

    async def asset(request):
        name = request.match_info["name"]
        kinds = {"app.js": "application/javascript", "style.css": "text/css", "icon.svg": "image/svg+xml", "i18n.js": "application/javascript", "locales.json": "application/json", "history.js": "application/javascript", "devices.js": "application/javascript", "guide.js": "application/javascript"}
        if name not in kinds:
            raise web.HTTPNotFound()
        return web.Response(body=resources.joinpath("static", name).read_bytes(), content_type=kinds[name])

    app.add_routes([web.get("/health", health), web.get("/", index), web.get("/static/{name}", asset),
        web.post("/api/login", login), web.get("/api/session", session), web.post("/api/logout", logout),
        web.get("/api/status", status), web.get("/api/config", config), web.put("/api/config", config),
        web.post("/api/apply", apply), web.get("/api/profiles", profiles), web.post("/api/profiles", profiles),
        web.delete("/api/profiles/{identifier}", delete_profile), web.post("/api/preview", preview),
        web.post("/api/mqtt/test", mqtt_test), web.get("/api/history/{serial}/series", series), web.get("/api/history/{serial}", history), web.get("/api/events", events), web.post("/api/loggers/{serial}/reconnect", reconnect),
        web.get("/api/archive/{kind}", download), web.get("/api/docs", docs), web.post("/api/import/preview", import_preview), web.post("/api/import", import_bundle), web.get("/api/firmware/{name}", firmware)])
    return app
