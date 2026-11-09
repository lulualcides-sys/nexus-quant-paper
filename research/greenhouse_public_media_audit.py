"""Public-only evidence harvester for Greenhouse Tracker marketing pages.

Does not access member area, checkout, authentication, protected APIs,
private indicators, or trading accounts. It inventories explicitly served
HTML/JS assets and public video references for independent REA inspection.

All raw HTML/JS stays transient in the CI workspace (not committed).
Output JSON is URL/metadata only, no third-party video redistribution.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

URLS=[
 "https://lojadagreenhouse.com.br/ofertatracker/",
 "https://lojadagreenhouse.com.br/tracker/",
 "https://lojadagreenhouse.com.br/",
]
UA="NexusQuantPublicVideoResearch/1.0 (read-only public documents; contact via repository)"
MAX_HTML_BYTES=5_000_000
MAX_JS_BYTES=1_200_000
MAX_JS_ASSETS=16
VIDEO_EXT=( ".mp4",".webm",".m3u8",".mov" )

class Tags(HTMLParser):
    def __init__(self):
        super().__init__()
        self.attrs=[]
        self.inline_js=[]
        self.in_script=False
        self.script_chunks=[]
    def handle_starttag(self,tag,attrs):
        d={str(k).lower():str(v or "") for k,v in attrs}
        if tag in ("script","video","source","iframe","a","img","track"):
            self.attrs.append({"tag":tag,"attrs":d})
        if tag=="script" and not d.get("src"):
            self.in_script=True
            self.script_chunks=[]
    def handle_data(self,s):
        if self.in_script:
            self.script_chunks.append(s)
    def handle_endtag(self,tag):
        if tag=="script" and self.in_script:
            self.inline_js.append("".join(self.script_chunks))
            self.in_script=False


def fetch_bytes(url,limit):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"text/html,application/javascript;q=0.9,*/*;q=0.8"})
    with urllib.request.urlopen(req,timeout=25) as response:
        d=response.read(limit+1)
        if len(d)>limit:
            raise ValueError("public asset exceeds conservative size cap")
        return d,response.geturl(),response.headers.get("content-type","")


def safe_link(value,base):
    value=html.unescape(str(value or "").replace("\\/","/")).strip("\"' \t\r\n")
    if not value or value.startswith(("javascript:","blob:","data:","#")):
        return None
    if value.startswith("//"):
        value="https:"+value
    p=urllib.parse.urljoin(base,value)
    parts=urllib.parse.urlparse(p)
    if parts.scheme not in ("https","http") or not parts.hostname:
        return None
    if parts.username or parts.password:
        return None
    # Tracked URL queries can contain personal identifiers. Log path only.
    return urllib.parse.urlunparse((parts.scheme,parts.netloc,parts.path,"","",""))


def media_kind(u):
    s=u.lower()
    if any(s.endswith(x) for x in VIDEO_EXT):
        return "video_file"
    if "youtube.com" in s or "youtu.be" in s or "youtube-nocookie.com" in s:
        return "youtube"
    if "vimeo.com" in s or "player.vimeo.com" in s:
        return "vimeo"
    if "wistia." in s or "bunny." in s or "mux." in s:
        return "other_player"
    return None

def list_public_media():
    out={"purpose":"public promotional media audit, no paywall","pages":[],"assets":[],"media_refs":[],"errors":[]}
    js_dir=Path("site-js");js_dir.mkdir(parents=True,exist_ok=True)
    index=0
    for page in URLS:
        try:
            raw,final,ctype=fetch_bytes(page,MAX_HTML_BYTES)
        except Exception as e:
            out["errors"].append({"url":page,"error":type(e).__name__+":"+str(e)[:180]})
            continue
        document=raw.decode("utf-8-sig",errors="replace")
        tags=Tags();tags.feed(document)
        page_entry={"url":page,"bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest(),
                    "inline_script_count":len(tags.inline_js),"tag_count":len(tags.attrs)}
        out["pages"].append(page_entry)
        def record(ref,src):
            u=safe_link(ref,final)
            if u is None:
                return
            kind=media_kind(u)
            if kind or src in ("video","source","track"):
                item={"reference_url":u,"type":kind or src,"observed_in":page,"evidence":src}
                if item not in out["media_refs"]:
                    out["media_refs"].append(item)
        # public attributes, including direct data-* and src/srcset candidates
        for tag in tags.attrs:
            attrs=tag["attrs"]
            for k,v in attrs.items():
                if k in ("src","href","poster","data-src","data-video","data-video-url",
                         "data-youtube","data-youtube-id","data-embed","data-mp4","data-hls"):
                    record(v,tag["tag"]+" "+k)
            if tag["tag"]=="script" and attrs.get("src") and index<MAX_JS_ASSETS:
                u=safe_link(attrs["src"],final)
                if not u or urllib.parse.urlparse(u).hostname!="lojadagreenhouse.com.br":
                    continue
                try:
                    b,_,js_ctype=fetch_bytes(u,MAX_JS_BYTES)
                    if "javascript" in js_ctype.lower() or u.endswith(".js"):
                        target=js_dir/f"asset_{index:02}.js"
                        target.write_bytes(b)
                        out["assets"].append({"src":u,"sha256":hashlib.sha256(b).hexdigest(),
                                              "bytes":len(b),"saved_as":str(target)})
                        index+=1
                        for pattern in (r"https?[:][/]{2}[^\s'\"<>]{6,250}",
                                        r"[/][^\s'\"<>]{3,200}\.(?:mp4|webm|m3u8)"):
                            for match in re.findall(pattern,b.decode("utf-8",errors="replace"),flags=re.I):
                                record(match,"external_public_js")
                except Exception as e:
                    out["errors"].append({"url":u,"error":str(e)[:120]})
        # JSX/inline scripts, public source visible in browser
        for i,content in enumerate(tags.inline_js):
            if not content.strip():
                continue
            if len(content.encode("utf-8"))<=MAX_JS_BYTES:
                target=js_dir/f"inline_{len(out['assets']):03}_{i:03}.js"
                target.write_text(content,encoding="utf-8")
                out["assets"].append({"src":final+"#inline="+str(i),"bytes":len(content),
                                       "sha256":hashlib.sha256(content.encode()).hexdigest(),
                                       "saved_as":str(target)})
            # capture URL-like refs including escaped HTML/JS string values
            normalized=html.unescape(content.replace("\\/","/"))
            for m in re.findall(r"https?://[A-Za-z0-9\-._~/?#%&+=:@,;]{12,350}",normalized):
                record(m,"inline_public_js")
            for m in re.findall(r"[/][A-Za-z0-9_\-/]{4,200}\.(?:mp4|webm|m3u8)",normalized,flags=re.I):
                record(m,"inline_video_path")
        # literal .mp4 references inside HTML outside JS
        for m in re.findall(r"https?://[A-Za-z0-9\-._~/?#%&+=:@,;]{10,350}\.(?:mp4|webm|m3u8)",document,flags=re.I):
            record(m,"html_literal")
        # Youtube IDs from public iframe/thumbs (media urls extracted only as links; no login)
        for m in re.findall(r"(?:youtube\.com/embed/|youtube\.com/watch\?v=|youtu\.be/|ytimg\.com/vi/)([A-Za-z0-9_-]{11})",document):
            record("https://www.youtube.com/watch?v="+m,"public_youtube_id")
        # Page hero video and publicly displayed live stream may be embedded via JS JSON
        page_entry["media_reference_count"]=sum(v["observed_in"]==page for v in out["media_refs"])
    return out


def main():
    result=list_public_media()
    Path("research/results").mkdir(parents=True,exist_ok=True)
    Path("research/results/greenhouse_public_media_refs.json").write_text(
        json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PUBLIC_MEDIA_START")
    print(json.dumps({"pages":result["pages"],"assets_count":len(result["assets"]),
                     "media_refs":result["media_refs"][:75],"errors":result["errors"][:15]},
                     ensure_ascii=False,indent=2))
    print("PUBLIC_MEDIA_END")

if __name__=="__main__":
    main()
