import argparse
import asyncio
import json
import re

from collections import defaultdict
from natsort import natsorted
from pathlib import Path
from playwright.async_api import expect, async_playwright

parser = argparse.ArgumentParser()
parser.add_argument(
    "--comparison",
    help="use the same (newest) version for host and remote",
    action="store_true",
)
args = parser.parse_args()


# https://github.com/microsoft/playwright-python
async def scrape(url):
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page()
        page.set_default_timeout(3000)
        messages = defaultdict(list)
        page.on("console", lambda message: messages[message.type].append(message.text))
        await page.goto(url)
        await page.screenshot(path="screenshot.png")
        host_version = await page.locator("#hostVersion").inner_text()
        remote_version = (
            await page.locator("#remoteVersion").inner_text()
            if await page.locator("#remoteVersion").is_visible()
            else None
        )
        same_instance = (
            json.loads(await page.locator("#sameInstance").inner_text())
            if await page.locator("#sameInstance").is_visible()
            else None
        )
        await browser.close()
        return {
            "messages": messages,
            "host": host_version,
            "remote": remote_version,
            "singleton": same_instance,
        }


async def run(
    host_package_version, remote_package_version, host_shared_hints, remote_shared_hints
):
    pnpm_lock_yaml = Path("..", "pnpm-lock.yaml")
    pnpm_lock_yaml_bytes = pnpm_lock_yaml.read_bytes()

    host_package_json = Path("layout", "package.json")
    host_package_json_text = host_package_json.read_text("utf-8")
    host_package_json_data = json.loads(host_package_json_text)
    host_package_json_data["dependencies"]["vue"] = host_package_version
    host_package_json_data["devDependencies"][
        "@vue/compiler-sfc"
    ] = host_package_version
    host_package_json.write_text(
        json.dumps(host_package_json_data, indent=2) + "\n", "utf-8"
    )

    remote_package_json = Path("home", "package.json")
    remote_package_json_text = remote_package_json.read_text("utf-8")
    remote_package_json_data = json.loads(remote_package_json_text)
    remote_package_json_data["dependencies"]["vue"] = remote_package_version
    remote_package_json_data["devDependencies"][
        "@vue/compiler-sfc"
    ] = remote_package_version
    remote_package_json.write_text(
        json.dumps(remote_package_json_data, indent=2) + "\n", "utf-8"
    )

    host_shared_json = Path("layout", "shared.json")
    host_shared_json_text = host_shared_json.read_text("utf-8")
    host_shared_json.write_text(json.dumps(host_shared_hints, indent=2), "utf-8")

    remote_shared_json = Path("home", "shared.json")
    remote_shared_json_text = remote_shared_json.read_text("utf-8")
    remote_shared_json.write_text(json.dumps(remote_shared_hints, indent=2), "utf-8")

    try:
        install = await asyncio.create_subprocess_exec(
            "pnpm", "install", stdout=asyncio.subprocess.DEVNULL
        )
        await install.wait()

        start = await asyncio.create_subprocess_exec(
            "pnpm",
            "start",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        host = None
        remote = None
        url = None

        while not (host and remote and url):
            line = (await start.stdout.readline()).decode("utf-8").rstrip()
            # print(line)
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

        result = {
            "actual": await scrape(url),
            "config": {
                "host": {
                    "package": host_package_version,
                    "shared": host_shared_hints,
                },
                "remote": {
                    "package": remote_package_version,
                    "shared": remote_shared_hints,
                },
            },
        }
        start.terminate()
        await start.wait()
        return result
    except Exception as exception:
        print(exception)
    finally:
        pnpm_lock_yaml.write_bytes(pnpm_lock_yaml_bytes)
        host_package_json.write_text(host_package_json_text, "utf-8")
        remote_package_json.write_text(remote_package_json_text, "utf-8")
        host_shared_json.write_text(host_shared_json_text, "utf-8")
        remote_shared_json.write_text(remote_shared_json_text, "utf-8")


async def main():
    count = 0

    results = []

    newVersion = "^3.3.8"
    oldVersion = "^3.0.11"

    # https://webpack.js.org/plugins/module-federation-plugin/#sharing-hints
    for host_package_version in [newVersion, oldVersion]:
        for remote_package_version in [newVersion, oldVersion]:
            if (
                not args.comparison and host_package_version == remote_package_version
            ) or (
                args.comparison
                and (
                    host_package_version != newVersion
                    or remote_package_version != newVersion
                )
            ):
                continue

            for host_vue_shared, remote_vue_shared in [
                (
                    None,
                    None,
                ),
                (
                    {},
                    {},
                ),
                (
                    {"version": host_package_version.lstrip("^")},
                    {"version": remote_package_version.lstrip("^")},
                ),
                (
                    {"requiredVersion": host_package_version},
                    {"requiredVersion": remote_package_version},
                ),
                (
                    {
                        "version": host_package_version.lstrip("^"),
                        "requiredVersion": host_package_version,
                    },
                    {
                        "version": remote_package_version.lstrip("^"),
                        "requiredVersion": remote_package_version,
                    },
                ),
            ]:
                for is_strict_version in [None, False, True]:
                    if is_strict_version is not None and (
                        host_vue_shared is None
                        or "requiredVersion" not in host_vue_shared
                    ):
                        continue
                    for is_singleton in [None, False, True]:
                        if is_singleton is not None and host_vue_shared is None:
                            continue
                        for is_import in [None, False]:
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

                            count += 1

                            print(
                                count,
                                host_package_version,
                                remote_package_version,
                                json.dumps(host_shared),
                                json.dumps(remote_shared),
                            )

                            result = await run(
                                host_package_version,
                                remote_package_version,
                                host_shared,
                                remote_shared,
                            )

                            if not result:
                                return

                            print()
                            print(json.dumps(result))
                            print()

                            results.append(result)

    results_json = Path("results.json")
    results_json.write_text(
        json.dumps(natsorted(results, json.dumps), indent=2), "utf-8"
    )


asyncio.run(main())
