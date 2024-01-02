import json
import urllib
from pathlib import Path
from unicodedata import normalize

import requests
import wget
from rich.console import Console
from rich.table import Table
from rich.traceback import install

c = Console()
install()


class ClientCCMA:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36 uacq"
            }
        )
        self.BASE_URL = "https://www.ccma.cat"
        self.BASE_API = "https://api.ccma.cat"
        self.DINAMICS_API = "https://dinamics.ccma.cat"

    def get_videos_api(self, programatv_id, items_pagina=10):
        api_url = f"{self.BASE_API}/videos?version=2.0&items_pagina=1&programatv_id={programatv_id}"
        try:
            api_response = self.session.get(api_url).json()
            total_items = api_response.get("resposta").get("paginacio").get("total_items")
        except Exception as e:
            c.print(e, style="red")
            return []
        items = []
        pagines = total_items // items_pagina + 1
        for pag in range(1, pagines + 1):
            api_url = f"{self.BASE_API}/videos?version=2.0&items_pagina={items_pagina}&pagina={pag}&programatv_id={programatv_id}&ordre=data_emissio"
            try:
                api_response = self.session.get(api_url).json()
                items += api_response.get("resposta").get("items").get("item")
            except Exception as e:
                c.print(e, style="red")
        return items

    def get_pvideos_api(self, capitol_id):
        api_url = f"{self.DINAMICS_API}/pvideo/media.jsp?media=video&idint={capitol_id}"
        try:
            api_response = self.session.get(api_url).json()
        except Exception as e:
            c.print(e, style="red")
            return None
        try:
            mp4_links = api_response.get("media").get("url")
        except Exception:
            mp4_links = api_response.get("variants")[0].get("media").get("url")
            c.print("video variants detected", style="yellow")
        try:
            max_resolution = str(max([int(link["label"][:-1]) for link in mp4_links])) + "p"
            url_mp4 = [link["file"] for link in mp4_links if max_resolution in link["label"]][0]
        except Exception:
            url_mp4 = None
        if url_mp4:
            c.print(f"video url disclossed with {max_resolution}", style="cyan")
            c.print(url_mp4, style="bold")
        return url_mp4

    def cerca(self, text):
        api_url = f"{self.BASE_API}/cercador/tot?text={text}&tipologia=PTVC_PROGRAMA"
        try:
            api_response = self.session.get(api_url).json()
            programes = api_response.get("resposta").get("items").get("item")
            table = Table()
            table.add_column("Select", style="cyan", no_wrap=True)
            table.add_column("Títol programa", style="bold")
            table.add_column("id", style="cyan")
            for i, p in enumerate(programes):
                table.add_row(str(i), p.get("titol"), str(p.get("id")))
            c.print(table)
            return programes
        except Exception as e:
            c.print(str(e), style="red")
            return []


def download_mp4(programatv_id, video):
    save_dir = Path(f"data/{programatv_id}/videos")
    try:
        save_dir.mkdir()
    except FileExistsError:
        pass
    file_name = f"{normalize('NFKD', video['programa'])}_{video['titol']}.mp4".replace(" ", "_")
    file_name = Path(file_name)
    if (save_dir / file_name).exists():
        c.print(f"{file_name} already exists", style="green")
    else:
        c.print(f"Downloading {file_name}", style="magenta")
        try:
            wget.download(video["url_mp4"], str(save_dir / file_name))
            c.print()
            c.print(f"{file_name} successfully downloaded", style="green")
        except (urllib.error.ContentTooShortError, FileNotFoundError) as e:
            c.print()
            c.print(f"{e}", style="red")
            download_mp4(programatv_id, video)
        except Exception as e:
            c.print()
            c.print(f"Error downloading: {e}", style="red")


def save_json_data(programatv_id, data):
    save_dir = Path(f"data/{programatv_id}")
    try:
        save_dir.mkdir()
    except FileExistsError:
        pass
    with open(f"data/{programatv_id}/info_{programatv_id}.json", "w") as json_file:
        json.dump(data, json_file, indent=2)


def read_json_data(programatv_id):
    try:
        with open(f"data/{programatv_id}/info_{programatv_id}.json") as json_file:
            data = json.load(json_file)
        return data
    except FileNotFoundError:
        c.print(f"'data/{programatv_id}/info_{programatv_id}.json' file not found", style="yellow")
        return []


def main():
    try:
        Path("data").mkdir()
    except FileExistsError:
        pass
    client = ClientCCMA()

    ###################################
    # Cerca el programa a descarregar #
    ###################################
    text = str(input("Cercar programa: "))
    programes = client.cerca(text)
    if len(programes) == 0:
        c.print("No s'ha trobat cap programa amb aquest nom", style="red")
        exit()
    elif len(programes) == 1:
        p_id = 0
    else:
        try:
            p_id = int(input(f"Seleccioneu id: (0-{len(programes)-1}) "))
        except ValueError:
            c.print("No s'ha trobat cap programa amb aquest id", style="bold red")
            exit()
        except KeyboardInterrupt:
            exit()
    try:
        programatv_id = programes[p_id]["id"]
    except Exception:
        c.print("No s'ha trobat cap programa amb aquest id", style="bold red")
        exit()

    ##########
    # Step 1 #
    ##########
    # Get info about the show and video list
    saved_data = read_json_data(programatv_id)
    if saved_data:
        c.print("using saved data", style="cyan")
        videos = saved_data
        c.print(f"{len(videos)} videos available", style="cyan")
    else:
        c.print("getting video info from CCMA API...", style="cyan")
        videos = client.get_videos_api(programatv_id)
        save_json_data(programatv_id, videos)
        c.print(f"{len(videos)} videos saved", style="green")

    ##########
    # Step 2 #
    ##########
    # Obtain the private video urls
    for video in videos:
        url_mp4 = None
        try:
            url_mp4 = video["url_mp4"]
            c.print(f"video {video['capitol']} url_mp4 ok", style="green")
            continue
        except KeyError:
            url_mp4 = client.get_pvideos_api(video["id"])
        if url_mp4:
            video["url_mp4"] = url_mp4
            c.print(f"video {video['capitol']} url_mp4 ok", style="green")
            save_json_data(programatv_id, videos)
            c.print("data updated", style="cyan")
        else:
            c.print(f"error with url_mp4 video {video['video']}", style="red")

    ##########
    # Step 3 #
    ##########
    # Download mp4 videos using wget
    for video in videos:
        try:
            if video["url_mp4"]:
                download_mp4(programatv_id, video)
        except KeyError:
            pass


if __name__ == "__main__":
    main()
