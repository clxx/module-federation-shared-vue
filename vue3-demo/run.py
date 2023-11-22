import json
import re
import subprocess

from pathlib import Path
from playwright.sync_api import expect, sync_playwright


# https://github.com/microsoft/playwright-python
def scrape(url):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.goto(url)
        page.get_by_text("mounted", exact=True).wait_for()
        expect(page.locator("p.errors")).to_have_count(0)
        page.screenshot(path="screenshot.png")
        hostVersion = page.locator("#hostVersion").inner_text()
        remoteVersion = page.locator("#remoteVersion").inner_text()
        sameInstance = page.locator("#sameInstance").inner_text()
        warnings = page.locator("p.warnings").all_inner_texts()
        browser.close()
        return (hostVersion, remoteVersion, sameInstance, warnings)


def start(home_vue_version, layout_vue_version, home_shared, layout_shared):
    pnpm_lock_yaml = Path("..", "pnpm-lock.yaml")
    pnpm_lock_yaml_bytes = pnpm_lock_yaml.read_bytes()

    home_package_json = Path("home", "package.json")
    home_package_json_text = home_package_json.read_text("utf-8")
    home_package_json_data = json.loads(home_package_json_text)
    home_package_json_data["dependencies"]["vue"] = home_vue_version
    home_package_json.write_text(
        json.dumps(home_package_json_data, indent=2) + "\n", "utf-8"
    )

    layout_package_json = Path("layout", "package.json")
    layout_package_json_text = layout_package_json.read_text("utf-8")
    layout_package_json_data = json.loads(layout_package_json_text)
    layout_package_json_data["dependencies"]["vue"] = layout_vue_version
    layout_package_json.write_text(
        json.dumps(layout_package_json_data, indent=2) + "\n", "utf-8"
    )

    home_shared_json = Path("home", "shared.json")
    home_shared_json_text = home_shared_json.read_text("utf-8")
    home_shared_json.write_text(json.dumps(home_shared, indent=2), "utf-8")

    layout_shared_json = Path("layout", "shared.json")
    layout_shared_json_text = layout_shared_json.read_text("utf-8")
    layout_shared_json.write_text(json.dumps(layout_shared, indent=2), "utf-8")

    try:
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
                print(line)
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
            print(
                home_vue_version, layout_vue_version, home_shared, layout_shared, result
            )
            proc.terminate()
    finally:
        pnpm_lock_yaml.write_bytes(pnpm_lock_yaml_bytes)
        home_package_json.write_text(home_package_json_text, "utf-8")
        layout_package_json.write_text(layout_package_json_text, "utf-8")
        home_shared_json.write_text(home_shared_json_text, "utf-8")
        layout_shared_json.write_text(layout_shared_json_text, "utf-8")


for home_vue_version in ["^3.3.8", "^3.0.11"]:
    for layout_vue_version in ["^3.3.8", "^3.0.11"]:
        if home_vue_version == layout_vue_version:
            continue
        for home_vue_shared, layout_vue_shared in [
            (None, None),
            ({}, {}),
            (
                {"version": home_vue_version},
                {"version": layout_vue_version},
            ),
            (
                {"requiredVersion": home_vue_version},
                {"requiredVersion": layout_vue_version},
            ),
        ]:
            for is_strict_version in [None, False, True]:
                if is_strict_version is not None and home_vue_shared is None:
                    continue
                for is_singleton in [None, False, True]:
                    if is_singleton is not None and home_vue_shared is None:
                        continue
                    for is_import in [None, False, True]:
                        if is_import is not None and home_vue_shared is None:
                            continue
                        home_shared = (
                            {
                                "vue": {
                                    key: value
                                    for key, value in (
                                        home_vue_shared
                                        | {
                                            "strictVersion": is_strict_version,
                                            "singleton": is_singleton,
                                            "import": is_import,
                                        }
                                    ).items()
                                    if value is not None
                                }
                            }
                            if home_vue_shared is not None
                            else {}
                        )
                        layout_shared = (
                            {
                                "vue": {
                                    key: value
                                    for key, value in (
                                        layout_vue_shared
                                        | {
                                            "strictVersion": is_strict_version,
                                            "singleton": is_singleton,
                                        }
                                    ).items()
                                    if value is not None
                                }
                            }
                            if layout_vue_shared is not None
                            else {}
                        )
                        start(
                            home_vue_version,
                            layout_vue_version,
                            home_shared,
                            layout_shared,
                        )
