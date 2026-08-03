#!/usr/bin/env node
// © 2026 Iryna Subbotina. All Rights Reserved. Proprietary — not open source. See LICENSE/NOTICE. Unauthorized copying, redistribution, or claim of authorship is prohibited.
/**
 * LumysAgent HR MCP Server
 * Tools: track_candidate, save_job_description, set_reminder,
 *        get_free_slots, get_email_summary, web_search, send_telegram_message
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { z } from "zod";
import { createServer } from "http";
import pg from "pg";
import fetch from "node-fetch";

import { readFileSync, existsSync } from "fs";

const { Pool } = pg;

const PORT = parseInt(process.env.MCP_HR_PORT || "3200");
const DATABASE_URL = process.env.DATABASE_URL;
const GOOGLE_SHEET_ID = process.env.GOOGLE_SHEET_ID;
const GOOGLE_CALENDAR_ID = process.env.GOOGLE_CALENDAR_ID;
const BRAVE_API_KEY = process.env.BRAVE_API_KEY || process.env.SERPAPI_KEY;
const TELEGRAM_BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN;

const OAUTH_TOKEN_PATH = process.env.GOOGLE_TOKEN_PATH || "/secrets/google-token.json";
const CLIENT_SECRET_PATH = process.env.GOOGLE_CLIENT_SECRET_PATH || "/secrets/client_secret.json";

const pool = DATABASE_URL ? new Pool({ connectionString: DATABASE_URL }) : null;

// ─── Google Auth (OAuth — works for Gmail, Calendar, Sheets) ────────────────

async function getGoogleAuth() {
  const { google } = await import("googleapis");

  // OAuth path: use refresh token from mounted secrets
  if (existsSync(OAUTH_TOKEN_PATH) && existsSync(CLIENT_SECRET_PATH)) {
    const tokenData = JSON.parse(readFileSync(OAUTH_TOKEN_PATH, "utf8"));
    const secretData = JSON.parse(readFileSync(CLIENT_SECRET_PATH, "utf8"));
    const creds = secretData.installed || secretData.web;
    const oauth2 = new google.auth.OAuth2(
      creds.client_id,
      creds.client_secret,
      creds.redirect_uris?.[0]
    );
    oauth2.setCredentials({
      refresh_token: tokenData.refresh_token,
      access_token: tokenData.token,
    });
    return oauth2;
  }

  // Service account fallback
  const serviceAccount = process.env.GOOGLE_CREDENTIALS_JSON
    ? JSON.parse(process.env.GOOGLE_CREDENTIALS_JSON)
    : null;
  if (serviceAccount) {
    return new google.auth.GoogleAuth({
      credentials: serviceAccount,
      scopes: [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/calendar.readonly",
        "https://www.googleapis.com/auth/gmail.readonly",
      ],
    });
  }

  throw new Error("No Google credentials found. Mount /secrets or set GOOGLE_CREDENTIALS_JSON.");
}

// ─── MCP Server ──────────────────────────────────────────────────────────────

const server = new McpServer({
  name: "lumys-hr",
  version: "1.0.0",
});

// ── track_candidate ──────────────────────────────────────────────────────────
server.tool(
  "track_candidate",
  "Add or update a candidate in the Google Sheets tracker and database.",
  {
    name: z.string().describe("Candidate full name"),
    profile_url: z.string().optional().describe("LinkedIn or Djinni profile URL"),
    source: z.string().optional().describe("linkedin | djinni | dou | referral | telegram"),
    status: z.string().optional().describe("new | contacted | screening | interview | offer | rejected"),
    vacancy: z.string().optional().describe("Vacancy title this candidate is for"),
    notes: z.string().optional().describe("Any notes about the candidate"),
  },
  async ({ name, profile_url, source, status, vacancy, notes }) => {
    const results = [];

    // Save to DB
    if (pool) {
      let vacancyId = null;
      if (vacancy) {
        const vRes = await pool.query(
          "SELECT id FROM vacancies WHERE title ILIKE $1 LIMIT 1",
          [`%${vacancy}%`]
        );
        vacancyId = vRes.rows[0]?.id || null;
      }
      await pool.query(
        `INSERT INTO candidates (name, profile_url, source, status, vacancy_id, notes)
         VALUES ($1, $2, $3, $4, $5, $6)
         ON CONFLICT (profile_url) DO UPDATE
           SET name=$1, status=COALESCE($4, candidates.status),
               notes=COALESCE($6, candidates.notes), updated_at=NOW()`,
        [name, profile_url || null, source || null, status || "new", vacancyId, notes || null]
      );
      results.push("✅ Збережено в БД");
    }

    // Append to Google Sheets
    if (GOOGLE_SHEET_ID) {
      try {
        const auth = await getGoogleAuth();
        const { google } = await import("googleapis");
        const sheets = google.sheets({ version: "v4", auth });
        await sheets.spreadsheets.values.append({
          spreadsheetId: GOOGLE_SHEET_ID,
          range: "Candidates!A:G",
          valueInputOption: "USER_ENTERED",
          requestBody: {
            values: [[
              new Date().toISOString().split("T")[0],
              name,
              profile_url || "",
              source || "",
              status || "new",
              vacancy || "",
              notes || "",
            ]],
          },
        });
        results.push("✅ Додано в Google Sheets");
      } catch (e) {
        results.push(`⚠️ Google Sheets помилка: ${e.message}`);
      }
    } else {
      results.push("ℹ️ Google Sheets не налаштований (GOOGLE_SHEET_ID/GOOGLE_CREDENTIALS_JSON)");
    }

    return { content: [{ type: "text", text: results.join("\n") }] };
  }
);

// ── save_job_description ─────────────────────────────────────────────────────
server.tool(
  "save_job_description",
  "Save a job description / vacancy to the database.",
  {
    title: z.string().describe("Job title, e.g. 'Senior Python Developer'"),
    company: z.string().optional().describe("Company name"),
    stack: z.array(z.string()).optional().describe("Tech stack, e.g. ['python', 'fastapi']"),
    seniority: z.string().optional().describe("junior | middle | senior | lead | principal"),
    requirements: z.string().optional().describe("Full requirements text or notes"),
  },
  async ({ title, company, stack, seniority, requirements }) => {
    if (!pool) return { content: [{ type: "text", text: "❌ DATABASE_URL not set" }] };
    const res = await pool.query(
      `INSERT INTO vacancies (title, company, stack, seniority, requirements)
       VALUES ($1, $2, $3, $4, $5) RETURNING id`,
      [title, company || null, stack || [], seniority || null, requirements || null]
    );
    return {
      content: [{
        type: "text",
        text: `✅ Вакансія "${title}" збережена (id: ${res.rows[0].id})`,
      }],
    };
  }
);

// ── set_reminder ─────────────────────────────────────────────────────────────
server.tool(
  "set_reminder",
  "Set a reminder that will be sent via Telegram at the specified time.",
  {
    chat_id: z.string().describe("Telegram chat ID to send the reminder to"),
    message: z.string().describe("Reminder message text"),
    remind_at: z.string().describe("ISO 8601 datetime, e.g. '2025-02-01T10:00:00'"),
  },
  async ({ chat_id, message, remind_at }) => {
    if (!pool) return { content: [{ type: "text", text: "❌ DATABASE_URL not set" }] };
    await pool.query(
      "INSERT INTO reminders (chat_id, message, remind_at) VALUES ($1, $2, $3)",
      [chat_id, message, new Date(remind_at)]
    );
    return {
      content: [{
        type: "text",
        text: `✅ Нагадування встановлено на ${remind_at}`,
      }],
    };
  }
);

// ── get_free_slots ───────────────────────────────────────────────────────────
server.tool(
  "get_free_slots",
  "Get available time slots from Google Calendar for the next N days.",
  {
    days: z.number().default(3).describe("Number of days to look ahead (default: 3)"),
    duration_minutes: z.number().default(60).describe("Duration of the meeting in minutes"),
  },
  async ({ days, duration_minutes }) => {
    if (!GOOGLE_CALENDAR_ID) {
      return {
        content: [{
          type: "text",
          text: "ℹ️ Google Calendar не налаштований (GOOGLE_CALENDAR_ID)",
        }],
      };
    }
    try {
      const auth = await getGoogleAuth();
      const { google } = await import("googleapis");
      const calendar = google.calendar({ version: "v3", auth });
      const now = new Date();
      const end = new Date(now.getTime() + days * 24 * 60 * 60 * 1000);

      const res = await calendar.freebusy.query({
        requestBody: {
          timeMin: now.toISOString(),
          timeMax: end.toISOString(),
          items: [{ id: GOOGLE_CALENDAR_ID }],
        },
      });

      const busy = res.data.calendars?.[GOOGLE_CALENDAR_ID]?.busy || [];
      const slots = [];
      let current = new Date(now);
      current.setMinutes(0, 0, 0);
      current.setHours(Math.max(current.getHours() + 1, 9));

      while (current < end) {
        const slotEnd = new Date(current.getTime() + duration_minutes * 60000);
        const h = current.getHours();
        if (h >= 9 && h < 18) {
          const isFree = !busy.some(b =>
            new Date(b.start) < slotEnd && new Date(b.end) > current
          );
          if (isFree) {
            slots.push(`${current.toLocaleDateString("uk-UA")} ${current.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" })}–${slotEnd.toLocaleTimeString("uk-UA", { hour: "2-digit", minute: "2-digit" })}`);
          }
        }
        current.setMinutes(current.getMinutes() + 30);
        if (slots.length >= 10) break;
      }

      return {
        content: [{
          type: "text",
          text: slots.length ? `Вільні слоти (${duration_minutes} хв):\n${slots.join("\n")}` : "Немає вільних слотів у вказаний період.",
        }],
      };
    } catch (e) {
      return { content: [{ type: "text", text: `❌ Google Calendar помилка: ${e.message}` }] };
    }
  }
);

// ── get_email_summary ────────────────────────────────────────────────────────
server.tool(
  "get_email_summary",
  "Get a summary of recent unread emails from Gmail.",
  {
    max_results: z.number().default(10).describe("Number of emails to summarize"),
    query: z.string().optional().describe("Gmail search query, e.g. 'from:candidate@email.com'"),
  },
  async ({ max_results, query }) => {
    try {
      const auth = await getGoogleAuth();
      const { google } = await import("googleapis");
      const gmail = google.gmail({ version: "v1", auth });
      const listRes = await gmail.users.messages.list({
        userId: "me",
        q: query || "is:unread",
        maxResults: max_results,
      });

      const messages = listRes.data.messages || [];
      if (!messages.length) {
        return { content: [{ type: "text", text: "Нових листів немає." }] };
      }

      const summaries = await Promise.all(
        messages.slice(0, max_results).map(async (m) => {
          const msg = await gmail.users.messages.get({
            userId: "me",
            id: m.id,
            format: "metadata",
            metadataHeaders: ["From", "Subject", "Date"],
          });
          const headers = msg.data.payload?.headers || [];
          const get = (name) => headers.find(h => h.name === name)?.value || "";
          return `• ${get("Date").substring(0, 16)} | ${get("From").replace(/<.*>/, "").trim()} | ${get("Subject")}`;
        })
      );

      return { content: [{ type: "text", text: summaries.join("\n") }] };
    } catch (e) {
      return { content: [{ type: "text", text: `❌ Gmail помилка: ${e.message}` }] };
    }
  }
);

// ── web_search ───────────────────────────────────────────────────────────────
server.tool(
  "web_search",
  "Search the web for candidates, companies, salary data, or market info.",
  {
    query: z.string().describe("Search query, e.g. 'site:linkedin.com/in python senior Ukraine'"),
    count: z.number().default(10).describe("Number of results (default: 10)"),
  },
  async ({ query, count }) => {
    if (!BRAVE_API_KEY) {
      return {
        content: [{
          type: "text",
          text: "ℹ️ Веб-пошук не налаштований (BRAVE_API_KEY або SERPAPI_KEY)",
        }],
      };
    }

    try {
      // Try Brave Search first
      const url = `https://api.search.brave.com/res/v1/web/search?q=${encodeURIComponent(query)}&count=${count}`;
      const res = await fetch(url, {
        headers: {
          "Accept": "application/json",
          "X-Subscription-Token": BRAVE_API_KEY,
        },
      });

      if (!res.ok) throw new Error(`Brave API: ${res.status}`);
      const data = await res.json();
      const results = (data.web?.results || []).map(r =>
        `**${r.title}**\n${r.url}\n${r.description || ""}`
      );

      return {
        content: [{
          type: "text",
          text: results.length ? results.join("\n\n") : "Нічого не знайдено.",
        }],
      };
    } catch (e) {
      return { content: [{ type: "text", text: `❌ Помилка пошуку: ${e.message}` }] };
    }
  }
);

// ── send_telegram_message ────────────────────────────────────────────────────
server.tool(
  "send_telegram_message",
  "Send a Telegram message to a specific chat. Only use after explicit user confirmation.",
  {
    chat_id: z.string().describe("Target Telegram chat ID or @username"),
    text: z.string().describe("Message text to send"),
  },
  async ({ chat_id, text }) => {
    if (!TELEGRAM_BOT_TOKEN) {
      return { content: [{ type: "text", text: "❌ TELEGRAM_BOT_TOKEN not set" }] };
    }
    try {
      const res = await fetch(
        `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat_id, text, parse_mode: "HTML" }),
        }
      );
      const data = await res.json();
      if (!data.ok) throw new Error(data.description);
      return { content: [{ type: "text", text: `✅ Повідомлення надіслано до ${chat_id}` }] };
    } catch (e) {
      return { content: [{ type: "text", text: `❌ Telegram помилка: ${e.message}` }] };
    }
  }
);

// ── Reminder cron ─────────────────────────────────────────────────────────────
async function sendPendingReminders() {
  if (!pool || !TELEGRAM_BOT_TOKEN) return;
  try {
    const res = await pool.query(
      "SELECT id, chat_id, message FROM reminders WHERE remind_at <= NOW() AND sent = FALSE"
    );
    for (const row of res.rows) {
      await fetch(
        `https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ chat_id: row.chat_id, text: `🔔 Нагадування: ${row.message}` }),
        }
      );
      await pool.query("UPDATE reminders SET sent=TRUE WHERE id=$1", [row.id]);
    }
  } catch (e) {
    console.error("Reminder check failed:", e.message);
  }
}

setInterval(sendPendingReminders, 60_000);

// ── HTTP transport (stateless — new transport per request for reliability) ───
const httpServer = createServer(async (req, res) => {
  if (req.url !== "/mcp") {
    res.writeHead(404).end("Not found");
    return;
  }
  const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: undefined });
  await server.connect(transport);
  await transport.handleRequest(req, res);
  await transport.close();
});

httpServer.listen(PORT, "0.0.0.0", () => {
  console.log(`LumysAgent HR MCP server listening on port ${PORT}`);
});
