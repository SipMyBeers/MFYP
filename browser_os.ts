// SUPERSEDED — pre-Gormers DittoMeThis era file. Kept for reference.
/**
 * BrowserOS — Per-Gorm content routing and visit tracking.
 *
 * Each ingestor (Reddit, HN, IG, etc.) is a "tab" in the BrowserOS.
 * Content gets routed to the right Gorm based on niche matching,
 * visit history is tracked, and signals are pushed via GormersBridge.
 */

import { Database } from "bun:sqlite";
import { join } from "path";

const dbPath = join(import.meta.dir, "mfyp_core.db");
const db = new Database(dbPath);

// Ensure BrowserOS tables exist
db.run(`
  CREATE TABLE IF NOT EXISTS browser_tabs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gorm_id TEXT NOT NULL,
    gorm_name TEXT NOT NULL,
    tab_url TEXT NOT NULL,
    platform TEXT NOT NULL,
    domain TEXT NOT NULL,
    status TEXT DEFAULT 'idle',
    last_active TEXT,
    UNIQUE(gorm_id, domain)
  )
`);

db.run(`
  CREATE TABLE IF NOT EXISTS visit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    gorm_id TEXT NOT NULL,
    gorm_name TEXT NOT NULL,
    url TEXT NOT NULL,
    domain TEXT NOT NULL,
    platform TEXT NOT NULL,
    content_snippet TEXT,
    visited_at TEXT DEFAULT (datetime('now'))
  )
`);

db.run(`
  CREATE TABLE IF NOT EXISTS domain_frequency (
    gorm_id TEXT NOT NULL,
    domain TEXT NOT NULL,
    visit_count INTEGER DEFAULT 1,
    last_visited TEXT DEFAULT (datetime('now')),
    source_requested INTEGER DEFAULT 0,
    PRIMARY KEY (gorm_id, domain)
  )
`);

// Niche → platform keyword mapping for routing
const NICHE_KEYWORDS: Record<string, string[]> = {
  "market": ["flipping", "resale", "arbitrage", "stockx", "ebay", "mercari", "sneaker", "resell"],
  "tech & AI": ["ai", "ml", "llm", "gpt", "model", "transformer", "neural", "machine learning", "deep learning", "coding", "programming"],
  "culture": ["music", "fashion", "art", "tiktok", "creator", "trend", "viral", "album", "artist"],
  "finance": ["stock", "crypto", "bitcoin", "trading", "investment", "macro", "fed", "interest rate"],
  "science": ["paper", "study", "research", "arxiv", "methodology", "experiment"],
  "startups": ["startup", "yc", "seed", "funding", "founder", "vc", "raise"],
  "longevity": ["longevity", "supplement", "fasting", "zone 2", "rapamycin", "nad", "vo2max"],
};

interface GormProfile {
  id: string;
  name: string;
  niche: string;
}

// Gorm profiles — fetched from Gormers API or configured locally
let gormProfiles: GormProfile[] = [];

const GORMERS_URL = process.env.GORMERS_URL || "https://gormers.com";
const GORM_TOKEN = process.env.GORM_SESSION || "";

async function fetchGormProfiles(): Promise<void> {
  try {
    const res = await fetch(`${GORMERS_URL}/api/pets`, {
      headers: GORM_TOKEN ? { Authorization: `Bearer ${GORM_TOKEN}` } : {},
    });
    if (res.ok) {
      const data = await res.json();
      const pets = Array.isArray(data) ? data : data.pets || [];
      gormProfiles = pets.map((p: any) => ({
        id: p.id,
        name: p.name,
        niche: (p.primary_niche || p.biome || "general").toLowerCase(),
      }));
      console.log(`░ BrowserOS: Loaded ${gormProfiles.length} Gorm profiles`);
    }
  } catch {
    console.log("░ BrowserOS: Could not reach Gormers API, using local fallback");
  }
}

