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


def start(host_vue_version, remote_vue_version, host_shared, remote_shared):
    pnpm_lock_yaml = Path("..", "pnpm-lock.yaml")
    pnpm_lock_yaml_bytes = pnpm_lock_yaml.read_bytes()

    host_package_json = Path("layout", "package.json")
    host_package_json_text = host_package_json.read_text("utf-8")
    host_package_json_data = json.loads(host_package_json_text)
    host_package_json_data["dependencies"]["vue"] = host_vue_version
    host_package_json_data["devDependencies"]["@vue/compiler-sfc"] = host_vue_version
    host_package_json.write_text(
        json.dumps(host_package_json_data, indent=2) + "\n", "utf-8"
    )

    remote_package_json = Path("home", "package.json")
    remote_package_json_text = remote_package_json.read_text("utf-8")
    remote_package_json_data = json.loads(remote_package_json_text)
    remote_package_json_data["dependencies"]["vue"] = remote_vue_version
    remote_package_json_data["devDependencies"]["@vue/compiler-sfc"] = remote_vue_version
    remote_package_json.write_text(
        json.dumps(remote_package_json_data, indent=2) + "\n", "utf-8"
    )

    host_shared_json = Path("layout", "shared.json")
    host_shared_json_text = host_shared_json.read_text("utf-8")
    host_shared_json.write_text(json.dumps(host_shared, indent=2), "utf-8")

    remote_shared_json = Path("home", "shared.json")
    remote_shared_json_text = remote_shared_json.read_text("utf-8")
    remote_shared_json.write_text(json.dumps(remote_shared, indent=2), "utf-8")

    try:
        subprocess.run("pnpm install", shell=True)

        with subprocess.Popen(
            "pnpm start",
            stdout=subprocess.PIPE,
            shell=True,
            encoding="utf-8",
        ) as proc:
            host = False
            remote = False
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
                    if match.group(1) == "layout":
                        host = True
                    elif match.group(1) == "home":
                        remote = True
                if host and remote and url:
                    break
            result = scrape(url)
            print(
                host_vue_version, remote_vue_version, host_shared, remote_shared, result
            )
            proc.terminate()
    finally:
        pnpm_lock_yaml.write_bytes(pnpm_lock_yaml_bytes)
        host_package_json.write_text(host_package_json_text, "utf-8")
        remote_package_json.write_text(remote_package_json_text, "utf-8")
        host_shared_json.write_text(host_shared_json_text, "utf-8")
        remote_shared_json.write_text(remote_shared_json_text, "utf-8")


for host_vue_version in ["^3.3.8", "^3.0.11"]:
    for remote_vue_version in ["^3.3.8", "^3.0.11"]:
        if host_vue_version == remote_vue_version:
            continue
        for host_vue_shared, remote_vue_shared in [
            (None, None),
            ({}, {}),
            (
                {"version": host_vue_version},
                {"version": remote_vue_version},
            ),
            (
                {"requiredVersion": host_vue_version},
                {"requiredVersion": remote_vue_version},
            ),
        ]:
            for is_strict_version in [None, False, True]:
                if is_strict_version is not None and host_vue_shared is None:
                    continue
                for is_singleton in [None, False, True]:
                    if is_singleton is not None and host_vue_shared is None:
                        continue
                    for is_import in [None, False, True]:
                        if is_import is not None and host_vue_shared is None:
                            continue
                        host_shared = (
                            {
                                "vue": {
                                    key: value
                                    for key, value in (
                                        host_vue_shared
                                        | {
                                            "strictVersion": is_strict_version,
                                            "singleton": is_singleton,
                                        }
                                    ).items()
                                    if value is not None
                                }
                            }
                            if host_vue_shared is not None
                            else {}
                        )
                        remote_shared = (
                            {
                                "vue": {
                                    key: value
                                    for key, value in (
                                        remote_vue_shared
                                        | {
                                            "strictVersion": is_strict_version,
                                            "singleton": is_singleton,
                                            "import": is_import,
                                        }
                                    ).items()
                                    if value is not None
                                }
                            }
                            if remote_vue_shared is not None
                            else {}
                        )
                        start(
                            host_vue_version,
                            remote_vue_version,
                            host_shared,
                            remote_shared,
                        )
