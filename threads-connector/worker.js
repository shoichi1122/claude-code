/**
 * Threads Connector — Cloudflare Worker
 *
 * SNSリファラル管理アプリ用の小さな中継サーバー。
 * ・Threads(Meta)のOAuthログインとトークン発行(長期トークンへの交換)
 * ・自分の投稿に来た返信(=反応)の取得をブラウザから呼べるようにする(CORS対応)
 *
 * アプリのシークレット(THREADS_APP_SECRET)はこのWorker内にのみ保持し、
 * ブラウザには渡しません。ブラウザが保持するのは長期アクセストークンのみです。
 *
 * 必要な環境変数(wrangler.toml / secret):
 *   THREADS_APP_ID       … MetaアプリのThreads App ID(公開情報)
 *   THREADS_APP_SECRET   … Threads App Secret(必ず `wrangler secret put` で設定)
 *   ALLOWED_ORIGIN       … 任意。許可するフロントのオリジン。未設定なら "*"
 *
 * Metaアプリ側の「リダイレクトURI」には、このWorkerの
 *   https://<worker>/auth/callback
 * を完全一致で登録してください。
 */

const GRAPH = 'https://graph.threads.net';
const AUTHORIZE = 'https://threads.net/oauth/authorize';
const SCOPE = 'threads_basic,threads_read_replies';

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/$/, '') || '/';

    try {
      if (request.method === 'OPTIONS') return cors(env, new Response(null, { status: 204 }));
      if (path === '/' || path === '/health') return cors(env, json({ ok: true, service: 'threads-connector' }));
      if (path === '/auth/start') return authStart(url, env);
      if (path === '/auth/callback') return authCallback(url, env);
      if (path === '/refresh') return cors(env, await refresh(url, env));
      if (path === '/api/replies') return cors(env, await apiReplies(url, env));
      return cors(env, json({ error: 'not_found', path }, 404));
    } catch (err) {
      return cors(env, json({ error: 'server_error', message: String(err && err.message || err) }, 500));
    }
  },
};

/* ---------- OAuth ---------- */

function authStart(url, env) {
  const back = url.searchParams.get('redirect') || '';
  const redirectUri = `${url.origin}/auth/callback`;
  const authorize = new URL(AUTHORIZE);
  authorize.searchParams.set('client_id', env.THREADS_APP_ID);
  authorize.searchParams.set('redirect_uri', redirectUri);
  authorize.searchParams.set('scope', SCOPE);
  authorize.searchParams.set('response_type', 'code');
  authorize.searchParams.set('state', back); // ログイン後に戻すフロントのURL
  return Response.redirect(authorize.toString(), 302);
}

async function authCallback(url, env) {
  const code = url.searchParams.get('code');
  const back = url.searchParams.get('state') || '';
  if (!code) return htmlError('認可コードが取得できませんでした。もう一度お試しください。');
  const redirectUri = `${url.origin}/auth/callback`;

  // 1) 認可コード → 短期トークン
  const form = new URLSearchParams({
    client_id: env.THREADS_APP_ID,
    client_secret: env.THREADS_APP_SECRET,
    grant_type: 'authorization_code',
    redirect_uri: redirectUri,
    code,
  });
  const shortRes = await fetch(`${GRAPH}/oauth/access_token`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form.toString(),
  });
  const shortData = await shortRes.json().catch(() => ({}));
  if (!shortRes.ok || !shortData.access_token) {
    return htmlError('短期トークンの取得に失敗しました: ' + JSON.stringify(shortData));
  }

  // 2) 短期トークン → 長期トークン(約60日)
  const exchange = new URL(`${GRAPH}/access_token`);
  exchange.searchParams.set('grant_type', 'th_exchange_token');
  exchange.searchParams.set('client_secret', env.THREADS_APP_SECRET);
  exchange.searchParams.set('access_token', shortData.access_token);
  const longRes = await fetch(exchange.toString());
  const longData = await longRes.json().catch(() => ({}));
  if (!longRes.ok || !longData.access_token) {
    return htmlError('長期トークンへの交換に失敗しました: ' + JSON.stringify(longData));
  }

  // 3) フロントへ #フラグメント で返す(サーバーには残さない)
  const frag = new URLSearchParams({
    threads_token: longData.access_token,
    threads_user_id: String(shortData.user_id || ''),
    threads_expires: String(longData.expires_in || ''),
  });
  if (!back) {
    // 戻り先が無い場合はトークンを画面表示(手動コピー用のフォールバック)
    return htmlPage(`連携に成功しました。以下のトークンをアプリに貼り付けてください:<br><textarea style="width:100%;height:80px">${escapeHtml(longData.access_token)}</textarea>`);
  }
  return Response.redirect(back + '#' + frag.toString(), 302);
}