function matchGorm(content: string, platform: string): GormProfile | null {
  if (gormProfiles.length === 0) return null;

  const text = content.toLowerCase();
  let bestMatch: GormProfile | null = null;
  let bestScore = 0;

  for (const gorm of gormProfiles) {
    let score = 0;
    const nicheKey = gorm.niche.toLowerCase();

    // Direct niche keyword matching
    for (const [niche, keywords] of Object.entries(NICHE_KEYWORDS)) {
      if (nicheKey.includes(niche) || niche.includes(nicheKey)) {
        score += keywords.filter(k => text.includes(k)).length * 3;
      }
    }

    // Niche words in content
    const nicheWords = nicheKey.split(/\s+/);
    score += nicheWords.filter(w => w.length > 3 && text.includes(w)).length * 5;

    if (score > bestScore) {
      bestScore = score;
      bestMatch = gorm;
    }
  }

  return bestScore >= 3 ? bestMatch : gormProfiles[0]; // Default to first Gorm if no match
}

function trackVisit(gormId: string, gormName: string, url: string, domain: string, platform: string, content: string): void {
  // Log individual visit
  db.prepare(
    "INSERT INTO visit_log (gorm_id, gorm_name, url, domain, platform, content_snippet) VALUES (?, ?, ?, ?, ?, ?)"
  ).run(gormId, gormName, url, domain, platform, content.slice(0, 200));

  // Update domain frequency
  const existing = db.prepare(
    "SELECT visit_count FROM domain_frequency WHERE gorm_id = ? AND domain = ?"
  ).get(gormId, domain) as { visit_count: number } | undefined;

  if (existing) {
    db.prepare(
      "UPDATE domain_frequency SET visit_count = visit_count + 1, last_visited = datetime('now') WHERE gorm_id = ? AND domain = ?"
    ).run(gormId, domain);
  } else {
    db.prepare(
      "INSERT INTO domain_frequency (gorm_id, domain) VALUES (?, ?)"
    ).run(gormId, domain);
  }

  // Update browser tab
  db.prepare(`
    INSERT INTO browser_tabs (gorm_id, gorm_name, tab_url, platform, domain, status, last_active)
    VALUES (?, ?, ?, ?, ?, 'active', datetime('now'))
    ON CONFLICT(gorm_id, domain) DO UPDATE SET
      tab_url = excluded.tab_url, status = 'active', last_active = datetime('now')
  `).run(gormId, gormName, url, platform, domain);
}

async function pushToGormers(gormId: string, content: string, url: string, domain: string, signalStrength: string): Promise<boolean> {
  try {
    const res = await fetch(`${GORMERS_URL}/api/relay`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(GORM_TOKEN ? { Authorization: `Bearer ${GORM_TOKEN}` } : {}),
      },
      body: JSON.stringify({
        message: url,
        type: "url",
        source: "mfyp",
        content_override: content,
        domain,
        signal_strength: signalStrength,
      }),
    });
    return res.ok;
  } catch {
    return false;
  }
}

async function pushVisitToGormers(gormId: string, url: string, domain: string): Promise<void> {
  try {
    await fetch(`${GORMERS_URL}/api/gorms/${gormId}/visit`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(GORM_TOKEN ? { Authorization: `Bearer ${GORM_TOKEN}` } : {}),
      },
      body: JSON.stringify({ url, domain, content_type: "rss" }),
    });
  } catch { /* non-fatal */ }
}

// ── Ingestor tabs ──

async function tabReddit(subreddit: string, limit = 5): Promise<void> {
  console.log(`░ TAB: Reddit r/${subreddit}`);
  try {
    const res = await fetch(`https://www.reddit.com/r/${subreddit}/hot.json?limit=${limit}`, {
      headers: { "User-Agent": "BrowserOS/1.0" },
    });
    if (!res.ok) { console.error(`░ Reddit blocked (${res.status})`); return; }
    const data = await res.json();
    const domain = `reddit.com/r/${subreddit}`;

    for (const child of data.data.children) {
      const post = child.data;
      const content = `${post.title} ${post.selftext || ""}`.trim();
      const url = post.url || `https://reddit.com${post.permalink}`;
      const gorm = matchGorm(content, "Reddit");
      if (!gorm) continue;

      trackVisit(gorm.id, gorm.name, url, domain, "Reddit", content);
      // Only push HIGH signals (upvote ratio > 0.9 and score > 50)
      const strength = post.score > 100 ? "HIGH" : post.score > 30 ? "MED" : "LOW";
      if (strength !== "LOW") {
        await pushToGormers(gorm.id, content.slice(0, 2000), url, domain, strength);
        await pushVisitToGormers(gorm.id, url, domain);
      }
    }
    console.log(`░ SUCCESS: r/${subreddit} processed`);
  } catch (e) { console.error(`░ Reddit error:`, e); }
}

