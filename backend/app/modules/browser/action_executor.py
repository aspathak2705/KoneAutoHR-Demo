import asyncio
from typing import Dict, Any, List
from playwright.async_api import Page
from loguru import logger

class ActionExecutor:
    """
    Module 3 — Executor
    Finds interactive elements matching targets using visible text, labels, ARIA tags, and executes actions.
    """
    async def execute_action(self, page: Page, plan: Dict[str, Any], elements: List[Dict[str, Any]]) -> bool:
        action = plan.get("action")
        target_text = plan.get("target_text", "").lower()
        
        logger.info(f"ActionExecutor | Executing: {plan.get('action')} (Reason: {plan.get('reason')})")

        if action == "click":
            # Search elements matching target_text
            for el in elements:
                label = (el["aria_label"] or el["text"] or el["id"]).lower()
                if target_text in label:
                    try:
                        await el["locator"].click()
                        logger.info(f"ActionExecutor | Clicked target element successfully: {label}")
                        await asyncio.sleep(2)
                        return True
                    except Exception as e:
                        logger.warning(f"ActionExecutor | Click failed on element {label}: {e}")
            
            # Fallback search priority
            try:
                btn = await page.wait_for_selector(f'button:has-text("Continue on this browser")', timeout=3000)
                if btn:
                    await btn.click()
                    return True
            except Exception:
                pass
            return False

        elif action == "fill_and_join":
            input_val = plan.get("input_text", "KONE AutoHR")
            # 1. Fill input name field
            input_filled = False
            for el in elements:
                if el["tag"] == "input":
                    try:
                        await el["locator"].fill(input_val)
                        logger.info(f"ActionExecutor | Filled guest name '{input_val}' in text input.")
                        await asyncio.sleep(1)
                        input_filled = True
                        break
                    except Exception:
                        continue

            if not input_filled:
                # Fallback input selector
                try:
                    await page.fill('input[type="text"]', input_val)
                    input_filled = True
                except Exception:
                    pass

            # 2. Click join button
            for el in elements:
                label = (el["aria_label"] or el["text"] or el["id"]).lower()
                if "join" in label or "now" in label:
                    try:
                        await el["locator"].click()
                        logger.info(f"ActionExecutor | Clicked join button: {label}")
                        await asyncio.sleep(3)
                        return True
                    except Exception:
                        continue
            
            # Fallback join click
            try:
                btn = await page.wait_for_selector('button:has-text("Join now"), button:has-text("Join")', timeout=3000)
                if btn:
                    await btn.click()
                    return True
            except Exception:
                pass
            return False

        elif action == "wait":
            duration = plan.get("duration", 5)
            await asyncio.sleep(duration)
            return True

        elif action == "idle":
            return True

        return False

action_executor = ActionExecutor()
