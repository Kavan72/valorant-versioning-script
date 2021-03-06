import os
import time
import json
import shutil
import datetime

import requests
import subprocess

from git import Repo
from git import Actor
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.realpath(__file__))
REPO_DIR = os.path.join(BASE_DIR, "valorant")
TEMP_DIR = os.path.join(BASE_DIR, "temp")

GITHUB_USERNAME = os.environ['GITHUB_USERNAME']
GITHUB_EMAIL = os.environ['GITHUB_EMAIL']
GITHUB_PASSWORD = os.environ['GITHUB_PASSWORD']
GITHUB_REPOSITORY_NAME = os.environ['GITHUB_REPOSITORY_NAME']

AUTHOR = Actor(GITHUB_USERNAME, GITHUB_EMAIL)
REMOTE_URL = f"https://{GITHUB_USERNAME}:{GITHUB_PASSWORD}@github.com/{GITHUB_USERNAME}/{GITHUB_REPOSITORY_NAME}.git"


def get_valorant_version(exe_file_path):
    exe_file_data = open(exe_file_path, "rb").read()

    pattern = '++Ares-Core+'.encode('utf-16-le')
    pos = exe_file_data.find(pattern) + len(pattern)

    branch, build_date, build_ver, version = filter(None, exe_file_data[pos:pos + 96].decode('utf-16-le').split('\x00'))

    return {
        'branch': branch,
        'build_date': build_date,
        'build_ver': build_ver,
        'version': version,
        'version_for_api': '-'.join((branch, 'shipping', build_ver, version.rsplit('.', 1)[-1].lstrip('0')))
    }


def push_to_github(commit_msg: str, remote_name: str = 'origin'):

    repo = Repo(REPO_DIR)

    if repo.index.diff(None) or repo.untracked_files:
        repo.git.add(all=True)
        repo.index.commit(commit_msg, author=AUTHOR, committer=AUTHOR)

        origin = repo.remote(name=remote_name)
        origin.push('master')


def check_update_for_region(region_data):
    patch_url = region_data["patch_url"]
    region = str(region_data["valid_shards"]["live"][0]).upper()

    os.makedirs(f"{REPO_DIR}/{region}", exist_ok=True)

    try:
        subprocess.check_call(
            [
                "./ManifestDownloader",
                patch_url,
                "-b",
                "https://valorant.secure.dyn.riotcdn.net/channels/public/bundles",
                "-f",
                "ShooterGame/Binaries/Win64/VALORANT-Win64-Shipping.exe",
                "-o",
                TEMP_DIR,
                "-t",
                "4"
            ], timeout=60)
    except:
        return shutil.rmtree(TEMP_DIR)
    else:

        version_data = get_valorant_version(f"{TEMP_DIR}/ShooterGame/Binaries/Win64/VALORANT-Win64-Shipping.exe")

        with open(f"{REPO_DIR}/{region}/version.json", "w") as out_file:
            out_file.write(json.dumps(
                {
                    **version_data,
                    'patch_url': patch_url,
                    'region': region
                }
            ))

        push_to_github(commit_msg=f"Update version for {region} to {version_data['version']}")


def main():

    try:
        Repo.clone_from(REMOTE_URL, REPO_DIR)
    except:
        pass

    while True:

        valorant_release = requests.get("https://clientconfig.rpg.riotgames.com/api/v1/config/public?namespace=keystone.products.valorant.patchlines", timeout=1)

        for configuration in json.loads(valorant_release.content)["keystone.products.valorant.patchlines.live"]["platforms"]["win"]["configurations"]:
            check_update_for_region(configuration)

        shutil.rmtree(TEMP_DIR)
        time.sleep(300)

        print(f"Last checked on:- {datetime.datetime.now()}")


if __name__ == '__main__':
    main()
