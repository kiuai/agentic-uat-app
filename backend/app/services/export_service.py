"""Export orchestration service — delegates to format-specific exporters."""

from __future__ import annotations

from app.exporters.gherkin_exporter import GherkinExporter
from app.exporters.playwright_exporter import PlaywrightExporter
from app.exporters.pytest_exporter import PytestExporter
from app.exporters.robot_framework_exporter import RobotFrameworkExporter
from app.exporters.selenium_exporter import SeleniumExporter
from app.models.test_script import ScriptFormat


class ExportService:
    _exporters = {
        ScriptFormat.PLAYWRIGHT_TS: PlaywrightExporter(language="ts"),
        ScriptFormat.PLAYWRIGHT_JS: PlaywrightExporter(language="js"),
        ScriptFormat.SELENIUM_PYTHON: SeleniumExporter(),
        ScriptFormat.PYTEST: PytestExporter(),
        ScriptFormat.ROBOT_FRAMEWORK: RobotFrameworkExporter(),
        ScriptFormat.GHERKIN: GherkinExporter(),
    }

    def get_exporter(self, fmt: ScriptFormat):  # type: ignore[return]
        exporter = self._exporters.get(fmt)
        if exporter is None:
            raise ValueError(f"No exporter registered for format: {fmt}")
        return exporter
