from moviepy import VideoFileClip, concatenate_videoclips
import os

def merge_videos(video_paths, output_path):
    """
    将多个本地 MP4 文件拼接成一个视频并保存到指定地址。

    参数:
        video_paths (list[str]): 本地视频文件路径列表，顺序即为拼接顺序。
        output_path (str): 拼接后视频的保存路径（需包含文件名，如 merged.mp4）。

    返回:
        str: 保存后的视频文件路径。
    """
    if not video_paths:
        raise ValueError("视频路径列表不能为空")

    clips = []
    for path in video_paths:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"视频文件不存在: {path}")
        clip = VideoFileClip(path)
        clips.append(clip)

    final_clip = concatenate_videoclips(clips, method="compose")
    final_clip.write_videofile(output_path, codec="libx264", audio_codec="aac")

    # 释放资源
    for clip in clips:
        clip.close()
    final_clip.close()

    return output_path

if __name__ == "__main__":
    video_paths = [
        "./test/video/monalisa_1.mp4",
        "./test/video/witch_1.mp4",
    ]
    output_path = "./test/video/merged_test.mp4"
    merge_videos(video_paths, output_path)
