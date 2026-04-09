// SUPERSEDED — pre-Gormers DittoMeThis era file. Kept for reference.
import puppeteer from 'puppeteer';
import { ingestSocialContent } from './feed_to_ditto';

async function scrapeInstagram(url: string) {
    console.log(`░ DIVING INTO RABBIT HOLE: ${url}`);
    const browser = await puppeteer.launch({ 
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox'] 
    });
    const page = await browser.newPage();
    
    try {
        await page.setUserAgent("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");
        await page.goto(url, { waitUntil: 'networkidle2', timeout: 60000 });

        // Grab the entire text body of the post/reel
        const fullContent = await page.evaluate(() => {
            return document.body.innerText || "No text content found";
        });

        ingestSocialContent(fullContent, url, "Instagram");
        console.log("░ SUCCESS: Full post content ingested into Ditto.");
    } catch (e) {
        console.error(`░ SCOOP_FAULT: ${e}`);
    } finally {
        await browser.close();
    }
}

const targetUrl = Bun.argv[2];
if (targetUrl) {
    scrapeInstagram(targetUrl);
} else {
    console.log("░ USAGE: bun rabbit_hole_ig.ts <url>");
}
