// SUPERSEDED — pre-Gormers DittoMeThis era file. Kept for reference.
import { readFileSync } from 'fs';
import { ingestSocialContent } from './feed_to_ditto';

async function processDeepDive() {
    const rawData = readFileSync('./tate_deep_dive.json', 'utf-8');
    const posts = JSON.parse(rawData);

    console.log(`░ PROCESSING ${posts.length} POSTS FROM DEEP DIVE...`);

    for (const post of posts) {
        const likes = post.likesCount || 0;
        const views = post.videoViewCount || 0;
        const caption = post.caption || "No Caption";
        const videoUrl = post.videoUrl || "";
        const imgUrl = post.displayUrl || "";
        
        // Grab top 3 comments if available
        const comments = post.latestComments?.slice(0, 3)
            .map((c: any) => `${c.ownerUsername}: ${c.text}`)
            .join(" | ") || "None";

        const meta = `[STATS: L:${likes} V:${views}] [COMMENTS: ${comments}]`;
        const content = videoUrl 
            ? `[VIDEO:${videoUrl}] ${meta} ${caption}`
            : `[IMG:${imgUrl}] ${meta} ${caption}`;

        ingestSocialContent(content, post.url, "Instagram");
    }
    console.log("░ SUCCESS: Deep Dive ingested.");
}

processDeepDive();
