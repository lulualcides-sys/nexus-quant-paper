"""Audit only actual publicly embedded YouTube clips from Greenhouse offer.

No login, no cookies, no private lessons, no bypass. Probe public embeds,
sample nine frames where accessible, return factual metadata. Do not
redistribute copyrighted media; downloaded bytes are deleted at end.
"""
import base64
import json
import subprocess
import tempfile
from pathlib import Path

IDS=["g5Jo41A03yE","NiWQ5otSEIM","PH_j7Q0xu0U","WacleOhwv7Y","zqI2EgUgUzc"]

def run(args,timeout=150):
    p=subprocess.run(args,text=True,capture_output=True,timeout=timeout)
    return p

def audit_one(id,folder):
    url="https://www.youtube.com/watch?v="+id
    result={"id":id,"public_embed_url":url}
    meta=run(["yt-dlp","--no-playlist","--no-warnings","--skip-download",
              "--dump-single-json","--socket-timeout","15",url],timeout=75)
    if meta.returncode:
        result["error"]="metadata unavailable: "+meta.stderr[-350:]
        return result
    try:
        info=json.loads(meta.stdout)
    except Exception:
        result["error"]="invalid metadata from extractor"
        return result
    result.update({"title":info.get("title"),"duration":info.get("duration"),
                   "channel":info.get("channel"),"upload_date":info.get("upload_date"),
                   "availability":info.get("availability")})
    duration=info.get("duration") or 0
    if duration<=1 or duration>1000:
        result["note"]="not sampled: duration not usable or over 16m40s"
        return result
    filename=folder/(id+".mp4")
    # 360p is sufficient for navigation/shape and reduces resource use.
    download=run(["yt-dlp","--no-playlist","--no-warnings","--socket-timeout","15",
                  "--max-filesize","50M","-f",
                  "best[height<=360][ext=mp4]/best[height<=360]/best[ext=mp4]",
                  "-o",str(filename),url],timeout=160)
    if download.returncode or not filename.is_file():
        result["note"]="metadata only; media download failed: "+download.stderr[-300:]
        return result
    frames=[]
    for i in range(9):
        ts=round((i+.5)*float(duration)/9,2)
        frame=folder/f"{id}_{i}.jpg"
        p=run(["ffmpeg","-hide_banner","-loglevel","error","-ss",str(ts),
               "-i",str(filename),"-frames:v","1",
               "-vf","scale=320:180:force_original_aspect_ratio=decrease,"
                     "pad=320:180:(ow-iw)/2:(oh-ih)/2",
               "-q:v","5","-y",str(frame)],timeout=45)
        if p.returncode or not frame.is_file():
            result["note"]="frame extraction incomplete";return result
        frames.append(frame)
    mosaic=folder/f"{id}_mosaic.jpg"
    argv=["ffmpeg","-hide_banner","-loglevel","error"]
    for frame in frames:argv+=["-i",str(frame)]
    argv+=["-filter_complex",
           "".join(f"[{k}:v]format=yuv420p[{k}];" for k in range(9))+
           "".join(f"[{k}]" for k in range(9))+
           "xstack=inputs=9:layout=0_0|320_0|640_0|0_180|320_180|640_180|0_360|320_360|640_360[out]",
           "-map","[out]","-frames:v","1","-q:v","5","-y",str(mosaic)]
    p=run(argv,timeout=40)
    if p.returncode or not mosaic.is_file():
        result["note"]="mosaic failed";return result
    timestamps=[round((i+.5)*float(duration)/9,2) for i in range(9)]
    result["sampled_frame_seconds"]=timestamps
    print("YOUTUBE_MOSAIC_START",id,"times",",".join(map(str,timestamps)),flush=True)
    print(base64.b64encode(mosaic.read_bytes()).decode(),flush=True)
    print("YOUTUBE_MOSAIC_END",id,flush=True)
    result["sampled_frames"]=9
    return result

def main():
    records=[]
    with tempfile.TemporaryDirectory(prefix="tracker_public_youtube_") as folder:
        folder=Path(folder)
        for id in IDS:
            try:
                res=audit_one(id,folder)
            except Exception as exc:
                res={"id":id,"public_embed_url":"https://www.youtube.com/watch?v="+id,
                     "error":type(exc).__name__+":"+str(exc)[:200]}
            records.append(res)
            print("YT_PUBLIC_STATUS",json.dumps(res,ensure_ascii=False),flush=True)
    folder=Path("research/results");folder.mkdir(parents=True,exist_ok=True)
    (folder/"tracker_public_youtube_audit.json").write_text(
        json.dumps(records,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")

if __name__=="__main__":main()
