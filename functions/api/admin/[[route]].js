/**
 * Cloudflare Pages Function - Admin API
 */
export const config = { runtime: "edge" };
const REPO_OWNER = "wenk000";
const REPO_NAME  = "tvbox-kstore";
const FILE_PATH   = "custom_sources.json";
const WORKFLOW_ID = "generate.yml";
const GITHUB_API  = "https://api.github.com";
const RAW_BASE    = "https://raw.githubusercontent.com/" + REPO_OWNER + "/" + REPO_NAME + "/main/" + FILE_PATH;
const corsHeaders = { "Access-Control-Allow-Origin": "*", "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS", "Access-Control-Allow-Headers": "Content-Type, Authorization" };
function jsonResponse(data, status = 200) { return new Response(JSON.stringify(data), { status, headers: { "Content-Type": "application/json", ...corsHeaders } }); }
function verifyAuth(request) { const authHeader = request.headers.get("Authorization") || ""; const adminPass = typeof ADMIN_PASSWORD !== "undefined" ? ADMIN_PASSWORD : "admin"; return authHeader === "Bearer " + adminPass; }
async function readSources() { try { const res = await fetch(RAW_BASE + "?t=" + Date.now()); if (res.ok) return await res.json(); } catch(e) {} return []; }
async function ghApi(token, path, method, body) {
  var url = GITHUB_API + path;
  var opts = { method: method, headers: { "Content-Type": "application/json", "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "tvbox-kstore-pages/1.0", "Authorization": "Bearer " + token } };
  if (body) opts.body = JSON.stringify(body);
  var res = await fetch(url, opts);
  var text = await res.text();
  if (!res.ok) throw new Error("GitHub " + res.status + ": " + text.substring(0, 200));
  if (text) return JSON.parse(text);
  return null;
}
async function writeFile(token, content, sha) {
  var encoded = btoa(unescape(encodeURIComponent(JSON.stringify(content, null, 2))));
  await ghApi(token, "/repos/" + REPO_OWNER + "/" + REPO_NAME + "/contents/" + FILE_PATH, "PUT", { message: "chore: 更新自定义接口列表", content: encoded, sha: sha });
}
async function getSha(token) {
  var data = await ghApi(token, "/repos/" + REPO_OWNER + "/" + REPO_NAME + "/contents/" + FILE_PATH, "GET", null);
  return data && data.sha;
}
export async function onRequestGet(context) {
  const { request } = context;
  if (request.method === 'OPTIONS') { return new Response(null, { status: 204, headers: corsHeaders });
}

 if (!verifyAuth(request)) { return jsonResponse({ error: '未授权' }, 401);
}
  //if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: corsHeaders });
  //if (!verifyAuth(request)) return jsonResponse({ error: "未授权" }, 401);
  const token = context.env && context.env.GITHUB_TOKEN;
  if (!token) return jsonResponse({ error: "GITHUB_TOKEN 未配置" }, 500);
  try {
    const sources = await readSources();
    return jsonResponse({ success: true, sources, storage: "github" });
  } catch (e) { return jsonResponse({ success: false, error: "读取失败: " + e.message }, 500); }
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
      const sources = await readSources();
      const newSource = { id: Date.now().toString(36) + Math.random().toString(36).slice(2, 6), name: name.trim(), url: url.trim(), created_at: new Date().toISOString() };
      sources.push(newSource);
      const sha = await getSha(token);
      if (!sha) return jsonResponse({ error: "无法获取文件SHA，请检查 Token 权限" }, 500);
      await writeFile(token, sources, sha);
      return jsonResponse({ success: true, source: newSource, storage: "github" });
    }
    if (action === "delete") {
      if (!id) return jsonResponse({ error: "缺少接口ID" }, 400);
      let sources = await readSources();
      const before = sources.length;
      sources = sources.filter(s => s.id !== id);
      if (sources.length === before) return jsonResponse({ error: "未找到该接口" }, 404);
      const sha = await getSha(token);
      if (!sha) return jsonResponse({ error: "无法获取文件SHA" }, 500);
      await writeFile(token, sources, sha);
      return jsonResponse({ success: true, remaining: sources.length });
    }
    if (action === "trigger") {
      try {
        await ghApi(token, `/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW_ID}/dispatches`, "POST", { ref: "main" });
        return jsonResponse({ success: true, message: "构建已触发，请等待约1-2分钟" });
      } catch (e) {
        return jsonResponse({ success: false, error: "触发失败: " + e.message }, 500);
      }
    }
    if (action === "status") {
      try {
        const runs = await ghApi(token, `/repos/${REPO_OWNER}/${REPO_NAME}/actions/workflows/${WORKFLOW_ID}/runs?per_page=1`, "GET", null);
        const latest = runs && runs.workflow_runs && runs.workflow_runs[0];
        return jsonResponse({
          success: true，
          running: latest ? (latest.status === "in_progress" || latest.status === "queued") : false,
          status: latest ? latest.status : "unknown",
          conclusion: latest ? latest.conclusion : null,
          run_id: latest ? latest.id : null,
          updated_at: latest ? latest.updated_at : null
        });
      } catch (e) {
        return jsonResponse({ success: false, error: e.message }, 500);
      }
    }
    return jsonResponse({ error: "未知操作" }, 400);
  } catch (e) { return jsonResponse({ success: false, error: "操作失败: " + e.message }, 500); }
}
