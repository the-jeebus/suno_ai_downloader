import os
import re
import json
import requests
import argparse
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, USLT, COMM, TXXX, TBPM
import librosa
import platform

def extract_script_content(html):
    pattern = r'<script>\s*self\.__next_f\.push\(\[.*?,"(.*?)"\]\s*\)</script>'
    matches = re.findall(pattern, html, re.DOTALL)
    unified_content = ''.join(matches).replace(r'\"', '"').replace(r'\\n', '\n').replace(r'\\t', '\t')
    # Decode all UTF-8 encoded sequences
    unified_content = unified_content.encode().decode('unicode_escape')
    return unified_content

def extract_json(unified_content):
    # Extract the main JSON block
    main_pattern = r'{"clip":{.*?}}'
    main_match = re.search(main_pattern, unified_content, re.DOTALL)
    if main_match:
        json_str = main_match.group(0)
        
        try:
            json_data = json.loads(json_str)
        except json.JSONDecodeError:
            # Attempt to clean the JSON string and retry
            json_str_cleaned = re.sub(r'[\x00-\x1f\x7f]', '', json_str)
            try:
                json_data = json.loads(json_str_cleaned)
            except json.JSONDecodeError as e:
                print(f"Failed to parse JSON after cleaning: {e}")
                return None
    else:
        json_data = None

    # Extract the additional JSON-like structures
    additional_pattern = r'\d+:\[\["\$".*?\]\]|\d+:[null,.*?]'
    matches = re.findall(additional_pattern, unified_content, re.DOTALL)

    additional_data = {}
    for match in matches:
        try:
            key, value = match.split(":", 1)
            value = json.loads(value)
            
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, list) and len(item) == 4:
                        inner_key = item[3].get("name") or item[3].get("property")
                        if inner_key:
                            additional_data[inner_key] = item[3].get("content", '').strip()
                        elif item[2] == "children":
                            additional_data["children"] = item[3].get("children", '').strip()
            elif isinstance(value, dict):
                additional_data.update(value)

        except (json.JSONDecodeError, ValueError):
            continue  # Skip any lines that can't be converted to JSON

    if json_data:
        # Check if 'prompt' is $16, replace it with 'lyrics' value if it exists
        prompt = json_data['clip']['metadata'].get('prompt', '').strip()
        lyrics = extract_lyrics(unified_content)  # Extract the lyrics from the unified content
        if prompt == '$16' and lyrics:
            json_data['clip']['metadata']['prompt'] = lyrics.strip()

        # Strip spaces from all string values in json_data
        def strip_spaces(obj):
            if isinstance(obj, dict):
                return {k: strip_spaces(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [strip_spaces(elem) for elem in obj]
            elif isinstance(obj, str):
                return obj.strip()
            else:
                return obj

        # Apply space stripping to json_data and additional_data
        json_data = strip_spaces(json_data)
        additional_data = strip_spaces(additional_data)

        # Add the additional data at the end of the 'clip' object
        json_data['clip'].update(additional_data)

    return json_data

def extract_lyrics(unified_content):
    # Adjust the pattern to capture any text, including special characters, between '16:T' and '6:["$'
    lyrics_pattern = r'16:T[0-9a-f]+,(.*?)6:\["\$"'
    
    # Use re.DOTALL to make sure that the pattern matches across multiple lines
    match = re.search(lyrics_pattern, unified_content, re.DOTALL)
    
    if match:
        lyrics = match.group(1).strip()  # Use .strip() to clean up any leading/trailing whitespace
        return lyrics.replace(r'\\n', '\n').replace(r'\n', '\n')  # Properly format newlines
    return None

def download_file(url, filename):
    response = requests.get(url, timeout=30)
    with open(filename, 'wb') as file:
        file.write(response.content)

def tag_mp3_file(mp3_filename, clip, image_filename, bpm, url):
    audio = EasyID3(mp3_filename)
    audio['title'] = clip['title']
    audio['artist'] = clip['display_name']
    audio['album'] = 'Suno AI Music'
    audio['date'] = clip['created_at'].split('T')[0]
    audio['genre'] = 'SunoAI'
    audio['catalognumber'] = clip['id']
    audio['mood'] = clip['metadata']['tags']
    audio.save()

    audio = ID3(mp3_filename)
    prompt = clip['metadata'].get('prompt', '')

    audio['USLT'] = USLT(encoding=3, lang='eng', desc='', text=prompt.replace('\\n', '\n'))
    formatted_bpm = f"{bpm:.3f}"  # Ensure the BPM is formatted to three decimal places
    audio['TXXX:BPM Precise'] = TXXX(encoding=3, desc='BPM Precise', text=formatted_bpm)
    
    # Add a comment with Suno URL, Style, and BPM
    comment_text = f"Suno URL: {url}\nStyle: {clip['metadata'].get('tags', 'N/A')}\nBPM: {clip['metadata'].get('estimated_bpm', 'N/A')}"
    audio['COMM'] = COMM(encoding=3, lang='eng', desc='', text=comment_text)

    if 'tags' in clip['metadata']:
        audio['COMM::tags'] = COMM(encoding=3, lang='eng', desc='tags', text=clip['metadata']['tags'])
    if image_filename:
        with open(image_filename, 'rb') as img_file:
            audio['APIC'] = APIC(
                encoding=3, 
                mime='image/jpeg', 
                type=3, 
                desc='Cover',
                data=img_file.read()
            )
    audio.save()

def estimate_bpm(mp3_filename):
    y, sr = librosa.load(mp3_filename)
    tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
    return float(tempo) if tempo.ndim == 0 else float(tempo[0])  # Ensure the tempo is a float

def clean_filename(filename):
    # Define illegal characters based on OS
    illegal_chars = {
        'Windows': r'[<>:"/\\|?*]',
        'Linux': r'[\\/\x00]',
        'Darwin': r'[\\/:]',
    }

    os_type = platform.system()  # Get the current OS type
    pattern = illegal_chars.get(os_type, r'[<>:"/\\|?*]')  # Default to Windows pattern

    # Clean the filename by replacing illegal characters with an underscore
    return re.sub(pattern, '_', filename)

def main():
    print(f"{'='*50}\n{' '*15}Suno AI Media Downloader\n{'='*50}\n")
    parser = argparse.ArgumentParser(description="Download media from Suno AI.")
    parser.add_argument("-u", "--url", help="Suno Song URL(s), comma-separated")
    parser.add_argument("-s", "--suno_id", help="Suno Song ID(s), comma-separated")
    parser.add_argument("-a", "--audio", action="store_true", help="Download audio and cover image")
    parser.add_argument("-v", "--video", action="store_true", help="Download video only")
    parser.add_argument("-i", "--image", action="store_true", help="Download image only")
    parser.add_argument("-d", "--data", action="store_true", help="Print JSON data")
    parser.add_argument("-l", "--list", help="Path to a file containing a list of Suno Song URLs")
    parser.add_argument("-f", "--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("-cd", "--change_directory", default="downloads", help="Directory to save downloads, default is 'downloads'")
    parser.add_argument("-sr", "--save_response", action="store_true", help="Save raw response to file")

    args = parser.parse_args()

    # Use the specified directory or default to 'downloads'
    download_dir = args.change_directory

    if not os.path.exists(download_dir):
        os.makedirs(download_dir)

    urls = []
    if args.list:
        with open(args.list, 'r') as file:
            urls = [line.strip() for line in file.readlines()]
    elif args.url:
        urls.extend(args.url.split(','))
    elif args.suno_id:
        urls.extend([f"https://suno.com/song/{id.strip()}" for id in args.suno_id.split(',')])
    else:
        urls.append(input("Enter Suno Song URL: "))

    for url in urls:
        if not url.strip():
            print("That is not a valid url.")
            continue
        if "suno.com" not in url:
            print("That is not a Suno url.")
            continue

        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            script_content = extract_script_content(response.text)
            json_data = extract_json(script_content)
            if not json_data:
                print(f"Failed to extract JSON data from URL: {url}")
                continue

            clip = json_data['clip']

            # Set the directory for downloads based on clip display name
            final_download_dir = os.path.join(download_dir, clean_filename(clip['display_name']))
            if not os.path.exists(final_download_dir):
                os.makedirs(final_download_dir)

            # Ensure BPM is estimated before setting the filename
            audio_url = clip['audio_url']
            audio_filename_temp = os.path.join(final_download_dir, 'temp_audio.mp3')
            download_file(audio_url, audio_filename_temp)
            bpm = estimate_bpm(audio_filename_temp)
            os.remove(audio_filename_temp)

            # Add the estimated BPM to the metadata
            json_data['clip']['metadata']['estimated_bpm'] = f"{bpm:.3f} BPM"

            base_filename = clean_filename(f"{clip['display_name']} - {clip['title']} {{id-{clip['id']}}}")
            base_filename = re.sub(r'[<>:"/\\|?*]', '', base_filename.replace('\\n', '').replace('\n', ''))

            # Add the Suno song URL to the JSON data
            final_json_data = {"suno_song_url": url, "clip": clip}

            json_filename = os.path.join(final_download_dir, f"{base_filename}.json")
            if not os.path.exists(json_filename) or args.force:
                with open(json_filename, 'w', encoding='utf-8') as json_file:
                    json.dump(final_json_data, json_file, indent=4)
            else:
                print(f"Json Exists - Skipping id: {clip['id']}")

            if args.data:
                print(json.dumps(final_json_data, indent=4))

            # Save raw response if requested
            if args.save_response:
                response_filename = os.path.join(final_download_dir, f"{base_filename}-response.txt")
                with open(response_filename, 'w', encoding='utf-8') as response_file:
                    response_file.write(script_content)

            image_filename = None
            # Ensure image is downloaded when audio is selected
            if args.audio or args.image:
                image_url = clip['image_large_url']
                image_filename = os.path.join(final_download_dir, f"{base_filename}.jpeg")
                if not os.path.exists(image_filename) or args.force:
                    print(f"Downloading {image_url}...")
                    download_file(image_url, image_filename)
                    print(f"    Downloaded: {base_filename}.jpeg\n")
                else:
                    print(f"Image Exists - Skipping id: {clip['id']}")

            if args.audio or args.video:
                if args.audio:
                    audio_filename = os.path.join(final_download_dir, f"{base_filename}.mp3")
                    if not os.path.exists(audio_filename) or args.force:
                        print(f"Downloading {audio_url}...")
                        download_file(audio_url, audio_filename)
                        print(f"    Downloaded: {base_filename}.mp3")
                        print(f"    Detecting BPM for {base_filename}.mp3")
                        print(f"        Estimated BPM: {bpm:.3f}")
                        print(f"    Writing ID3 Tags on: {base_filename}.mp3")
                        tag_mp3_file(audio_filename, clip, image_filename, bpm, url)
                    else:
                        print(f"Audio Exists - Skipping id: {clip['id']}")

                if args.video:
                    video_url = clip['video_url']
                    video_filename = os.path.join(final_download_dir, f"{base_filename}.mp4")
                    if not os.path.exists(video_filename) or args.force:
                        print(f"Downloading {video_url}...")
                        download_file(video_url, video_filename)
                        print(f"    Downloaded: {base_filename}.mp4\n")
                    else:
                        print(f"Video Exists - Skipping id: {clip['id']}")
            else:  # Default behavior without specific args
                image_url = clip['image_large_url']
                image_filename = os.path.join(final_download_dir, f"{base_filename}.jpeg")
                if not os.path.exists(image_filename) or args.force:
                    print(f"Downloading {image_url}...")
                    download_file(image_url, image_filename)
                    print(f"    Downloaded: {base_filename}.jpeg\n")
                else:
                    print(f"Image Exists - Skipping id: {clip['id']}")

                audio_filename = os.path.join(final_download_dir, f"{base_filename}.mp3")
                if not os.path.exists(audio_filename) or args.force:
                    print(f"Downloading {audio_url}...")
                    download_file(audio_url, audio_filename)
                    print(f"    Downloaded: {base_filename}.mp3")
                    print(f"    Detecting BPM for {base_filename}.mp3")
                    print(f"        Estimated BPM: {bpm:.3f}")
                    print(f"    Writing ID3 Tags on: {base_filename}.mp3")
                    tag_mp3_file(audio_filename, clip, image_filename, bpm, url)
                else:
                    print(f"Audio Exists - Skipping id: {clip['id']}")

                video_url = clip['video_url']
                video_filename = os.path.join(final_download_dir, f"{base_filename}.mp4")
                if not os.path.exists(video_filename) or args.force:
                    print(f"Downloading {video_url}...")
                    download_file(video_url, video_filename)
                    print(f"    Downloaded: {base_filename}.mp4\n")
                else:
                    print(f"Video Exists - Skipping id: {clip['id']}")
        else:
            print(f"Failed to fetch the URL: {response.status_code}")

if __name__ == "__main__":
    main()
