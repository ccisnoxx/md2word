"""验证上线开关和测试公司名单的配置合同。"""

from os import environ
from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError

from app.core.config import Settings


class TableValueRolloutSettingsTests(TestCase):
    def test_empty_list_and_turned_off_switch_deny_enrollment(self) -> None:
        with patch.dict(environ, clear=True):
            settings = Settings(_env_file=None, document_table_value_pdf_binding_enabled=True)
            self.assertFalse(settings.allows_table_value_pdf_binding("tenant_a", "company_a"))
            settings = Settings(_env_file=None,
                                document_table_value_pdf_binding_company_allowlist=[["tenant_a", "company_a"]])
            self.assertFalse(settings.allows_table_value_pdf_binding("tenant_a", "company_a"))

    def test_environment_requires_exact_tenant_company_pair(self) -> None:
        with patch.dict(environ, {
            "DOCUMENT_TABLE_VALUE_PDF_BINDING_ENABLED": "true",
            "DOCUMENT_TABLE_VALUE_PDF_BINDING_COMPANY_ALLOWLIST": '[["tenant_a","company_a"]]',
        }, clear=True):
            settings = Settings(_env_file=None)
            self.assertTrue(settings.allows_table_value_pdf_binding("tenant_a", "company_a"))
            self.assertFalse(settings.allows_table_value_pdf_binding("tenant_b", "company_a"))
            self.assertFalse(settings.allows_table_value_pdf_binding("tenant_a", "company_b"))

    def test_rejects_incomplete_or_blank_ids(self) -> None:
        for value in ('[["tenant_a"]]', '[["tenant_a"," "]]'):
            with self.subTest(value=value), patch.dict(environ, {
                "DOCUMENT_TABLE_VALUE_PDF_BINDING_COMPANY_ALLOWLIST": value,
            }, clear=True), self.assertRaises(ValidationError):
                Settings(_env_file=None)
