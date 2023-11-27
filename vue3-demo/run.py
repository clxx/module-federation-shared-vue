import asyncio
import json
import re

from collections import defaultdict
from natsort import natsorted, natsort_keygen
from pathlib import Path
from playwright.async_api import expect, async_playwright


class NestedDict(dict):
    def __missing__(self, key):
        self[key] = [] if key == "hints" else NestedDict()
        return self[key]


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
        host_version = (
            await page.locator("#hostVersion").inner_text()
            if await page.locator("#hostVersion").is_visible()
            else None
        )
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


async def serve(
    host_package_version,
    remote_package_version,
    host_shared_hints,
    remote_shared_hints,
    needs_install,
    log_description,
    info_log,
    warnings_log,
):
    if needs_install:
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

    Path("layout", "shared.json").write_text(
        json.dumps(host_shared_hints, indent=2), "utf-8"
    )

    Path("home", "shared.json").write_text(
        json.dumps(remote_shared_hints, indent=2), "utf-8"
    )

    if needs_install:
        install = await asyncio.create_subprocess_exec(
            "pnpm", "install", stdout=asyncio.subprocess.DEVNULL, cwd=".."
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
    warnings = False

    while not (host and remote and url):
        line = (await start.stdout.readline()).decode("utf-8").rstrip()
        print(log_description, line, file=info_log)
        if match := re.fullmatch(
            r"layout start: <i> \[webpack-dev-server\] Loopback: (.+)", line
        ):
            url = match.group(1)
        elif match := re.fullmatch(
            r"(home|layout) start: webpack \d+\.\d+\.\d+ compiled (successfully|with \d+ warnings) in \d+ ms",
            line,
        ):
            if match.group(1) == "layout":
                host = True
            elif match.group(1) == "home":
                remote = True
            if match.group(2) != "successfully":
                warnings = True

    result = (
        None
        if warnings
        else {
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
    )

    start.terminate()

    await start.wait()

    while not start.stdout.at_eof():
        line = (await start.stdout.readline()).decode("utf-8").rstrip()
        print(log_description, line, file=info_log)

    if not result:
        print(
            log_description,
            "Skipped result due to compile errors",
            file=warnings_log,
            flush=True,
        )

    return result


def runs():
    # "3.3.9" is the most recent Vue - this is deliberately not the latest version!
    newVersion = "^3.3.8"
    oldVersion = "^3.0.11"

    runs_set = set()
    runs_list = []

    # https://webpack.js.org/plugins/module-federation-plugin/#sharing-hints
    for host_package_version in [
        newVersion,
        newVersion.lstrip("^"),
        oldVersion,
        oldVersion.lstrip("^"),
    ]:
        for remote_package_version in [
            newVersion,
            newVersion.lstrip("^"),
            oldVersion,
            oldVersion.lstrip("^"),
        ]:
            for baseline in [False, True]:
                if (
                    not baseline and host_package_version == remote_package_version
                ) or (
                    baseline
                    and (
                        host_package_version != remote_package_version
                        or host_package_version
                        not in [newVersion, newVersion.lstrip("^")]
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
                    # https://webpack.js.org/plugins/module-federation-plugin/#version
                    # "By default, webpack uses the version from the package.json file of the dependency."
                    # Therefore we do not set version here explicitly...
                    (
                        {"requiredVersion": host_package_version},
                        {"requiredVersion": remote_package_version},
                    ),
                ]:
                    for is_strict_version in [None, False, True]:
                        if is_strict_version is not None and (
                            host_vue_shared is None
                            or "requiredVersion" not in host_vue_shared
                        ):
                            continue

                        for is_singleton in [None, True]:
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

                                args = [
                                    host_package_version,
                                    remote_package_version,
                                    host_shared,
                                    remote_shared,
                                ]

                                args_json = json.dumps(args)

                                if args_json not in runs_set:
                                    runs_set.add(args_json)
                                    runs_list.append(args)

    return natsorted(runs_list, lambda args: f"{args[0]} {args[1]}")


def generate_hints_chooser(results):
    natsort_key = natsort_keygen()

    hints_chooser_wizard = NestedDict()

    for result in results:
        host = result["actual"]["host"] or ""
        remote = result["actual"]["remote"] or ""
        value = result["actual"]["singleton"]
        singleton = json.dumps(value) if value else ""
        messages = result["actual"]["messages"]
        if messages:
            if list(messages.keys()) != ["warning"]:
                raise Exception("Unknown message type!")
            warning = json.dumps(messages["warning"])
        else:
            warning = json.dumps([])
        hints = hints_chooser_wizard["host"][host]["remote"][remote]["singleton"][
            singleton
        ]["warning"][warning]["hints"]
        hints.append(result["config"])
        hints.sort(key=lambda hint: natsort_key(json.dumps(hint)))

    Path("hints_chooser_wizard.json").write_text(
        json.dumps(hints_chooser_wizard, indent=2, sort_keys=True), "utf-8"
    )


async def main():
    pnpm_lock_yaml = Path("..", "pnpm-lock.yaml")
    pnpm_lock_yaml_bytes = pnpm_lock_yaml.read_bytes()

    host_package_json = Path("layout", "package.json")
    host_package_json_bytes = host_package_json.read_bytes()

    remote_package_json = Path("home", "package.json")
    remote_package_json_bytes = remote_package_json.read_bytes()

    host_shared_json = Path("layout", "shared.json")
    host_shared_json_bytes = host_shared_json.read_bytes()

    remote_shared_json = Path("home", "shared.json")
    remote_shared_json_bytes = remote_shared_json.read_bytes()

    with open("info.log", "w", encoding="utf-8") as info_log, open(
        "warning.log", "w", encoding="utf-8"
    ) as warning_log, open("error.log", "w", encoding="utf-8") as error_log:
        try:
            results = []

            old_install = None

            sorted_runs = runs()

            count = 0
            total = len(sorted_runs)

            for args in sorted_runs:
                count += 1

                log_description = f"{count:03}/{total:03}"

                print(
                    log_description,
                    "host package version:",
                    args[0],
                    "|",
                    "remote package version:",
                    args[1],
                    "|",
                    "host shared:",
                    json.dumps(args[2]),
                    "|",
                    "remote shared:",
                    json.dumps(args[3]),
                    file=info_log,
                )

                result = await serve(
                    *args,
                    old_install != f"{args[0]} {args[1]}",
                    log_description,
                    info_log,
                    warning_log,
                )

                old_install = f"{args[0]} {args[1]}"

                print(log_description, file=info_log)
                print(
                    log_description,
                    "scraped result:",
                    json.dumps(result),
                    file=info_log,
                )
                print(file=info_log)

                if result:
                    results.append(result)

            results_json = Path("results.json")

            results_json_data = natsorted(results, json.dumps)

            results_json.write_text(json.dumps(results_json_data, indent=2), "utf-8")
        except Exception as exception:
            print(log_description, exception, file=error_log, flush=True)
        finally:
            pnpm_lock_yaml.write_bytes(pnpm_lock_yaml_bytes)
            host_package_json.write_bytes(host_package_json_bytes)
            remote_package_json.write_bytes(remote_package_json_bytes)
            host_shared_json.write_bytes(host_shared_json_bytes)
            remote_shared_json.write_bytes(remote_shared_json_bytes)

    generate_hints_chooser(results_json_data)


asyncio.run(main())
