"""第三方 IM 绑定授权（R4-4）：钉钉/飞书 OAuth 授权 URL + 回调绑定 + 演示模式

- 未配置凭证时走 demo 模式：回调直接模拟外部身份完成绑定
- 真实模式：code 换 token 换用户信息（urllib），任何异常返回中文错误 JSON
- secret/token 不落日志、返回时脱敏
"""
import json
import urllib.parse
import urllib.request
from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException

from app.routers.auth import audit, db_conn, get_current_person

router = APIRouter(prefix="/api/auth", tags=["im-bind"])

PROVIDERS = {
    "dingtalk": {
        "label": "钉钉",
        "authorize": "https://login.dingtalk.com/oauth2/auth",
    },
    "feishu": {
        "label": "飞书",
        "authorize": "https://open.feishu.cn/open-apis/authen/v1/authorize",
    },
}


def _check_provider(provider):
    if provider not in PROVIDERS:
        raise HTTPException(422, f"暂不支持的第三方平台：{provider}（支持 dingtalk/feishu）")
    return PROVIDERS[provider]


def _get_conf(conn, provider):
    return conn.execute("SELECT * FROM auth_providers WHERE provider=?", (provider,)).fetchone()


def _configured(row):
    return bool(row and row["enabled"] and (row["app_id"] or "").strip()
                and (row["app_secret"] or "").strip())


def _provider_view(row):
    """配置视图：app_secret 脱敏为 已配置/未配置"""
    d = dict(row)
    d["app_secret"] = "已配置" if (row["app_secret"] or "").strip() else "未配置"
    d["enabled"] = bool(row["enabled"])
    d["configured"] = _configured(row)
    return d