async function refresh(url, env) {
  const token = url.searchParams.get('access_token');
  if (!token) return json({ error: 'missing_access_token' }, 400);
  const u = new URL(`${GRAPH}/refresh_access_token`);
  u.searchParams.set('grant_type', 'th_refresh_token');
  u.searchParams.set('access_token', token);
  const res = await fetch(u.toString());
  const data = await res.json().catch(() => ({}));
  if (!res.ok) return json({ error: 'refresh_failed', detail: data }, res.status);
  return json({ access_token: data.access_token, expires_in: data.expires_in });
}

/* ---------- 反応(返信)の取得 ---------- */

async function apiReplies(url, env) {
  const token = url.searchParams.get('access_token');
  if (!token) return json({ error: 'missing_access_token' }, 400);
  const postLimit = Math.min(parseInt(url.searchParams.get('posts') || '25', 10) || 25, 50);

  // 自分のユーザー名(自分の返信を除外するため)
  let me = '';
  try {
    const meRes = await fetch(`${GRAPH}/v1.0/me?fields=username&access_token=${encodeURIComponent(token)}`);
    const meData = await meRes.json();
    me = (meData.username || '').toLowerCase();
  } catch (e) { /* 取得できなくても続行 */ }

  // 直近の投稿一覧
  const threadsRes = await fetch(
    `${GRAPH}/v1.0/me/threads?fields=id,permalink,timestamp&limit=${postLimit}&access_token=${encodeURIComponent(token)}`
  );
  const threadsData = await threadsRes.json().catch(() => ({}));
  if (!threadsRes.ok) return json({ error: 'threads_fetch_failed', detail: threadsData }, threadsRes.status);
  const posts = Array.isArray(threadsData.data) ? threadsData.data : [];

  // 各投稿の返信を集約(ユーザー名で重複排除、最新の返信を優先)
  const byUser = new Map();
  for (const post of posts) {
    const repRes = await fetch(
      `${GRAPH}/v1.0/${post.id}/replies?fields=id,text,username,timestamp,permalink&access_token=${encodeURIComponent(token)}`
    );
    if (!repRes.ok) continue;
    const repData = await repRes.json().catch(() => ({}));
    for (const r of (repData.data || [])) {
      const uname = (r.username || '').toLowerCase();
      if (!uname || uname === me) continue;
      const existing = byUser.get(uname);
      if (!existing || (r.timestamp || '') > (existing.timestamp || '')) {
        byUser.set(uname, {
          username: r.username,
          text: r.text || '',
          timestamp: r.timestamp || '',
          permalink: r.permalink || '',
          post_permalink: post.permalink || '',
        });
      }
    }
  }

  const replies = [...byUser.values()].sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
  return json({ replies, post_count: posts.length });
}

/* ---------- ヘルパー ---------- */

function json(obj, status = 200) {
  return new Response(JSON.stringify(obj), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}

function cors(env, res) {
  const origin = (env && env.ALLOWED_ORIGIN) || '*';
  const h = new Headers(res.headers);
  h.set('Access-Control-Allow-Origin', origin);
  h.set('Access-Control-Allow-Methods', 'GET, OPTIONS');
  h.set('Access-Control-Allow-Headers', 'Content-Type');
  h.set('Vary', 'Origin');
  return new Response(res.body, { status: res.status, headers: h });
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

function htmlPage(inner) {
  return new Response(
    `<!doctype html><meta charset="utf-8"><body style="font-family:sans-serif;max-width:560px;margin:40px auto;padding:0 16px;line-height:1.7">${inner}</body>`,
    { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
  );
}

function htmlError(msg) {
  return htmlPage(`<h3>⚠️ エラー</h3><p>${escapeHtml(msg)}</p><p><a href="javascript:history.back()">戻る</a></p>`);
}
