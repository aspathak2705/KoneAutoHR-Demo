import asyncio
from app.db.database import SessionLocal
from app.modules.meeting_bot.services.meeting_bot_service import meeting_bot_service

async def main():
    session_id = "4aca47b3-2011-4745-bbdb-2d4e7cf86b20"
    bot = meeting_bot_service.get_bot(session_id)
    if not bot or not bot.context.page:
        print("No active bot or page found.")
        return
        
    page = bot.context.page
    print("Page URL:", page.url)
    
    # Get all video elements and their attributes
    videos = await page.locator("video").all()
    print(f"Found {len(videos)} video elements.")
    for idx, video in enumerate(videos):
        html = await video.evaluate("el => el.outerHTML")
        print(f"Video {idx}: {html}")
        
        # Get parent element outerHTML (up to 3 levels)
        parent = video
        for lvl in range(1, 4):
            parent = parent.locator("..")
            try:
                parent_html = await parent.evaluate("el => el.outerHTML")
                # print just the tag and attributes of parent
                tag_and_attrs = parent_html.split(">")[0] + ">"
                print(f"  Parent Lvl {lvl}: {tag_and_attrs}")
            except Exception as e:
                print(f"  Parent Lvl {lvl} error: {e}")
                
    # Check other potential stage containers
    containers = ["div[class*='stage']", "div[class*='sharing']", "div[class*='share']", "div[class*='video']"]
    for selector in containers:
        cnt = await page.locator(selector).count()
        print(f"Selector '{selector}' matches count: {cnt}")
        if cnt > 0:
            first_html = await page.locator(selector).first.evaluate("el => el.outerHTML")
            print(f"  First '{selector}' element: {first_html.split('>')[0]}>")

if __name__ == "__main__":
    asyncio.run(main())
