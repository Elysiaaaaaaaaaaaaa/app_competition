import requests
import time
import json
from screenwriter import Script

# Make your first video generation request
def generate_video():
    url = 'https://www.sora2api.org/api/generate-video'
    headers = {
        'Authorization': 'Bearer YOUR_API_KEY',
        'Content-Type': 'application/json'
    }
    payload = {
        'prompt': 'A beautiful sunset over the ocean with gentle waves',
        'aspectRatio': '16:9',
        'duration': 10,
        'type': 'text2video'
    }

    response = requests.post(url, headers=headers, json=payload)
    result = response.json()

    print(f"Task ID: {result['data']['taskId']}")
    print(f"Credits used: {result['data']['creditsUsed']}")

    return result['data']['taskId']  # Save this for status checking





def generate_and_wait_for_video(story):
    base_url = 'https://www.sora2api.org/api'
    headers = {
        'Authorization': r'sk-onODJdUvQtLtKrQHs6RMRwus05FqUOJx',
        'Content-Type': 'application/json'
    }
    prompt = story.outline[0]+'\n'+story.all_stuff+'\n'+story.script[0]
    # Step 1: Start video generation
    generate_payload = {
        'prompt': prompt,
        'aspectRatio': '16:9',
        'duration': 10,
        'type': 'text2video'
    }

    response = requests.post(
        f'{base_url}/generate-video',
        headers=headers,
        json=generate_payload
    )
    result = response.json()
    task_id = result['data']['taskId']
    print(f'Video generation started, Task ID: {task_id}')

    # Step 2: Poll for completion
    while True:
        status_response = requests.post(
            f'{base_url}/check-video-status',
            headers=headers,
            json={'taskId': task_id}
        )
        status_result = status_response.json()

        status = status_result['data']['status']
        progress = status_result['data'].get('progress', 0)
        print(f'Status: {status}, Progress: {progress}%')

        if status == 'succeeded':
            video_url = status_result['data']['videoUrl']
            print(f'Video ready! URL: {video_url}')
            return video_url
        elif status == 'failed':
            raise Exception('Video generation failed')

        # Still processing, wait 5 seconds before checking again
        time.sleep(5)


# Usage
try:
    story = Script("隐居森林研究魔法与数学的精灵偶遇了前来避雨的勇者小队")
    video_url = generate_and_wait_for_video(story)
    print(f'Final video URL: {video_url}')
except Exception as e:
    print(f'Error: {e}')