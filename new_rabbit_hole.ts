// SUPERSEDED — pre-Gormers DittoMeThis era file. Kept for reference.
import { $ } from "bun";
import { ingestSocialContent } from './feed_to_ditto';

async function ingestPublicUser(username: string) {
    console.log(`░ SCANNING PUBLIC PROFILE: ${username}`);
    
    try {
        // Using the 'user' command to get public posts as JSON
        const response = await $`instagram-cli user ${username} --posts --output json`.text();
        const data = JSON.parse(response);

        if (data && data.posts) {
            for (const post of data.posts) {
                // Feeds the caption and metadata into the vector brain
                ingestSocialContent(post.caption, `https://instagram.com/p/${post.shortcode}`, "Instagram-Public");
            }
            console.log(`░ SUCCESS: ${data.posts.length} public posts ingested for ${username}.`);
        }
    } catch (e) {
        console.error(`░ CLI_FAULT: Could not reach public profile. Profile might be private.`);
    }
}

const target = Bun.argv[2];
if (target) {
    ingestPublicUser(target);
} else {
    console.log("░ USAGE: bun new_rabbit_hole.ts <username>");
}
