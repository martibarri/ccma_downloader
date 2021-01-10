import json
import re
import requests
import wget

from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.expected_conditions import presence_of_element_located
from huepy import info, run, bad, good, warn, bold


BASE_URL = "https://www.ccma.cat"
BASE_API = "https://api.ccma.cat"
DINAMICS_API = "https://dinamics.ccma.cat"


def plats_bruts(href):
    return href and re.compile("tv3/alacarta/plats-bruts").search(href)


def get_html(page=None):
    capitols_url = "/tv3/plats-bruts/capitols/"
    url = BASE_URL + capitols_url + f"?pagina={page}"
    response = requests.get(url)
    raw_html = response.text
    return raw_html


def get_capitol_links():
    print(info("get capitol links from CCMA website"))
    capitol_links = set()
    for p in range(1, 6):
        raw_html = get_html(p)
        soup = BeautifulSoup(raw_html, "html.parser")
        raw_links = soup.find_all(href=plats_bruts)
        for link in raw_links:
            capitol_links.add(BASE_URL + link["href"])
    return list(capitol_links)


def get_capitols_api():
    api_url = f"{BASE_API}/videos?version=2.0&items_pagina=80&programatv_id=126706100&ordre=data_emissio"
    api_response = requests.get(api_url)
    capitols_json = api_response.json()
    try:
        capitols = capitols_json["resposta"]["items"]["item"]
    except KeyError as e:
        raise e
    for capitol in capitols:
        c_id = capitol["id"]
        nom_friendly = capitol["nom_friendly"]
        capitol["url"] = f"{BASE_URL}/tv3/alacarta/plats-bruts/{nom_friendly}/video/{c_id}/"
    return capitols


def get_mp4_link_api(capitol_id):
    api_url = f"{DINAMICS_API}/pvideo/media.jsp?media=video&idint={capitol_id}"
    api_response = requests.get(api_url)
    json = api_response.json()
    try:
        mp4_links = json["variants"]["media"]["url"]
    except KeyError:
        mp4_links = json["media"]["url"]
    try:
        max_resolution = str(max([int(link["label"][:-1]) for link in mp4_links])) + "p"
        url_mp4 = [link["file"] for link in mp4_links if max_resolution in link["label"]][0]
    except Exception:
        url_mp4 = None
    if url_mp4:
        print(info(f"video url disclossed with {max_resolution}"))
        print(bold(url_mp4))
    return url_mp4


def selenium_parse(url):
    driver = webdriver.Chrome()

    driver.get(url)

    # Cookies: more info
    try:
        element_present = presence_of_element_located((By.ID, "didomi-notice-learn-more-button"))
        WebDriverWait(driver, 10).until(element_present)
    except TimeoutException:
        print("Timed out waiting for page to load")
        driver.quit()
        return
    else:
        driver.find_element_by_id("didomi-notice-learn-more-button").click()
        print("Configuring cookies...")

    # opt-out
    elements = driver.find_elements_by_xpath("//button/span")
    disagree_elements = []
    for e in elements:
        if e.text.strip() == "DISAGREE":
            disagree_elements.append(e)
    while disagree_elements:
        e = disagree_elements[0]
        try:
            e.click()
        except Exception:
            driver.execute_script("document.getElementsByClassName('didomi-popup-body')[0].scrollTo(0, document.getElementsByClassName('didomi-popup-body')[0].scrollHeight)")
        else:
            disagree_elements.remove(e)
        print(e.text.strip())

    # Save preferences
    driver.find_element_by_class_name("didomi-consent-popup-actions").click()

    # click to load video
    try:
        element_present = presence_of_element_located((By.CLASS_NAME, "M-rmp"))
        WebDriverWait(driver, 10).until(element_present)
    except TimeoutException:
        print("Timed out waiting for page to load")
        driver.quit()
        return
    else:
        driver.find_element_by_class_name("M-rmp").click()
        print("loading video...")

    # wait for video to load
    try:
        element_present = presence_of_element_located((By.CSS_SELECTOR, "video[src]"))
        WebDriverWait(driver, 30).until(element_present)
    except TimeoutException:
        print("Timed out waiting for page to load")
        driver.quit()
        return

    # get url
    url_mp4 = driver.find_element_by_tag_name("video").get_attribute("src")
    while not url_mp4:
        # wait for finishing hardcoded ads
        WebDriverWait(driver, 10)
        url_mp4 = driver.find_element_by_tag_name("video").get_attribute("src")
    if url_mp4:
        print(info("video url disclossed!"))
        print(bold(url_mp4))

    driver.quit()
    return url_mp4


def download_mp4(capitol):
    # Create save directory
    save_dir = Path("capitols")
    try:
        save_dir.mkdir()
    except FileExistsError:
        pass
    file_name = Path(f"{capitol['nom_friendly']}.mp4")
    if (save_dir / file_name).exists():
        print(good(f"{file_name} already exists"))
    else:
        print(run(f"Downloading {file_name}"))
        wget.download(capitol["url_mp4"], str(save_dir / file_name))
        print()
        print(good(f"{file_name} correctly downloaded"))


def save_json_data(data):
    with open('capitols.json', 'w') as json_file:
        json.dump(data, json_file, indent=2)
    json_file.close()


def read_json_data():
    try:
        with open('capitols.json', 'r') as json_file:
            data = json.load(json_file)
        json_file.close()
        return data
    except FileNotFoundError:
        print(warn("'capitols.json' file not found"))
        return []


def main():
    ##########
    # Step 1 #
    ##########
    # Get public urls for each episode using requests, and save all data to a local file.
    # capitol_links = get_capitol_links()  # old method
    saved_data = read_json_data()
    if len(saved_data) == 73:
        print(info("using saved data"))
        capitols = saved_data
        print(info(f"{len(capitols)} 'capitols' available"))
    else:
        print(info("getting 'capitols' from CCMA API..."))
        capitols = get_capitols_api()
        save_json_data(capitols)
        print(good(f"{len(capitols)} 'capitols' saved"))

    ##########
    # Step 2 #
    ##########
    # Obtain the hidden mp4 url of each episode.
    for capitol in capitols:
        url_mp4 = None
        try:
            if not capitol["url_mp4"]:
                # url_mp4 = selenium_parse(capitol["url"])  # old method using selenium
                url_mp4 = get_mp4_link_api(capitol["id"])
            else:
                print(good(f"capitol {capitol['capitol']} url_mp4 ok"))
                continue
        except KeyError:
            # url_mp4 = selenium_parse(capitol["url"])  # old method using selenium
            url_mp4 = get_mp4_link_api(capitol["id"])
        if url_mp4:
            capitol["url_mp4"] = url_mp4
            print(good(f"capitol {capitol['capitol']} url_mp4 ok"))
            save_json_data(capitols)
            print(info("data updated"))
        else:
            print(bad(f"error with url_mp4 capitol {capitol['capitol']}"))

    ##########
    # Step 3 #
    ##########
    # Download mp4 videos with wget
    for capitol in capitols:
        try:
            if capitol["url_mp4"]:
                download_mp4(capitol)
        except KeyError:
            pass


if __name__ == "__main__":
    main()
