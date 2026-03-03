import requests

num = 6

for num in range(6, 318):
    image_url = f'https://assets.leaguestat.com/pwhl/240x240/{num}.jpg'
    file_path = f'C:\\Users\\msaun\\PWHLByTheNumbers\\assets\\players\\Official\\{num}.jpg'

    response = requests.get(image_url)

    if response.status_code == 200:
        with open(file_path, 'wb') as file:
            file.write(response.content)
        print(f"Image successfully downloaded to {file_path}")
    else:
        print(f"Failed to download image. Status code: {response.status_code}")
