/**
 * Alert subscription Worker for rijexamenwachttijden.nl
 *
 * Responsibilities:
 *  - POST /api/subscribe    { email, location }   -> stores a pending subscription, sends confirmation email
 *  - GET  /api/confirm?token=...                   -> activates a subscription
 *  - GET  /api/unsubscribe?token=...                -> removes a subscription
 *  - scheduled()                                    -> runs weekly (via Cron Trigger), compares this week's
 *                                                       data.json against last-sent values, emails anyone
 *                                                       subscribed to a location whose wait time changed
 *
 * Bindings expected (see wrangler.jsonc notes below):
 *   env.SUBSCRIPTIONS   KV namespace  -- subscription records, keyed by token
 *   env.LAST_ALERTED    KV namespace  -- last wait-time value we alerted on, keyed by "<location>:<examSlug>"
 *   env.RESEND_API_KEY  Secret        -- Resend API key
 *   env.SITE_URL        Var           -- e.g. "https://rijexamenwachttijden.nl"
 *   env.FROM_EMAIL      Var           -- e.g. "alerts@rijexamenwachttijden.nl"
 *   env.ASSETS          Assets binding -- existing static-asset serving (unchanged)
 */

const EXAM_LABELS = {
  "wanneer-praktijkexamen": "praktijkexamen",
  "wanneer-herexamen": "herexamen",
  "wanneer-theorie-examen": "theorie-examen",
};

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);

    if (request.method === "POST" && url.pathname === "/api/subscribe") {
      return handleSubscribe(request, env);
    }
    if (request.method === "GET" && url.pathname === "/api/confirm") {
      return handleConfirm(url, env);
    }
    if (request.method === "GET" && url.pathname === "/api/unsubscribe") {
      return handleUnsubscribe(url, env);
    }

    // Everything else: serve the static site as before.
    return env.ASSETS.fetch(request);
  },

  async scheduled(event, env, ctx) {
    ctx.waitUntil(runWeeklyCheck(env));
  },
};

// ---------------------------------------------------------------- helpers

function json(data, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "content-type": "application/json; charset=utf-8" },
  });
}

function isValidEmail(email) {
  return typeof email === "string" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email) && email.length < 200;
}

function randomToken() {
  return crypto.randomUUID().replace(/-/g, "");
}

async function sendEmail(env, { to, subject, html }) {
  const res = await fetch("https://api.resend.com/emails", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${env.RESEND_API_KEY}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      from: env.FROM_EMAIL,
      to,
      subject,
      html,
    }),
  });
  if (!res.ok) {
    console.error("Resend error", res.status, await res.text());
  }
  return res.ok;
}

// ---------------------------------------------------------------- subscribe / confirm / unsubscribe

async function handleSubscribe(request, env) {
  let body;
  try {
    body = await request.json();
  } catch {
    return json({ error: "invalid_request" }, 400);
  }

  const email = (body.email || "").trim().toLowerCase();
  const location = (body.location || "").trim().toLowerCase();

  if (!isValidEmail(email)) return json({ error: "invalid_email" }, 400);
  if (!/^[a-z0-9-]{1,80}$/.test(location)) return json({ error: "invalid_location" }, 400);

  const token = randomToken();
  const record = { email, location, confirmed: false, createdAt: Date.now() };

  // 30 day TTL on unconfirmed signups -- if someone never confirms, it
  // just quietly expires instead of sitting around forever.
  await env.SUBSCRIPTIONS.put(token, JSON.stringify(record), { expirationTtl: 60 * 60 * 24 * 30 });

  const confirmUrl = `${env.SITE_URL}/api/confirm?token=${token}`;
  await sendEmail(env, {
    to: email,
    subject: "Bevestig je wachttijd-alert",
    html: `
      <p>Bevestig je aanmelding om een e-mail te krijgen zodra de wachttijd voor
      <strong>${location}</strong> verandert:</p>
      <p><a href="${confirmUrl}">${confirmUrl}</a></p>
      <p style="color:#888;font-size:0.85em">Heb je dit niet aangevraagd? Dan kun je deze e-mail negeren.</p>
    `,
  });

  return json({ ok: true });
}