def _bind(conn, person_id, provider, external_id, external_name, actor):
    """落绑定（UNIQUE(person_id,provider) 覆盖式）+ 审计"""
    conn.execute("DELETE FROM user_bindings WHERE person_id=? AND provider=?",
                 (person_id, provider))
    conn.execute(
        "INSERT INTO user_bindings(person_id,provider,external_id,external_name,bound_at)"
        " VALUES(?,?,?,?,?)",
        (person_id, provider, external_id, external_name,
         datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    audit(conn, actor, "绑定第三方账号", f"{PROVIDERS[provider]['label']}·{external_name}")
    return dict(conn.execute(
        "SELECT * FROM user_bindings WHERE person_id=? AND provider=?",
        (person_id, provider)).fetchone())


@router.get("/providers")
def list_providers(conn=Depends(db_conn), person=Depends(get_current_person)):
    """授权配置列表（app_secret 脱敏）"""
    return [_provider_view(r) for r in conn.execute("SELECT * FROM auth_providers ORDER BY id")]


@router.put("/providers/{provider}")
def update_provider(provider: str, body: dict = Body(...), conn=Depends(db_conn),
                    person=Depends(get_current_person)):
    """配置 app_id/app_secret/redirect_uri/enabled，仅 boss/coach；secret 脱敏返回"""
    _check_provider(provider)
    if person["tier"] not in ("boss", "coach"):
        raise HTTPException(403, "仅高管/教练团可配置第三方授权")
    row = _get_conf(conn, provider)
    if not row:
        raise HTTPException(404, "授权配置不存在（请先完成 R4 播种）")
    sets, args = [], []
    for k in ("app_id", "app_secret", "redirect_uri"):
        if k in body:
            sets.append(f"{k}=?")
            args.append((body.get(k) or "").strip())
    if "enabled" in body:
        sets.append("enabled=?")
        args.append(1 if body.get("enabled") else 0)
    if not sets:
        raise HTTPException(400, "没有可更新的字段（支持 app_id/app_secret/redirect_uri/enabled）")
    args.append(provider)
    conn.execute(f"UPDATE auth_providers SET {', '.join(sets)} WHERE provider=?", args)
    conn.commit()
    # 审计只记字段名，不落 secret 值
    audit(conn, person["name"], "配置第三方授权", PROVIDERS[provider]["label"],
          f"更新字段：{','.join(body.keys())}")
    return _provider_view(_get_conf(conn, provider))


@router.get("/oauth/{provider}/url")
def oauth_url(provider: str, conn=Depends(db_conn), person=Depends(get_current_person)):
    """生成授权 URL：已配置凭证按平台标准拼接；未配置返回 demo 模式 URL"""
    meta = _check_provider(provider)
    conf = _get_conf(conn, provider)
    if _configured(conf):
        redirect = conf["redirect_uri"] or \
            f"http://localhost:8000/api/auth/oauth/{provider}/callback"
        if provider == "dingtalk":
            qs = urllib.parse.urlencode({
                "redirect_uri": redirect, "response_type": "code",
                "client_id": conf["app_id"], "scope": "openid",
                "state": str(person["id"]), "prompt": "consent"})
        else:  # feishu
            qs = urllib.parse.urlencode({
                "app_id": conf["app_id"], "redirect_uri": redirect,
                "state": str(person["id"])})
        return {"provider": provider, "demo": False, "url": f"{meta['authorize']}?{qs}"}
    return {"provider": provider, "demo": True,
            "url": f"/api/auth/oauth/{provider}/callback?demo=1&person_id={person['id']}",
            "tip": f"未配置{meta['label']}应用凭证，当前为演示模式（配置后自动切换真实授权）"}


def _http_json(req):
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _dingtalk_user(conf, code):
    """钉钉：code 换 userAccessToken 再取用户信息"""
    r = _http_json(urllib.request.Request(
        "https://api.dingtalk.com/v1.0/oauth2/userAccessToken",
        data=json.dumps({"clientId": conf["app_id"], "clientSecret": conf["app_secret"],
                         "code": code, "grantType": "authorization_code"}).encode("utf-8"),
        headers={"Content-Type": "application/json"}))
    token = r.get("accessToken")
    if not token:
        raise RuntimeError(f"换取 accessToken 失败：{r}")
    u = _http_json(urllib.request.Request(
        "https://api.dingtalk.com/v1.0/contact/users/me",
        headers={"x-acs-dingtalk-access-token": token}))
    return u.get("unionId") or u.get("openId") or "", u.get("nick") or "钉钉用户"


def _feishu_user(conf, code):
    """飞书：先取 tenant_access_token，code 换 user_access_token 再取用户信息"""
    t = _http_json(urllib.request.Request(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data=json.dumps({"app_id": conf["app_id"], "app_secret": conf["app_secret"]}).encode("utf-8"),
        headers={"Content-Type": "application/json"}))
    tenant = t.get("tenant_access_token")
    if not tenant:
        raise RuntimeError(f"换取 tenant_access_token 失败：{t}")
    r = _http_json(urllib.request.Request(
        "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token",
        data=json.dumps({"grant_type": "authorization_code", "code": code}).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {tenant}"}))
    if r.get("code") != 0:
        raise RuntimeError(f"换取 user_access_token 失败：{r}")
    u = _http_json(urllib.request.Request(
        "https://open.feishu.cn/open-apis/authen/v1/user_info",
        headers={"Authorization": f"Bearer {r['data']['access_token']}"}))
    data = u.get("data") or {}
    return data.get("union_id") or data.get("open_id") or "", data.get("name") or "飞书用户"


@router.get("/oauth/{provider}/callback")
def oauth_callback(provider: str, code: str = None, demo: str = None,
                   person_id: int = None, state: str = None, conn=Depends(db_conn)):
    """授权回调（浏览器直达，免 token）：demo 模拟绑定；真实模式 code 换用户，异常返回中文错误 JSON"""
    meta = _check_provider(provider)
    pid = person_id or state
    person = conn.execute("SELECT * FROM people WHERE id=?", (pid or -1,)).fetchone()
    if not person:
        return {"ok": False, "detail": "回调失败：未找到对应平台人员（person_id/state 无效）"}
    if demo:
        binding = _bind(conn, person["id"], provider,
                        f"demo_{provider}_{person['id']}",
                        f"{meta['label']}用户_{person['name']}", person["name"])
        return {"ok": True, "demo": True, "provider": provider,
                "msg": f"演示模式：已为 {person['name']} 模拟绑定{meta['label']}账号",
                "binding": binding}
    if not code:
        return {"ok": False, "detail": f"{meta['label']}回调缺少 code 参数"}
    conf = _get_conf(conn, provider)
    if not _configured(conf):
        return {"ok": False, "detail": f"{meta['label']}应用凭证未配置，无法完成真实授权"}
    try:
        if provider == "dingtalk":
            ext_id, ext_name = _dingtalk_user(conf, code)
        else:
            ext_id, ext_name = _feishu_user(conf, code)
    except Exception as e:
        return {"ok": False, "detail": f"{meta['label']}授权回调失败：{e}"}
    binding = _bind(conn, person["id"], provider, ext_id, ext_name, person["name"])
    return {"ok": True, "demo": False, "provider": provider,
            "msg": f"已为 {person['name']} 绑定{meta['label']}账号「{ext_name}」",
            "binding": binding}


@router.get("/bindings")
def list_bindings(conn=Depends(db_conn), person=Depends(get_current_person)):
    """当前人的第三方绑定列表"""
    return [dict(r) for r in conn.execute(
        "SELECT * FROM user_bindings WHERE person_id=? ORDER BY id", (person["id"],))]


@router.post("/bindings/{provider}")
def bind_provider(provider: str, conn=Depends(db_conn), person=Depends(get_current_person)):
    """主动绑定入口（demo 用）：等效于 demo 回调，直接模拟外部身份完成绑定"""
    meta = _check_provider(provider)
    binding = _bind(conn, person["id"], provider,
                    f"demo_{provider}_{person['id']}",
                    f"{meta['label']}用户_{person['name']}", person["name"])
    return {"ok": True, "provider": provider, "binding": binding}


@router.delete("/bindings/{provider}")
def unbind_provider(provider: str, conn=Depends(db_conn), person=Depends(get_current_person)):
    """解绑当前人的指定平台"""
    meta = _check_provider(provider)
    row = conn.execute(
        "SELECT * FROM user_bindings WHERE person_id=? AND provider=?",
        (person["id"], provider)).fetchone()
    if not row:
        raise HTTPException(404, f"当前账号未绑定{meta['label']}")
    conn.execute("DELETE FROM user_bindings WHERE id=?", (row["id"],))
    conn.commit()
    audit(conn, person["name"], "解绑第三方账号", f"{meta['label']}·{row['external_name']}")
    return {"ok": True, "provider": provider}
