import json
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
        page.get_by_text("mounted", True).wait_for()
        hostVersion = page.locator("#hostVersion").inner_text()
        remoteVersion = page.locator("#remoteVersion").inner_text()
        sameInstance = page.locator("#sameInstance").inner_text()
        warnings = page.locator("p.warnings").all_inner_texts()
        browser.close()
        return (hostVersion, remoteVersion, sameInstance, warnings)


def start(home_vue_version, layout_vue_version, home_shared, layout_shared):
    subprocess.run("pnpm install", shell=True)

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


count = 0
for home_vue_version in ["^3.3.8", "^3.0.11"]:
    for layout_vue_version in ["^3.3.8", "^3.0.11"]:
        if home_vue_version == layout_vue_version:
            continue
        for home_shared, layout_shared in [
            ({}, {}),
            ({"vue": {}}, {"vue": {}}),
            (
                {"vue": {"version": home_vue_version}},
                {"vue": {"version": layout_vue_version}},
            ),
            (
                {"vue": {"requiredVersion": home_vue_version}},
                {"vue": {"requiredVersion": layout_vue_version}},
            ),
        ]:
            for is_strict_version in [None, False, True]:
                if is_strict_version is not None and "vue" not in home_shared:
                    continue
                for is_singleton in [None, False, True]:
                    if is_singleton is not None and "vue" not in home_shared:
                        continue
                    for is_import in [None, False, True]:
                        if is_import is not None and "vue" not in home_shared:
                            continue
                        count += 1
                        if "vue" in home_shared:
                            home_shared["vue"] = {
                                key: value
                                for key, value in (
                                    home_shared["vue"]
                                    | {
                                        "strictVersion": is_strict_version,
                                        "singleton": is_singleton,
                                        "import": is_import,
                                    }
                                ).items()
                                if value is not None
                            }
                        if "vue" in layout_shared:
                            layout_shared["vue"] = {
                                key: value
                                for key, value in (
                                    layout_shared["vue"]
                                    | {
                                        "strictVersion": is_strict_version,
                                        "singleton": is_singleton,
                                    }
                                ).items()
                                if value is not None
                            }
                        print(
                            count,
                            home_vue_version,
                            layout_vue_version,
                            json.dumps(home_shared),
                            json.dumps(layout_shared),
                        )
