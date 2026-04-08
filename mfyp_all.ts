import { ingestSocialContent } from './feed_to_ditto';

async function stealthFetch(url: string) {
    const response = await fetch(url, {
        headers: {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Accept": "application/json"
        }
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    return response.json();
}

async function ingestAll() {
    console.log("░ INITIALIZING MULTI-FRONTAL STEALTH INGESTION...");
    
    // Reddit (r/LocalLLaMA)
    try {
        const data = await stealthFetch("https://www.reddit.com/r/LocalLLaMA/hot.json?limit=5");
        data.data.children.forEach((p: any) => 
            ingestSocialContent(p.data.title + " " + p.data.selftext, p.data.url, "Reddit")
        );
        console.log("░ SUCCESS: Reddit Ingested.");
    } catch (e) { console.error("░ REDDIT_BLOCK: Stealth failed. Try a VPN or Proxy."); }

    // Hacker News
    try {
        const data = await stealthFetch("https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=5");
        data.hits.forEach((h: any) => 
            ingestSocialContent(h.title, h.url || `https://news.ycombinator.com/item?id=${h.objectID}`, "HackerNews")
        );
        console.log("░ SUCCESS: HN Ingested.");
    } catch (e) { console.error("░ HN_FAULT:", e); }
}

ingestAll();