async function handleConfirm(url, env) {
  const token = url.searchParams.get("token") || "";
  const raw = await env.SUBSCRIPTIONS.get(token);
  if (!raw) return htmlResponse("Deze link is ongeldig of verlopen.", 400);

  const record = JSON.parse(raw);
  record.confirmed = true;
  // No TTL now that it's confirmed -- stays active until unsubscribed.
  await env.SUBSCRIPTIONS.put(token, JSON.stringify(record));

  return htmlResponse(
    `Bevestigd! Je krijgt een e-mail zodra de wachttijd voor <strong>${record.location}</strong> verandert.`
  );
}

async function handleUnsubscribe(url, env) {
  const token = url.searchParams.get("token") || "";
  await env.SUBSCRIPTIONS.delete(token);
  return htmlResponse("Uitgeschreven. Je ontvangt geen alerts meer voor deze locatie.");
}

function htmlResponse(message, status = 200) {
  return new Response(
    `<!doctype html><html lang="nl"><meta charset="utf-8">
     <body style="font-family:sans-serif;max-width:480px;margin:80px auto;padding:0 20px">
       <p>${message}</p>
       <p><a href="/">Terug naar rijexamenwachttijden.nl</a></p>
     </body></html>`,
    { status, headers: { "content-type": "text/html; charset=utf-8" } }
  );
}

// ---------------------------------------------------------------- weekly comparison job

async function runWeeklyCheck(env) {
  const dataRes = await env.ASSETS.fetch(`${env.SITE_URL}/data.json`);
  if (!dataRes.ok) {
    console.error("Could not fetch data.json for weekly check");
    return;
  }
  const current = await dataRes.json();

  // Walk every location/exam-type combo, compare to last-alerted value.
  const changes = []; // { location, examSlug, oldValue, newValue }
  for (const [lslug, entry] of Object.entries(current)) {
    for (const [examSlug, newValue] of Object.entries(entry.weeks || {})) {
      const key = `${lslug}:${examSlug}`;
      const oldValue = await env.LAST_ALERTED.get(key);
      if (oldValue !== null && oldValue !== String(newValue)) {
        changes.push({ location: lslug, name: entry.name, examSlug, oldValue, newValue });
      }
      await env.LAST_ALERTED.put(key, String(newValue));
    }
  }

  if (changes.length === 0) return;

  // For each changed location, find confirmed subscribers and email them.
  // KV doesn't support "list by value", so we list all subscription keys
  // and filter in-memory -- fine at this scale (dozens/hundreds of subs).
  const list = await env.SUBSCRIPTIONS.list();
  const subsByLocation = {};
  for (const { name: token } of list.keys) {
    const raw = await env.SUBSCRIPTIONS.get(token);
    if (!raw) continue;
    const sub = JSON.parse(raw);
    if (!sub.confirmed) continue;
    (subsByLocation[sub.location] ||= []).push({ token, email: sub.email });
  }

  for (const change of changes) {
    const subs = subsByLocation[change.location] || [];
    if (subs.length === 0) continue;

    const examLabel = EXAM_LABELS[change.examSlug] || change.examSlug;
    const direction = Number(change.newValue) < Number(change.oldValue) ? "korter" : "langer";

    for (const sub of subs) {
      const unsubUrl = `${env.SITE_URL}/api/unsubscribe?token=${sub.token}`;
      await sendEmail(env, {
        to: sub.email,
        subject: `Wachttijd ${change.name}: ${change.oldValue} \u2192 ${change.newValue} weken`,
        html: `
          <p>De wachttijd voor <strong>${examLabel}</strong> in <strong>${change.name}</strong>
          is veranderd van ${change.oldValue} naar ${change.newValue} weken (${direction}).</p>
          <p><a href="${env.SITE_URL}/locatie/${change.location}/">Bekijk de volledige geschiedenis</a></p>
          <p style="color:#888;font-size:0.85em">
            <a href="${unsubUrl}">Uitschrijven voor deze locatie</a>
          </p>
        `,
      });
    }
  }
}
