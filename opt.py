import os
import argparse
import shutil
import requests
from PIL import Image
from io import BytesIO
from bs4 import BeautifulSoup
import re
from urllib.parse import unquote

def download_and_optimize_image(url, output_dir) -> (str | dict):
    response = requests.get(url)

    # Get filename from Content-Disposition header if available
    content_disposition = response.headers.get('content-disposition')
    if content_disposition:
        fname = re.findall('filename=(.+)', content_disposition)
        if len(fname) == 0:
            # If no match, use the basename of the url
            filename = os.path.basename(url)
        else:
            # If there's a match, decode the quoted string
            filename = unquote(fname[0])
    else:
        # If no Content-Disposition header, use the basename of the url
        filename = os.path.basename(url)

    # only run on jpeg and png files
    ENDINGS=('.jpg', '.jpeg', '.png')
    if filename.lower().endswith(ENDINGS):
        img = Image.open(BytesIO(response.content))
        if img.size[0] > 1600 or img.size[1] > 1600:
            img.thumbnail((1600, 1600))

        optimized_img_path = os.path.join(output_dir, filename)
        os.makedirs(os.path.dirname(optimized_img_path), exist_ok=True)
        img.save(optimized_img_path, optimize=True, quality=85)
        return optimized_img_path

    # If it's a gif, use ffmpeg to convert it to a video
    elif filename.lower().endswith('.gif'):
        video_path = os.path.join(output_dir, filename.replace('.gif', '.mp4'))
        os.makedirs(os.path.dirname(video_path), exist_ok=True)
        os.system(f'ffmpeg -i {url} -vf "scale=trunc(iw/2)*2:trunc(ih/2)*2" -an -c:v libx264 -pix_fmt yuv420p {video_path}')
        return {
            'type': 'video',
            'path': video_path
        }

    img_path = os.path.join(output_dir, filename)
    os.makedirs(os.path.dirname(img_path), exist_ok=True)
    with open(img_path, 'wb') as file:
        file.write(response.content)
    return img_path

def process_html_file(html_file, output_path):
    with open(html_file, 'r') as file:
        data = file.read()
    soup = BeautifulSoup(data, 'html.parser')
    img_relative_path = os.path.join(os.path.dirname(output_path), 'img')
    for img in soup.find_all('img'):
        try:
            url = img['src']
            optimized_img_path = download_and_optimize_image(url, img_relative_path)
            if isinstance(optimized_img_path, dict):
               # This is a video, so replace the img tag with a div tag that contains a video tag (make it loop, autoplay, and muted)
                rel_path = os.path.relpath(optimized_img_path['path'], os.path.dirname(output_path)).replace('\\', '/')
                video_tag = soup.new_tag('video', src=rel_path, loop='', autoplay='', muted='')

                div_tag = soup.new_tag('div')
                if img.has_attr('class') and 'image-zoomable' in img['class']:
                    div_tag['class'] = 'image-zoomable'

                # Take all attributes from the previous tag, except src
                for attr in img.attrs:
                    if attr != 'src':
                        video_tag[attr] = img[attr]

                div_tag.append(video_tag)

                img.replace_with(div_tag)
            else:
                img['src'] = os.path.relpath(optimized_img_path, os.path.dirname(output_path)).replace('\\', '/')
        except Exception as e:
            print(f"Failed to optimize image {url}: {e}")
    with open(output_path, 'w') as file:
        file.write(str(soup))

def main(input_dir, output_dir):
    shutil.rmtree(output_dir, ignore_errors=True)

    for root, dirs, files in os.walk(input_dir):
        # Ignore dot directories
        dirs[:] = [d for d in dirs if not d[0] == '.']

        for filename in files:
            # Ignore dot files
            if filename.startswith('.'):
                continue

            file_path = os.path.join(root, filename)
            rel_path = os.path.relpath(file_path, input_dir)
            new_path = os.path.join(output_dir, rel_path)

            os.makedirs(os.path.dirname(new_path), exist_ok=True)

            if filename.endswith('.html'):
                process_html_file(file_path, new_path)
            else:
                shutil.copy(file_path, new_path)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Optimize images in HTML.')
    parser.add_argument('-i', '--input_dir', required=True, help='Directory containing the input files.')
    parser.add_argument('-o', '--output_dir', required=True, help='Directory to save the optimized images and HTML.')
    args = parser.parse_args()
    main(args.input_dir, args.output_dir)

