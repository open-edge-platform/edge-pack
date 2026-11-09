import os
import re
import stat
import yaml
import requests
from .log import ep_logger

# Maximum allowed size for downloaded recipe files (1 MiB). Prevents disk
# exhaustion from a malicious or compromised upstream manifest server.
_MAX_RECIPE_SIZE = 1 * 1024 * 1024

manifest_repo = None


def _safe_url(url: str) -> str:
    """Truncate and sanitize a URL for safe inclusion in log messages."""
    # Strip the scheme+host so only the path (the variable portion) is logged,
    # reducing information exposure if logs leak.
    truncated = re.sub(r'^https?://[^/]+', '', url)
    return truncated[:200]


def _sanitize_msg(msg: str) -> str:
    """Strip control characters and limit length to prevent log injection."""
    sanitized = ''.join(c if 32 <= ord(c) < 127 or c in ('\n', '\r', '\t') else '?' for c in msg)
    return sanitized[:500]


class AutoUpdater:
    def __init__(self, ui_version, debug_level: str = "MUTE"):
        update_logger = ep_logger(name="update_log", log_file="/var/log/edgepack/update.log", level=debug_level)
        self.logger = update_logger.get_logger()
        self.sync(ui_version)

    def _fetch(self, url):
        session = requests.Session()
        session.trust_env = False
        headers = {'User-Agent': 'curl/8.5.0'}
        response = session.get(url, headers=headers, proxies={'http': None, 'https': None}, timeout=10)
        response.raise_for_status()
        return response.text

    def _parse_listing(self, html, base_url):
        # Apache directory listing rows: <a href="..."> followed by date in next td
        dirs, files = [], []
        for match in re.finditer(r'<a href="([^"?/][^"]*)">[^<]+</a>\s*</td><td[^>]*>\s*([\d-]+ [\d:]+)', html):
            name, date = match.group(1), match.group(2)
            if name.endswith('/'):
                dirs.append((base_url + name, date))
            else:
                files.append((base_url + name, date))
        return dirs, files

    _MAX_CRAWL_DEPTH = 10  # Prevent unbounded recursion from directory-bomb payloads

    def _crawl(self, url, depth: int = 0):
        if not url:
            return []
        if depth > self._MAX_CRAWL_DEPTH:
            self.logger.debug("Crawl depth exceeded for %s — stopping", _safe_url(url))
            return []
        html = self._fetch(url)
        dirs, files = self._parse_listing(html, url)
        results = []
        for file_url, date in files:
            if file_url.endswith('.yml') or file_url.endswith('.yaml'):
                results.append((date, file_url))
        for dir_url, _ in dirs:
            results.extend(self._crawl(dir_url, depth + 1))
        return results

    def get_compatible(self, ui_version):
        all_yamls = self._crawl(manifest_repo)
        if not all_yamls:
            return None

        compatible = {"date": [], "url": []}
        for date, url in all_yamls:
            try:
                content = self._fetch(url)
                parsed = yaml.safe_load(content)
                if not isinstance(parsed, dict):
                    self.logger.debug("Skipping %s: top-level value is not a mapping", _safe_url(url))
                    continue
                version_field = parsed.get('version', '')
                # version_field format: "0.1-0002" — split on '-' to get ["0.1", "0002"]
                parts = str(version_field).split('-')
                if len(parts) == 2 and parts[0] == ui_version:
                    compatible["date"].append(date)
                    compatible["url"].append(url)
            except Exception as e:
                self.logger.debug("Skipping %s: %s", _safe_url(url), _sanitize_msg(str(e)))

        if not compatible:
            self.logger.warning("No compatible yaml found for tui_version %s", ui_version)
            return None

        return compatible

    def get_latest(self, ui_version):
        #return the url and date of the latest compatible recipe for the ui
        all_yamls = self._crawl(manifest_repo)
        if not all_yamls:
            return None

        compatible = []
        for date, url in all_yamls:
            try:
                content = self._fetch(url)
                parsed = yaml.safe_load(content)
                if not isinstance(parsed, dict):
                    continue
                version_field = parsed.get('version', '')
                # version_field format: "0.1-0002" — split on '-' to get ["0.1", "0002"]
                parts = str(version_field).split('-')
                if len(parts) == 2 and parts[0] == ui_version:
                    compatible.append({'ui_version': parts[0], 'recipe_version': parts[1], 'date': date, 'url': url})
            except Exception as e:
                self.logger.debug("Skipping %s: %s", _safe_url(url), _sanitize_msg(str(e)))

        if not compatible:
            self.logger.warning("No compatible recipe found for tui_version %s", ui_version)
            return None

        # Pick highest minor version number ("0004" > "0002")
        latest = max(compatible, key=lambda x: x['recipe_version'])
        return latest

    def revert(self):
        return

    def sync(self, ui_version):
        try:
            self._crawl(manifest_repo)
        except requests.exceptions.Timeout:
            self.logger.debug("Request timed out. Check network connectivity.")
            self.logger.warning("Failed to fetch the latest installation recipe from repo.")
        except requests.exceptions.RequestException as e:
            self.logger.debug("Request failed: %s", _sanitize_msg(str(e)))
            self.logger.warning("Failed to fetch the latest installation recipe from repo.")

        latest_recipe = self.get_latest(ui_version)
        compatible_recipe = self.get_compatible(ui_version)

        if not latest_recipe or not compatible_recipe:
            self.logger.warning("No compatible recipe found for ui_version %s", ui_version)
            return

        if latest_recipe["url"] in compatible_recipe["url"]:
            self.logger.info("latest recipe from repo: %s", _safe_url(latest_recipe["url"]))
            dest_dir = os.path.expanduser('~/.edgepack/recipe')
            os.makedirs(dest_dir, exist_ok=True)
            # Restrict recipe directory permissions to owner-only (0o700).
            try:
                os.chmod(dest_dir, stat.S_IRWXU)
            except OSError:
                pass  # best-effort; non-root may not have permission
            original_name = os.path.splitext(os.path.basename(latest_recipe["url"]))[0]
            full_version = f"{latest_recipe['ui_version']}-{latest_recipe['recipe_version']}"
            dest = os.path.join(dest_dir, f"{original_name}-{full_version}.yml")
            content = self._fetch(latest_recipe["url"])

            # Validate downloaded content before writing: enforce size limit and
            # ensure it is a parseable YAML mapping so a malicious upstream cannot
            # write arbitrary binary or oversized data to disk.
            if len(content.encode('utf-8')) > _MAX_RECIPE_SIZE:
                self.logger.warning("Recipe download exceeded %d bytes — rejecting", _MAX_RECIPE_SIZE)
                return
            parsed = yaml.safe_load(content)
            if not isinstance(parsed, dict):
                self.logger.warning("Recipe top-level value is not a YAML mapping — rejecting")
                return

            # Stage the downloaded content in a temp file first so it is never
            # written directly to its final location until validation passes.
            tmp_path = dest + '.tmp'
            try:
                with open(tmp_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                os.chmod(tmp_path, stat.S_IRUSR | stat.S_IWUSR)  # 0o600 — owner read/write only
                os.replace(tmp_path, dest)  # atomic move on POSIX; dest is only visible after validation succeeds
            except OSError:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                raise
            self.logger.info("Downloaded latest template to %s", dest)


# Guard so the module can be run standalone (e.g. for testing/validation) but
# does not auto-execute on import — keeps startup fast and avoids debug log noise.
if __name__ == "__main__":
    AutoUpdater("0.1", "DEBUG")
