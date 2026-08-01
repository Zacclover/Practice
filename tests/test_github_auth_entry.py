import re
import unittest
from pathlib import Path


SOURCE = (Path(__file__).resolve().parents[1] / "index.html").read_text(encoding="utf-8")


class GitHubAuthEntryTests(unittest.TestCase):
    def test_tool_area_has_an_accessible_hidden_cloud_login_entry(self):
        self.assertIn('id="cloudLoginButton"', SOURCE)
        self.assertRegex(
            SOURCE,
            r'<button[^>]*\bid="cloudLoginButton"[^>]*\bhidden\b[^>]*>',
        )
        self.assertIn('使用 GitHub 登录', SOURCE)
        self.assertIn('class="workspace-tab-add"', SOURCE)

    def test_valid_config_reveals_login_and_invalid_config_keeps_it_hidden(self):
        self.assertIn('function initializeCloudAuthEntry()', SOURCE)
        function = re.search(
            r'function initializeCloudAuthEntry\(\) \{(?P<body>.*?)\n    \}',
            SOURCE,
            re.S,
        )
        self.assertIsNotNone(function)
        body = function.group('body')
        self.assertIn('getCloudRuntimeConfig()', body)
        self.assertIn('if (!config.enabled)', body)
        self.assertIn('cloudLoginButton.hidden = false', body)

    def test_login_uses_github_authorize_endpoint_and_current_origin_path(self):
        self.assertIn('function startGitHubLogin()', SOURCE)
        function = re.search(r'function startGitHubLogin\(\) \{(?P<body>.*?)\n    \}', SOURCE, re.S)
        self.assertIsNotNone(function)
        body = function.group('body')
        self.assertIn('/auth/v1/authorize', body)
        self.assertIn('provider=github', body)
        self.assertIn('redirect_to', body)
        self.assertIn('window.location.origin', body)
        self.assertIn('window.location.pathname', body)
        self.assertIn('window.location.assign', body)

    def test_authenticated_github_profile_replaces_login_button_and_offers_logout(self):
        self.assertIn('id="cloudAccountMenu"', SOURCE)
        self.assertIn('id="cloudAccountAvatar"', SOURCE)
        self.assertIn('id="cloudAccountName"', SOURCE)
        self.assertIn('id="cloudLogoutButton"', SOURCE)
        self.assertIn('function renderCloudAccount(profile)', SOURCE)
        self.assertIn('function signOutCloudAccount()', SOURCE)
        self.assertIn("/auth/v1/user", SOURCE)
        self.assertIn("/auth/v1/logout", SOURCE)
        self.assertIn('cloudLoginButton.hidden = true', SOURCE)
        self.assertIn('cloudAccountMenu.hidden = false', SOURCE)

    def test_auth_entry_does_not_embed_sdk_or_secret_credentials(self):
        self.assertNotIn('supabase.createClient', SOURCE)
        self.assertNotRegex(SOURCE.lower(), r'service_role|secret[_-]?key')


if __name__ == '__main__':
    unittest.main()
