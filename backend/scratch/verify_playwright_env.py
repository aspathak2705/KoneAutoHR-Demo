import asyncio
import sys
import shutil
from pathlib import Path
from playwright.async_api import async_playwright

async def verify_env():
    print("==================================================")
    print("      PLAYWRIGHT ENVIRONMENT VERIFICATION        ")
    print("==================================================")
    
    # 1. Check Python version
    print(f"[+] Python Version: {sys.version}")
    
    temp_profile = Path(__file__).parent / "test_verify_profile"
    if temp_profile.exists():
        shutil.rmtree(temp_profile, ignore_errors=True)
    temp_profile.mkdir(parents=True, exist_ok=True)
    
    playwright = None
    context = None
    try:
        # 2. Try starting Playwright
        print("[+] Initializing async_playwright...")
        playwright = await async_playwright().start()
        print("[+] async_playwright started successfully.")
        
        # 3. Try launching Chromium
        print(f"[+] Launching Chromium (headless=True, userDataDir={temp_profile})...")
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(temp_profile),
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        print("[+] Chromium persistent context launched successfully!")
        
        # 4. Try opening a page
        print("[+] Opening new page...")
        page = await context.new_page()
        print("[+] Page created. Navigating to about:blank...")
        await page.goto("about:blank")
        print(f"[+] Page title: '{await page.title()}'")
        
        print("[+] Closing page and context...")
        await context.close()
        context = None
        print("[+] Playwright environment is fully functional!")
        
    except Exception as e:
        print(f"[-] VERIFICATION FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
        
    finally:
        if context:
            try:
                await context.close()
            except Exception:
                pass
        if playwright:
            try:
                await playwright.stop()
            except Exception:
                pass
        # Clean up profile folder
        shutil.rmtree(temp_profile, ignore_errors=True)
        print("[+] Temporary profile folders cleaned up.")
        print("==================================================")

if __name__ == "__main__":
    asyncio.run(verify_env())