async function tabHackerNews(limit = 5): Promise<void> {
  console.log("░ TAB: Hacker News");
  try {
    const res = await fetch(`https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=${limit}`);
    if (!res.ok) return;
    const data = await res.json();
    const domain = "news.ycombinator.com";

    for (const hit of data.hits) {
      const content = hit.title || "";
      const url = hit.url || `https://news.ycombinator.com/item?id=${hit.objectID}`;
      const gorm = matchGorm(content, "HackerNews");
      if (!gorm) continue;

      trackVisit(gorm.id, gorm.name, url, domain, "HackerNews", content);
      const strength = hit.points > 200 ? "HIGH" : hit.points > 50 ? "MED" : "LOW";
      if (strength !== "LOW") {
        await pushToGormers(gorm.id, content, url, domain, strength);
        await pushVisitToGormers(gorm.id, url, domain);
      }
    }
    console.log("░ SUCCESS: HN processed");
  } catch (e) { console.error("░ HN error:", e); }
}

// ── Status display ──

export function getActiveTabs(): { gorm_name: string; domain: string; status: string; last_active: string }[] {
  return db.prepare(
    "SELECT gorm_name, domain, status, last_active FROM browser_tabs WHERE status = 'active' ORDER BY last_active DESC LIMIT 20"
  ).all() as any[];
}

export function getFrequentDomains(gormId: string): { domain: string; visit_count: number; source_requested: number }[] {
  return db.prepare(
    "SELECT domain, visit_count, source_requested FROM domain_frequency WHERE gorm_id = ? ORDER BY visit_count DESC LIMIT 20"
  ).all(gormId) as any[];
}

export function getDomainsNeedingSourceRequest(): { gorm_id: string; gorm_name: string; domain: string; visit_count: number }[] {
  return db.prepare(`
    SELECT df.gorm_id, bt.gorm_name, df.domain, df.visit_count
    FROM domain_frequency df
    JOIN browser_tabs bt ON df.gorm_id = bt.gorm_id AND df.domain = bt.domain
    WHERE df.visit_count >= 10 AND df.source_requested = 0
  `).all() as any[];
}

// ── Main run ──

async function run() {
  console.log("░ ═══════════════════════════════════════");
  console.log("░ BrowserOS v1 — Per-Gorm Content Router");
  console.log("░ ═══════════════════════════════════════");

  await fetchGormProfiles();

  if (gormProfiles.length === 0) {
    console.log("░ WARNING: No Gorm profiles loaded. Content will be stored locally only.");
  }

  // Open tabs — each is an ingestor
  await tabReddit("LocalLLaMA", 5);
  await tabReddit("MachineLearning", 5);
  await tabReddit("Flipping", 5);
  await tabReddit("startups", 5);
  await tabHackerNews(5);

  // Report active tabs
  const tabs = getActiveTabs();
  console.log(`\n░ ACTIVE TABS: ${tabs.length}`);
  tabs.forEach(t => console.log(`  ${t.gorm_name} → ${t.domain} (${t.last_active})`));

  // Check for domains needing source requests
  const pending = getDomainsNeedingSourceRequest();
  if (pending.length > 0) {
    console.log(`\n░ SOURCE REQUESTS PENDING:`);
    pending.forEach(p => console.log(`  ${p.gorm_name} wants to add ${p.domain} (${p.visit_count} visits)`));
  }

  console.log("\n░ BrowserOS session complete.");
}

if (import.meta.main) {
  run();
}
