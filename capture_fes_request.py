"""Capture the exact FES API request when selecting address and going to date step."""
import json
import re
from playwright.sync_api import sync_playwright

CAPTURED = []

def handle_route(route):
    request = route.request
    if "sperrmuell" in request.url and request.post_data:
        CAPTURED.append({
            "url": request.url,
            "method": request.method,
            "headers": dict(request.headers),
            "post_data": request.post_data,
        })
    route.continue_()

def handle_response(response):
    request = response.request
    if "sperrmuell" in request.url and request.method == "POST":
        try:
            body = response.text()
            if body and ("availableDates" in body or "fixedDate" in body or "authenticated" in body):
                CAPTURED.append({
                    "response_url": response.url,
                    "status": response.status,
                    "body": body[:3000],
                })
        except Exception:
            pass

def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        context.route("**/*", handle_route)
        page = context.new_page()
        page.on("response", handle_response)
        page.goto("https://www.fes-frankfurt.de/services/sperrmuell", wait_until="networkidle", timeout=20000)
        # Street field
        page.click('input[placeholder="Straße"]')
        page.fill('input[placeholder="Straße"]', "Westendstr.")
        page.wait_for_timeout(1500)
        # Select first option that contains Westend
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        page.wait_for_timeout(800)
        # House number
        page.click('input[placeholder="Nr."]')
        page.wait_for_timeout(1000)
        page.fill('input[placeholder="Nr."]', "100")
        page.wait_for_timeout(500)
        page.keyboard.press("ArrowDown")
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)
        # Click Weiter
        page.click('a:has-text("Weiter")')
        page.wait_for_timeout(3000)
        browser.close()

    for i, c in enumerate(CAPTURED):
        print("--- Captured", i + 1, "---")
        print(json.dumps(c, indent=2, ensure_ascii=False)[:2500])
        print()

if __name__ == "__main__":
    main()
