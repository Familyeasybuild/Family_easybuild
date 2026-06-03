import datetime
import hashlib
import os
import shutil
import traceback
import zipfile
from xml.dom import minidom


def repo_suffix(repo_id):
    if repo_id.startswith("repository."):
        return repo_id.split(".", 1)[1]
    return repo_id


def resolve_repo_url(repo_id, env=os.environ):
    repo_url = env.get("KODI_REPO_URL")
    if repo_url:
        return repo_url.rstrip("/") + "/"
    suffix = repo_suffix(repo_id)
    return "https://" + suffix + ".github.io/" + suffix + "/"


class Generator:
    """
    Generate a Kodi repository from the addon folders in the repo root.
    Run from the tools directory.
    """

    def __init__(self):
        self.tools_path = os.path.abspath(os.path.dirname(os.path.realpath(__file__)))
        self.addonid = os.environ["KODI_REPO_ID"]
        self.repo_name = os.environ["KODI_REPO_NAME"]
        self.repo_version = os.environ["KODI_REPO_VERSION"]
        self.author = os.environ["KODI_REPO_AUTHOR"]
        self.summary = os.environ.get("KODI_REPO_SUMMARY", self.repo_name + " Repository")
        self.description = os.environ.get("KODI_REPO_DESCRIPTION", "Repository from " + self.repo_name + ".")
        self.output_path = os.environ.get("KODI_REPO_OUTPUT_PATH", "_" + repo_suffix(self.addonid) + "/")
        self.url = resolve_repo_url(self.addonid)
        self.excludes = os.environ.get("KODI_REPO_EXCLUDES", ".psd,.pyo,.pyc,.gitignore,.DS_Store").split(",")

        os.chdir(os.path.abspath(os.path.join(self.tools_path, os.pardir)))

        self._pre_run()
        self._generate_repo_files()
        self._generate_addons_file()
        self._generate_md5_file()
        self._generate_zip_files()

        print("Finished updating addons xml, md5 files and zipping addons")

    def _pre_run(self):
        if os.path.exists(self.output_path):
            shutil.rmtree(self.output_path)
        os.makedirs(self.output_path)

    def _generate_repo_files(self):
        action = "Update" if os.path.isfile(self.addonid + os.path.sep + "addon.xml") else "Create"
        print(action + " repository addon")

        with open(self.tools_path + os.path.sep + "template.xml", "r", encoding="utf-8") as template:
            template_xml = template.read()

        repo_xml = template_xml.format(
            addonid=self.addonid,
            name=self.repo_name,
            version=self.repo_version,
            author=self.author,
            summary=self.summary,
            description=self.description,
            url=self.url,
            output_path=self.output_path,
        )

        if not os.path.exists(self.addonid):
            os.makedirs(self.addonid)

        self._copy_repository_artwork()
        self._save_file(repo_xml, file=self.addonid + os.path.sep + "addon.xml")

    def _copy_repository_artwork(self):
        for asset in ("icon.png", "fanart.jpg"):
            target = os.path.join(self.addonid, asset)
            if os.path.isfile(target):
                continue

            source = self._find_repository_artwork(asset)
            if source:
                shutil.copy(source, target)
            else:
                print("**** " + asset + " missing for " + self.addonid)

    def _find_repository_artwork(self, asset):
        candidates = []
        configured_path = os.environ.get("KODI_REPO_ASSETS_PATH")
        if configured_path:
            candidates.append(configured_path)
        candidates.append("repository.myrepo")
        candidates.extend(
            entry
            for entry in os.listdir(".")
            if entry.startswith("repository.") and entry != self.addonid
        )

        seen = set()
        for candidate in candidates:
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            source = os.path.join(candidate, asset)
            if os.path.isfile(source):
                return source
        return None

    def _generate_zip_files(self):
        addons = os.listdir(".")
        for addon in addons:
            addon_xml_path = os.path.join(addon, "addon.xml")
            if not os.path.isfile(addon_xml_path):
                continue
            try:
                if not os.path.isdir(addon) or addon in {".git", self.output_path, self.tools_path}:
                    continue
                document = minidom.parse(addon_xml_path)
                for parent in document.getElementsByTagName("addon"):
                    version = parent.getAttribute("version")
                    addonid = parent.getAttribute("id")
                self._generate_zip_file(addon, version, addonid)
            except Exception:
                failure = traceback.format_exc()
                print("Kodi Repo Generator Exception:\n" + str(failure))

    def _generate_zip_file(self, path, version, addonid):
        print("Generate zip file for " + addonid + " " + version)
        filename = path + "-" + version + ".zip"
        try:
            with zipfile.ZipFile(filename, "w") as repo_zip:
                for root, dirs, files in os.walk(path + os.path.sep):
                    for file in files:
                        ext = os.path.splitext(file)[-1].lower()
                        if ext not in self.excludes:
                            repo_zip.write(os.path.join(root, file))

            addon_output_path = self.output_path + addonid
            if not os.path.exists(addon_output_path):
                os.makedirs(addon_output_path)

            output_zip = addon_output_path + os.path.sep + filename
            if os.path.isfile(output_zip):
                os.rename(output_zip, output_zip + "." + datetime.datetime.now().strftime("%Y%m%d%H%M%S"))
            shutil.move(filename, output_zip)
            shutil.copy(addonid + "/addon.xml", addon_output_path + os.path.sep + "addon.xml")
            self._copy_declared_assets(addonid, addon_output_path)
        except Exception:
            failure = traceback.format_exc()
            print("Kodi Repo Generator Exception:\n" + str(failure))

    def _copy_declared_assets(self, addonid, addon_output_path):
        addon_root = os.path.abspath(addonid)
        output_root = os.path.abspath(addon_output_path)
        document = minidom.parse(os.path.join(addonid, "addon.xml"))
        asset_paths = []

        for assets_node in document.getElementsByTagName("assets"):
            for asset_node in assets_node.childNodes:
                if asset_node.nodeType != asset_node.ELEMENT_NODE:
                    continue
                asset_path = self._node_text(asset_node).strip()
                if asset_path:
                    asset_paths.append(asset_path)

        for asset_path in dict.fromkeys(asset_paths):
            source = os.path.abspath(os.path.normpath(os.path.join(addonid, asset_path)))
            if not source.startswith(addon_root + os.path.sep) or not os.path.isfile(source):
                print("**** " + asset_path + " missing for " + addonid)
                continue

            target = os.path.abspath(os.path.normpath(os.path.join(addon_output_path, asset_path)))
            if not target.startswith(output_root + os.path.sep):
                print("**** skipped unsafe asset path " + asset_path + " for " + addonid)
                continue

            target_dir = os.path.dirname(target)
            if not os.path.exists(target_dir):
                os.makedirs(target_dir)
            shutil.copy(source, target)

    def _node_text(self, node):
        return "".join(
            child.data
            for child in node.childNodes
            if child.nodeType == child.TEXT_NODE
        )

    def _generate_addons_file(self):
        addons_xml = "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<addons>\n"
        for addon in os.listdir("."):
            addon_xml_path = os.path.join(addon, "addon.xml")
            if not os.path.isfile(addon_xml_path):
                continue
            try:
                xml_lines = open(addon_xml_path, "r", encoding="utf-8", errors="ignore").read().splitlines()
                addon_xml = ""
                for line in xml_lines:
                    if line.find("<?xml") >= 0:
                        continue
                    addon_xml += str(line.rstrip() + "\n")
                addons_xml += addon_xml.rstrip() + "\n\n"
            except Exception:
                failure = traceback.format_exc()
                print("Excluding %s for %s" % (str(addon_xml_path), str(addon)))
                print("Exception Details:")
                print(str(failure))

        addons_xml = addons_xml.strip() + "\n</addons>\n"
        self._save_file(addons_xml, file=self.output_path + "addons.xml")

    def _generate_md5_file(self):
        try:
            hash_object = hashlib.md5()
            with open((self.output_path + "addons.xml"), "rb") as addons_file:
                hash_object.update(addons_file.read())
            self._save_file(hash_object.hexdigest(), file=self.output_path + "addons.xml.md5")
        except Exception:
            failure = traceback.format_exc()
            print("**** An error occurred creating addons.xml.md5 file!\n")
            print("Kodi Repo Generator Exception:\n" + str(failure))

    def _save_file(self, data, file):
        try:
            with open(file, "w", encoding="utf-8", errors="ignore") as f:
                f.write(data)
        except Exception:
            failure = traceback.format_exc()
            print("**** An error occurred saving %s file!\n")
            print("Kodi Repo Generator Exception:\n" + str(failure))


if __name__ == "__main__":
    Generator()
