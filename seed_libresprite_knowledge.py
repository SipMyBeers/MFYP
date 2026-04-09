"""
Seed LibreSprite Knowledge
==========================
Seeds a Gorm with LibreSprite API reference + pixel art technique knowledge.
Run once to give a Gorm the foundation for sprite creation.

STAGED: Needs Ghengis + Ollama + MFYP_BRIDGE_SECRET.

Usage: python3 seed_libresprite_knowledge.py --gorm-id 1 --gorm-name Visu
"""

import asyncio
import argparse
import os
import sys

# Ensure MFYP modules are importable
sys.path.insert(0, os.path.dirname(__file__))

from skill_manager import save_skill_entry

ENTRIES = [
    {
        "claim": "LibreSprite JS API: newSprite(w,h) creates sprite. "
                 "spr.layer(0).cel(0).image gets Image for drawing. "
                 "img.putPixel(x,y,color) places one pixel. img.clear(color) fills canvas. "
                 "pixelColor.rgba(r,g,b,a) creates color (0-255). "
                 "spr.saveAs(path, true) saves PNG. Canvas: (0,0)=top-left.",
        "confidence": "HIGH",
        "cluster_tag": "libresprite-api",
        "source_url": "https://github.com/LibreSprite/LibreSprite/blob/master/SCRIPTING.md",
    },
    {
        "claim": "LibreSprite palette setup: define 5-6 color vars at top. "
                 "Signal biome: teal=rgba(29,158,117,255), dark=rgba(14,79,58,255), "
                 "hi=rgba(77,255,180,255), outline=rgba(10,20,15,255). "
                 "Scholar: blue=rgba(24,95,165,255). Void: red=rgba(114,36,62,255). "
                 "Always include transparent=rgba(0,0,0,0).",
        "confidence": "HIGH",
        "cluster_tag": "libresprite-api",
        "source_url": "https://github.com/LibreSprite/LibreSprite/blob/master/SCRIPTING.md",
    },
    {
        "claim": "At 32x32, silhouette must be readable as solid shape at 1x size. "
                 "Body occupies 60-70% of canvas height. Strong diagonal or asymmetric shapes "
                 "read better than symmetric. Avoid thin one-pixel limbs.",
        "confidence": "HIGH",
        "cluster_tag": "sprite-technique-silhouette",
        "source_url": "https://www.derekyu.com/makegames/pixelart.html",
    },
    {
        "claim": "5-color max for 32x32 creatures: base, dark shadow (25-30% darker, hue shift cool), "
                 "bright highlight (25-30% lighter, hue shift warm), dark outline (near-black, biome tinted), "
                 "transparent background. More colors = noise at small size.",
        "confidence": "HIGH",
        "cluster_tag": "sprite-technique-color",
        "source_url": "https://www.slynyrd.com/pixelblog-catalogue",
    },
    {
        "claim": "Selective outlining: dark outline only on edges facing background or different-colored region. "
                 "No outline between same-colored interior regions. Darker edges at bottom, lighter at top "
                 "(overhead light source).",
        "confidence": "MED",
        "cluster_tag": "sprite-technique-outline",
        "source_url": "https://saint11.art/blog/pixel-art-tutorials/",
    },
    {
        "claim": "Personality posture at 32x32: forward lean=aggressive/alert (5-10 degree angle). "
                 "Upright=calm/analytical. Hunched=defensive/skeptical. Wide stance=confident. "
                 "Body center of gravity conveys personality even at tiny sizes.",
        "confidence": "MED",
        "cluster_tag": "sprite-technique-personality",
        "source_url": "https://www.derekyu.com/makegames/pixelart.html",
    },
    {
        "claim": "Eyes most important at 32x32. 2x2 pixels minimum per eye. "
                 "Wide circle=curious, narrow horizontal=calculating, angled inward=aggressive, "
                 "half-closed=skeptical. Position: upper third of head. "
                 "1 bright glow pixel at corner of each eye adds life.",
        "confidence": "HIGH",
        "cluster_tag": "sprite-technique-eyes",
        "source_url": "https://saint11.art/blog/pixel-art-tutorials/",
    },
]


async def seed(gorm_id: int, gorm_name: str):
    print(f"[Seed] Adding LibreSprite + pixel art knowledge to {gorm_name} (#{gorm_id})...")

    for entry in ENTRIES:
        result = await save_skill_entry(
            gorm_id=gorm_id,
            gorm_name=gorm_name,
            domain="pixel art",
            claim=entry["claim"],
            confidence=entry["confidence"],
            source_url=entry.get("source_url", ""),
        )
        tag = entry.get("cluster_tag", "")
        if result:
            print(f"  + {tag}: {entry['claim'][:60]}...")
        else:
            print(f"  x FAILED: {tag}")

    print(f"\n[Seed] Done. {gorm_name} now has {len(ENTRIES)} pixel art knowledge entries.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--gorm-id", type=int, required=True)
    parser.add_argument("--gorm-name", type=str, default="Visu")
    args = parser.parse_args()
    asyncio.run(seed(args.gorm_id, args.gorm_name))
