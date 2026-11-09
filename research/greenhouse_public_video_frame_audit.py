"""Inspect only actual publicly linked Tracker promotional video files.

Read-only, no cookies, no credentials, no member API, no checkout. Reports
duration and samples frames; raw media and JPEG sheets remain temporary and
are not committed, published or redistributed. A small base64 JPEG contact
sheet is printed solely in the ephemeral GitHub Actions audit log so the
researching assistant can visually inspect observed frames.
"""
import base64
import json
import os
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path

PUBLIC_VIDEO_URLS={
    "pregao_13_10_full":"https://lojadagreenhouse.com.br/wp-content/uploads/2026/10/tracker-pregao-13-10.mp4",
    "pregao_13_10_preview":"https://lojadagreenhouse.com.br/wp-content/uploads/2026/10/tracker-pregao-13-10-previa.mp4",
    "open_lesson_1":"https://ferandrade.com.br/tracker/wp-content/uploads/2026/01/1.mp4",
    "open_lesson_2":"https://ferandrade.com.br/tracker/wp-content/uploads/2026/01/2.mp4",
    "open_lesson_3":"https://ferandrade.com.br/tracker/wp-content/uploads/2026/01/3.mp4",
    "open_method":"https://ferandrade.com.br/tracker/wp-content/uploads/2026/01/0121-1.mp4",
}
LIMIT_BYTES=75_000_000
ALLOWED={"lojadagreenhouse.com.br","ferandrade.com.br"}

def get_video(url,target):
    p=urllib.parse.urlparse(url)
    if p.scheme!="https" or p.hostname not in ALLOWED or not p.path.endswith(".mp4"):
        raise ValueError("Only explicitly observed public MP4 sources permitted")
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0 (public media research)"})
    with urllib.request.urlopen(req,timeout=45) as response:
        final=urllib.parse.urlparse(response.geturl())
        if final.hostname not in ALLOWED:
            raise ValueError("Unexpected cross-domain media redirect")
        length=response.headers.get("content-length")
        if length and int(length)>LIMIT_BYTES:
            raise ValueError(f"Video size {length} over 75MB audit cap")
        with open(target,"wb") as fp:
            total=0
            while True:
                chunk=response.read(1024*1024)
                if not chunk: break
                total+=len(chunk)
                if total>LIMIT_BYTES: raise ValueError("Video exceeds 75MB cap")
                fp.write(chunk)
        return total

def examine(key,url,folder):
    mp4=folder/(key+".mp4")
    size=get_video(url,mp4)
    probe=subprocess.run(["ffprobe","-v","error","-show_entries",
                          "format=duration,size:stream=codec_type,width,height",
                          "-of","json",str(mp4)],text=True,capture_output=True,
                         timeout=35,check=True)
    meta=json.loads(probe.stdout)
    duration=float(meta["format"]["duration"])
    if duration<=1 or duration>1800:
        raise ValueError("Unexpected duration")
    sheets=[]
    # 9 sample frames from first 92% of each video, timestamp before/after
    # displayed in log. For long videos, pick deterministic full-length coverage.
    for part in (0,1):
        start=0.02*duration + part*0.46*duration
        span=0.46*duration
        frames=[]
        for n in range(9):
            ts=min(duration-0.25,start+(n+.5)*span/9)
            frame=folder/f"{key}_{part}_{n}.jpg"
            command=["ffmpeg","-hide_banner","-loglevel","error",
                     "-ss",str(ts),"-i",str(mp4),"-frames:v","1",
                     "-vf","scale=480:270:force_original_aspect_ratio=decrease,"
                           "pad=480:270:(ow-iw)/2:(oh-ih)/2",
                     "-q:v","6","-y",str(frame)]
            subprocess.run(command,check=True,capture_output=True,timeout=30)
            frames.append(frame)
        # use FFmpeg itself for a 3x3 mosaic at 1440x810 (no PIL dep)
        layout=folder/f"{key}_{part}_sheet.jpg"
        argv=["ffmpeg","-hide_banner","-loglevel","error"]
        for p in frames:
            argv+=["-i",str(p)]
        argv+=["-filter_complex",
               "".join(f"[{k}:v]format=yuv420p[{k}];" for k in range(9))+
               "".join(f"[{k}]" for k in range(9))+
               "xstack=inputs=9:layout=0_0|480_0|960_0|0_270|480_270|960_270|0_540|480_540|960_540[out]",
               "-map","[out]","-frames:v","1","-q:v","6","-y",str(layout)]
        subprocess.run(argv,check=True,capture_output=True,timeout=45)
        dates=[round(min(duration-0.25,start+(n+.5)*span/9),1) for n in range(9)]
        # output is for transient forensic analysis, not a distributed artifact
        sheets.append({"part":part,"timestamp_seconds":dates,"jpeg_bytes":layout.stat().st_size})
        print(f"VIDEO_SHEET_START {key} part={part} seconds="+",".join(map(str,dates)),flush=True)
        print(base64.b64encode(layout.read_bytes()).decode("ascii"),flush=True)
        print(f"VIDEO_SHEET_END {key} part={part}",flush=True)
    return {"title":key,"public_url":url,"bytes":size,"duration_seconds":duration,
            "video_streams":[s for s in meta["streams"] if s["codec_type"]=="video"],
            "contact_sheets":sheets}

def main():
    reports=[]
    with tempfile.TemporaryDirectory(prefix="public_tracker_frames_") as tmp:
        folder=Path(tmp)
        for key,url in PUBLIC_VIDEO_URLS.items():
            try:
                print("VIDEO_AUDIT_BEGIN",key,flush=True)
                report=examine(key,url,folder)
                reports.append(report)
                print("VIDEO_AUDIT_OK",json.dumps({k:v for k,v in report.items() if k!="contact_sheets"}),flush=True)
            except Exception as e:
                reports.append({"title":key,"public_url":url,"error":type(e).__name__+":"+str(e)[:250]})
                print("VIDEO_AUDIT_ERROR",key,type(e).__name__,str(e)[:250],flush=True)
    out=Path("research/results");out.mkdir(parents=True,exist_ok=True)
    (out/"tracker_public_video_metadata.json").write_text(json.dumps(reports,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("VIDEO_AUDIT_ALL",json.dumps([{k:v for k,v in r.items() if k!="contact_sheets"} for r in reports],ensure_ascii=False),flush=True)

if __name__=="__main__":
    main()
