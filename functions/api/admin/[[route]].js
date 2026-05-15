/**
 * Cloudflare Pages Function - Admin API
 * 管理自定义接口：读取、添加、删除
 * 数据持久化到 GitHub 仓库的 custom_sources.json
 */

export const config = { runtime: "edge" };

const REPO_OWNER = "haonanren118";
const REPO_NAME  = "tvbox-kstore";
const FILE_PATH   = "custom_sources.json";
const GITHUB_API  = "https://api.github.com";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type, Authorization",
};

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...corsHeaders },
  });
}

function verifyAuth(request) {
  const authHeader = request.headers.get("Authorization") || "";
  const adminPass  = typeof ADMIN_PASSWORD !== "undefined" ? ADMIN_PASSWORD : "admin";
  return authHeader === "Bearer " + adminPass;
}

async function getFileSha(token) {
  const res = await fetch(`${GITHUB_API}/repos/${REPO_OWNER}/${REPO_NAME}/contents/${FILE_PATH}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
  });
  if (!res.ok) return null;
  const data = await res.json();
  return data.sha || null;
}

async function readFile(token) {
  const res = await fetch(`${GITHUB_API}/repos/${REPO_OWNER}/${REPO_NAME}/contents/${FILE_PATH}`, {
    headers: { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json" },
  });
  if (!res.ok) return [];
  const data = await res.json();
  const content = atob(data.content);
  try { return JSON.parse(content); } catch { return []; }
}

async function writeFile(token, content, sha) {
  const body = {
    message: `chore: 更新自定义接口列表`,
    content: btoa(unescape(encodeURIComponent(JSON.stringify(content, null, 2)))),
    sha: sha || undefined,
  };
  const res = await fetch(`${GITHUB_API}/repos/${REPO_OWNER}/${REPO_NAME}/contents/${FILE_PATH}`, {
    method: "PUT",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json", Accept: "application/vnd.github+json" },
    body: JSON.stringify(body),
  });
  return res.ok;
}

export async function onRequestGet(context) {
  const { request } = context;
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  if (!verifyAuth(request)) return jsonResponse({ error: "未授权" }, 401);

  const token = context.env?.GITHUB_TOKEN;
  if (!token) return jsonResponse({ error: "GitHub Token 未配置" }, 500);

  try {
    const sources = await readFile(token);
    return jsonResponse({ success: true, sources, storage: "github" });
  } catch (e) {
    return jsonResponse({ success: false, error: e.message }, 500);
  }
}

export async function onRequestPost(context) {
  const { request } = context;
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  if (!verifyAuth(request)) return jsonResponse({ error: "未授权" }, 401);

  const token = context.env?.GITHUB_TOKEN;
  if (!token) return jsonResponse({ error: "GitHub Token 未配置" }, 500);

  try {
    const body    = await request.json();
    const { action, name, url, id } = body;

    if (action === "login") {
      return jsonResponse({ success: true, token: "verified" });
    }

    if (action === "add") {
      if (!name || !url) return jsonResponse({ error: "名称和地址不能为空" }, 400);
      try { new URL(url); } catch { return jsonResponse({ error: "地址格式不正确" }, 400); }

      const sha     = await getFileSha(token);
      const sources = await readFile(token);
      const newSource = {
        id:         Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
        name:       name.trim(),
        url:        url.trim(),
        created_at: new Date().toISOString(),
      };
      sources.push(newSource);
      const ok = await writeFile(token, sources, sha);
      if (!ok) return jsonResponse({ error: "写入 GitHub 失败" }, 500);
      return jsonResponse({ success: true, source: newSource, storage: "github" });
    }

    if (action === "delete") {
      if (!id) return jsonResponse({ error: "缺少接口ID" }, 400);
      const sha     = await getFileSha(token);
      let   sources = await readFile(token);
      const before  = sources.length;
      sources       = sources.filter(s => s.id !== id);
      if (sources.length === before) return jsonResponse({ error: "未找到该接口" }, 404);
      const ok = await writeFile(token, sources, sha);
      if (!ok) return jsonResponse({ error: "写入 GitHub 失败" }, 500);
      return jsonResponse({ success: true, remaining: sources.length });
    }

    return jsonResponse({ error: "未知操作" }, 400);
  } catch (e) {
    return jsonResponse({ error: "请求处理失败: " + e.message }, 500);
  }
}