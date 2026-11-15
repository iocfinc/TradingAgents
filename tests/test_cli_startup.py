from __future__ import annotations

import subprocess
import sys


def test_cli_main_import_does_not_load_trading_graph() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, cli.main; print('tradingagents.graph.trading_graph' in sys.modules)",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False"
