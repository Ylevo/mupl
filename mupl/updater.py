import logging
import sys
from io import BytesIO
from pathlib import Path
from threading import Timer
from zipfile import ZipFile

import requests
from packaging import version

from mupl import __version__
from mupl.utils.config import root_path, config, TRANSLATION

logger = logging.getLogger("mupl")

skip_update_files = ["name_id_map.json"]


def raise_error(ex):
    raise ex


def remove_other_langs(current_downloaded_langs, zip_files):
    """Remove extra languages from update not already downloaded."""
    for zfile in reversed(zip_files):
        lang_files = [
            l for l in Path(zfile.filename).parts if "loc" in Path(zfile.filename).parts
        ]
        if lang_files:
            lang_file = next(
                filter(lambda x: x.endswith((".json", ".md")), lang_files), None
            )
            if lang_file not in current_downloaded_langs:
                zip_files.remove(zfile)
    return zip_files


def check_for_update():
    """Check For any program updates."""
    logger.debug("Looking for program update.")

    update = False
    local_version = version.parse(__version__)
    remote_release = requests.get(
        "https://api.github.com/repos/ArdaxHz/mupl/releases/latest"
    )
    if remote_release.ok:
        remote_release_json = remote_release.json()
        remote_version = version.parse(remote_release_json["tag_name"])

        if remote_version > local_version:
            print(
                TRANSLATION["new_update_found"].format(
                    local_version, remote_version, remote_release_json["name"]
                )
            )
            logger.info(
                f"Update found: {local_version} => {remote_version}: {remote_release_json['name']}."
            )
            if remote_version.major != local_version.major:
                print(
                    TRANSLATION["new_update_warning"]
                    + "\nhttps://github.com/ArdaxHz/mupl/releases/latest"
                )

            timeout = 10
            t = Timer(timeout, raise_error, [ValueError(TRANSLATION["not_updating"])])
            t.start()
            answer = input(TRANSLATION["input_want_update"])
            t.cancel()

            if answer.lower() in ["true", "1", "t", "y", "yes"]:
                update = True
            else:
                update = False

            if not update:
                print(TRANSLATION["not_updating"])
                logger.info(f"Skipping update {remote_version}")
                return False

            current_downloaded_langs = [
                lang.name for lang in root_path.rglob("loc/*.json")
            ]
            if "en.json" not in current_downloaded_langs:
                current_downloaded_langs.append("en.json")

            logger.debug(f"{current_downloaded_langs=}")

            zip_resp = requests.get(remote_release_json["zipball_url"])
            if zip_resp.ok:
                myzip = ZipFile(BytesIO(zip_resp.content))
                zip_root = [z for z in myzip.infolist() if z.is_dir()][0].filename
                zip_files = [z for z in myzip.infolist() if not z.is_dir()]
                zip_files = remove_other_langs(current_downloaded_langs, zip_files)

                for fileinfo in zip_files:
                    filename = root_path.joinpath(
                        fileinfo.filename.replace(zip_root, "")
                    )
                    if filename.name in skip_update_files:
                        logger.debug(f"Skipping update for {filename.name}")
                        continue

                    filename.parent.mkdir(parents=True, exist_ok=True)
                    file_data = myzip.read(fileinfo)

                    with open(filename, "wb") as fopen:
                        fopen.write(file_data)

                Path(config["paths"]["mdauth_path"]).unlink(missing_ok=True)
                print(TRANSLATION["successfully_updated"])
                logger.info(
                    f"Updated to version {remote_version}: {remote_release_json['name']}."
                )
                sys.exit()
        else:
            return False

    logger.info("Updating error.")
    print(TRANSLATION["update_error"])
