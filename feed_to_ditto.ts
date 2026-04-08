import { Database } from "bun:sqlite";
import { join } from "path";

// Ensure we point to the correct DB path relative to your project
const dbPath = join(import.meta.dir, "mfyp_core.db");
const db = new Database(dbPath);
const entityId = "33A1DF10-3484-4957-B8B7-97BD1B3DDE2D"; // Ditto_Alpha

export function ingestSocialContent(text: string, url: string, platform: string) {
  try {
    const query = db.prepare(`
      INSERT INTO ingestion_log (entity_id, url, content, processed_status)
      VALUES (?, ?, ?, 'pending')
    `);
    query.run(entityId, url, `[${platform}] ${text}`);
    console.log(`░ FEEDING DITTO [${platform}]: ${url}`);
  } catch (e) {
    console.error(`░ FEED_FAULT: ${e}`);
  }
}

// Logic for manual testing via CLI: bun feed_to_ditto.ts "tweet text" "url"
if (import.meta.main) {
    const [,, text, url] = Bun.argv;
    if (text && url) ingestSocialContent(text, url, "X");
}
