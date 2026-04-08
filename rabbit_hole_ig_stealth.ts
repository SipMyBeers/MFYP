import { ingestSocialContent } from './feed_to_ditto';

async function ghostFetch(username: string) {
    console.log(`░ GHOST PROTOCOL INITIATED: ${username}`);
    const url = `https://www.instagram.com/api/v1/users/web_profile_info/?username=${username}`;
    
    const response = await fetch(url, {
        headers: {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 19_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/19.0 Mobile/15E148 Safari/604.1",
            "x-ig-app-id": "936619743392459",
            "sec-ch-ua-platform": "iOS",
            "Referer": "https://www.instagram.com/"
        }
    });

    if (!response.ok) {
        console.error("░ BLOCK_DETECTED: Instagram is demanding a login. Cooling down.");
        return;
    }

    const data = await response.json();
    const edges = data.data.user.edge_owner_to_timeline_media.edges;

    for (const edge of edges) {
        const node = edge.node;
        const meta = `[STATS: L:${node.edge_media_preview_like.count}]`;
        const content = node.is_video 
            ? `[VIDEO:${node.video_url}] ${meta} ${node.edge_media_to_caption.edges[0]?.node.text}`
            : `[IMG:${node.display_url}] ${meta} ${node.edge_media_to_caption.edges[0]?.node.text}`;

        ingestSocialContent(content, `https://instagram.com/p/${node.shortcode}`, "Instagram");
    }
    console.log(`░ SUCCESS: ${edges.length} items fed to Ditto.`);
}

ghostFetch("tatekickboxingchamp");
