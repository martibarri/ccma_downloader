# plats-bruts-scrap

Dirty script to download "Plats Bruts" videos

Steps:

1- Get public urls for each episode using `requests`, and save all data to a local file.

2- Obtain the hidden mp4 url of each episode using `selenium`.

3- Download mp4 videos with `wget`.
