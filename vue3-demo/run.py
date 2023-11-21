import re
import subprocess

from playwright.sync_api import expect, sync_playwright


# https://github.com/microsoft/playwright-python
def scrape(url):
    print(url)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url)
        page.get_by_text("mounted", exact=True).wait_for()
        hostVersion = page.locator("#hostVersion").inner_text()
        remoteVersion = page.locator("#remoteVersion").inner_text()
        sameInstance = page.locator("#sameInstance").inner_text()
        warnings = page.locator("p.warnings").all_inner_texts()
        browser.close()
        return (hostVersion, remoteVersion, sameInstance, warnings)

subprocess.run('pnpm install', shell=True)

with subprocess.Popen(
    "pnpm start",
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    shell=True,
    encoding="utf-8",
) as proc:
    home = False
    layout = False
    url = ""
    while line := proc.stdout.readline():
        line = line.strip()
        if match := re.fullmatch(
            r"layout start: <i> \[webpack-dev-server\] Loopback: (.+)", line
        ):
            url = match.group(1)
        elif match := re.fullmatch(
            r"(home|layout) start: webpack \d+\.\d+\.\d+ compiled successfully in \d+ ms",
            line,
        ):
            if match.group(1) == "home":
                home = True
            elif match.group(1) == "layout":
                layout = True
        if home and layout and url:
            break
    result = scrape(url)
    print(result)
    proc.terminate()
