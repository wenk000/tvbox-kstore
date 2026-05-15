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
const RAW_BASE    = "https://raw.githubusercontent.com/" + REPO_OWNER + "/" + REPO_NAME + "/main/" + FILE_PATH;

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

function safeBase64Decode(str) {
  try {
    var idx = str.indexOf(",");
    if (idx !== -1) str = str.substring(idx + 1);
    return decodeURIComponent(escape(atob(str)));
  } catch(e) { return null; }
}

async function getFileSha(token) {
  try {
    const res = await fetch(GITHUB_API + "/repos/" + REPO_OWNER + "/" + REPO_NAME + "/contents/" + FILE_PATH, {
      headers: { Authorization: "Bearer " + token, Accept: "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28" },
    });
    if (!res.ok) return null;
    const data = await res.json();
    return data.sha || null;
  } catch { return null; }
}

async function readFile() {
  // 方式1：通过 raw.githubusercontent.com 读取（无需 token）
  try {
    const res2 = await fetch(RAW_BASE);
    if (res2.ok) {
      const text = await res2.text();
      return JSON.parse(text);
    }
  } catch(e) { /* fall through */ }
  return [];
}

async function writeFile(token, content, sha) {
  var encoded = btoa(unescape(encodeURIComponent(JSON.stringify(content, null, 2))));
  var bodyObj = {
    message: "chore: 更新自定义接口列表",
    content: encoded,
  };
  if (sha) bodyObj.sha = sha;

  const res = await fetch(GITHUB_API + "/repos/" + REPO_OWNER + "/" + REPO_NAME + "/contents/" + FILE_PATH, {
    method: "PUT",
    headers: {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
      Accept: "application/vnd.github+json",
      "X-GitHub-Api-Version": "2022-11-28",
      "User-Agent": "tvbox-kstore-pages/1.0",
    },
    body: JSON.stringify(bodyObj),
  });

  if (!res.ok) {
    var errText = await res.text();
    throw new Error("GitHub " + res.status + ": " + errText.substring(0, 200));
  }
  return true;
}

export async function onRequestGet(context) {
  const { request } = context;
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  if (!verifyAuth(request)) return jsonResponse({ error: "未授权" }, 401);

  const token = context.env && context.env.GITHUB_TOKEN;
  if (!token) return jsonResponse({ error: "GITHUB_TOKEN 未配置" }, 500);

  try {
    const sources = await readFile();
    return jsonResponse({ success: true, sources, storage: "github" });
  } catch (e) {
    return jsonResponse({ success: false, error: "读取失败: " + e.message }, 500);
  }
}

export async function onRequestPost(context) {
  const { request } = context;
  if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  if (!verifyAuth(request)) return jsonResponse({ error: "未授权" }, 401);

  const token = context.env && context.env.GITHUB_TOKEN;
  if (!token) return jsonResponse({ error: "GITHUB_TOKEN 未配置" }, 500);

  try {
    const body    = await request.json();
    const { action, name, url, id } = body;

    if (action === "login") return jsonResponse({ success: true, token: "verified" });

    if (action === "add") {
      if (!name || !url) return jsonResponse({ error: "名称和地址不能为空" }, 400);
      try { new URL(url); } catch { return jsonResponse({ error: "地址格式不正确" }, 400); }

      const sha     = await getFileSha(token);
      const sources = await readFile();
      const newSource = {
        id:         Date.now().toString(36) + Math.random().toString(36).slice(2, 6),
        name:       name.trim(),
        url:        url.trim(),
        created_at: new Date().toISOString(),
      };
      sources.push(newSource);
      await writeFile(token, sources, sha);
      return jsonResponse({ success: true, source: newSource, storage: "github" });
    }

    if (action === "delete") {
      if (!id) return jsonResponse({ error: "缺少接口ID" }, 400);
      const sha     = await getFileSha(token);
      let   sources = await readFile();
      const before  = sources.length;
      sources       = sources.filter(s => s.id !== id);
      if (sources.length === before) return jsonResponse({ error: "未找到该接口" }, 404);
      await writeFile(token, sources, sha);
      return jsonResponse({ success: true, remaining: sources.length });
    }

    return jsonResponse({ error: "未知操作" }, 400);
  } catch (e) {
    return jsonResponse({ success: false, error: "操作失败: " + e.message }, 500);
  }
}
