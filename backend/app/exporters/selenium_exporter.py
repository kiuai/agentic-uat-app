"""Selenium Python exporter."""

from __future__ import annotations

from typing import Any

from jinja2 import Template

from app.exporters.base import BaseExporter

_TEMPLATE = """from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import unittest


class {{ title | replace(' ', '') }}Test(unittest.TestCase):
    def setUp(self):
        self.driver = webdriver.Chrome()
        self.driver.implicitly_wait(10)
        self.wait = WebDriverWait(self.driver, 10)

    def tearDown(self):
        self.driver.quit()

    def test_{{ title | lower | replace(' ', '_') }}(self):
        \"\"\"{{ title }}
        Preconditions: {{ preconditions | join('; ') }}
        \"\"\"
{% for step in steps %}
        # Step {{ step.step_number }}: {{ step.description }}
{% if step.action == 'navigate' %}
        self.driver.get('{{ step.target }}')
{% elif step.action == 'fill' %}
        element = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//*[@aria-label='{{ step.target }}']")))
        element.clear()
        element.send_keys('{{ step.input_data or '' }}')
{% elif step.action == 'click' %}
        self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(),'{{ step.target }}')]"))).click()
{% endif %}
{% endfor %}


if __name__ == '__main__':
    unittest.main()
"""


class SeleniumExporter(BaseExporter):
    def __init__(self) -> None:
        self._template = Template(_TEMPLATE)

    def export(self, test_case: dict[str, Any]) -> str:
        return self._template.render(
            title=test_case.get("title", "Test"),
            preconditions=test_case.get("preconditions", []),
            steps=test_case.get("steps", []),
        )
