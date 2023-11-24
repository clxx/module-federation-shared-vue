import json

from natsort import natsort_keygen
from pathlib import Path


class NestedDict(dict):
    def __missing__(self, key):
        self[key] = [] if key == "hints" else NestedDict()
        return self[key]


natsort_key = natsort_keygen()


def main():
    results = json.loads(Path("results_different_versions.json").read_text("utf-8"))

    hints_chooser_wizard = NestedDict()

    for result in results:
        host = result["actual"]["host"]
        remote = result["actual"]["remote"] or ""
        value = result["actual"]["singleton"]
        singleton = json.dumps(value) if value else ""
        messages = result["actual"]["messages"]
        if messages:
            if list(messages.keys()) != ["warning"]:
                raise Exception("Unknown message type!")
            warnings = messages["warning"]
            if len(warnings) != 1:
                raise Exception("Not a single warning!")
            warning = warnings[0]
        else:
            warning = ""
        hints = hints_chooser_wizard["host"][host]["remote"][remote]["singleton"][
            singleton
        ]["warning"][warning]["hints"]
        hints.append(result["config"])
        hints.sort(key=lambda hint: natsort_key(json.dumps(hint)))

    Path("hints_chooser_wizard.json").write_text(
        json.dumps(hints_chooser_wizard, indent=2, sort_keys=True), "utf-8"
    )


main()
