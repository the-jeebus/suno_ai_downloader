
# Suno AI Media Downloader

This script is designed to download media from Suno AI, specifically audio, images, and video. The script can extract metadata from the media, estimate the BPM (beats per minute) of the audio file, and tag the downloaded MP3 file with the relevant information.

## Required Packages

To run the script, you need to install the following Python packages. You can install them using `pip`:

```bash
pip install requests mutagen librosa argparse
```

## Features

- **Download Audio, Images, Videos, and Data**: The script can download data, audio, images, and videos from the specified Suno AI URLs.
- **Estimate BPM**: The script uses the `librosa` library to estimate the BPM of the downloaded audio file.
- **ID3 Tagging**: The script uses `mutagen` to tag the downloaded MP3 files with the title, artist, album, and other relevant metadata.
- **Directory Structure**: By default, the script saves the downloaded files in a `downloads` directory. You can specify a different directory using the `-cd` argument.
- **Automatic Filename and Directory Cleaning**: The script automatically removes illegal characters from filenames and directory names to ensure compatibility across different operating systems (Windows, Mac, Linux).

## Usage

### Command-Line Arguments

- `-u, --url`: Suno Song URL(s), comma-separated. If not provided, the script will prompt you to paste the URL.
- `-s, --suno_id`: Suno Song ID(s), comma-separated.
- `-a, --audio`: Download audio and cover image.
- `-v, --video`: Download video only.
- `-i, --image`: Download image only.
- `-d, --data`: Print JSON data.
- `-l, --list`: Path to a file containing a list of Suno Song URLs.
- `-f, --force`: Overwrite existing files.
- `-cd, --change_directory`: Directory to save downloads, default is `downloads`.
- `-sr, --save_response`: Save raw response to a file.

### Examples

1. **Download a single Suno AI song:**

    ```bash
    python get_suno.py -u https://suno.com/song/example-id
    ```	

2. **Download multiple Suno AI songs using a comma-separated list of URLs:**

    ```bash
    python get_suno.py -u "https://suno.com/song/example-id1,https://suno.com/song/example-id2"
    ```

3. **Download audio and cover image only:**

    ```bash
    python get_suno.py -a -u "https://suno.com/song/example-id"
    ```

4. **Download all content (audio, image, video) for a list of Suno AI song URLs from a file:**

    ```bash
    python get_suno.py -l urls.txt
    ```

5. **Save the downloaded files to a specific directory:**

    ```bash
    python get_suno.py -cd "my custom_directory" -u "https://suno.com/song/example-id"
    ```

### Default Behavior

If no arguments are provided, the script will prompt you to paste the Suno AI song URL.

## Notes

- The script will automatically create a directory based on the artist's name to save the downloaded content.
- Illegal characters in filenames and directories will be automatically replaced with underscores to ensure compatibility across operating systems.
